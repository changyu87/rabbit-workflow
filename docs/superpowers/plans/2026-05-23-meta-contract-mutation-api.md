# Meta-Contract Mutation API Implementation Plan (Plan B.3)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement `contract.lib.mutation` — the third of four API libraries declared by the meta-contract architecture. Provides 7 idempotent mutation primitives + 1 escape hatch that `/rabbit-config` dispatchers will invoke when a feature's CONFIGURATION declares a value change.

**Architecture:** New module `lib/mutation.py` follows the same pattern as `lib/publish.py`: each API is a function that takes its declared args plus keyword-only context (`repo_root` for filesystem APIs; `feature_dir` for the script escape hatch) and returns a `CheckResult` from `lib.checks`. Hand-rolled dotted-key path support for the JSON APIs (stdlib only — no third-party JSON-path libs). All operations are idempotent: re-running with unchanged effective state is a no-op.

**Tech Stack:** Python 3 (stdlib only — `json`, `os`, `subprocess`, `pathlib`).

---

## Merge-conflict avoidance with parallel B.2 branch

ws43 is implementing `lib/runtime.py` on `feature/meta-contract-api-libraries` in parallel. To minimize conflicts at merge time:

- **DO NOT** touch `.claude/features/contract/feature.json` (no version bump in this branch)
- **DO NOT** touch `.claude/features/contract/docs/spec/spec.md` (no invariant additions in this branch)
- Both will be updated in a separate merge commit AFTER both B.2 and B.3 land
- `lib/mutation.py` is a brand-new file — no conflict
- `test/run.py` will gain new `run_test(...)` lines at the bottom — minor textual conflict resolvable by accepting both

The final commit message (Task 7) MUST note that spec invariant + version bump are pending in the merge commit.

---

## File structure

**Create:**
- `.claude/features/contract/lib/mutation.py` — module with 7 API functions
- `.claude/features/contract/test/test-mutation-write-marker.py`
- `.claude/features/contract/test/test-mutation-delete-marker.py`
- `.claude/features/contract/test/test-mutation-set-json-key.py`
- `.claude/features/contract/test/test-mutation-delete-json-key.py`
- `.claude/features/contract/test/test-mutation-append-json-array.py`
- `.claude/features/contract/test/test-mutation-remove-json-array-value.py`
- `.claude/features/contract/test/test-mutation-run-feature-script.py`

**Modify:**
- `.claude/features/contract/test/run.py` — append 7 `run_test(...)` lines (one per new test, in same commit as the test it wires)

---

## Universal rules applied to every task

These mirror the foundation plan's Revision R1 / R2 conventions:

**R1 — Same-commit wiring.** Each task that creates a new `test-*.py` file MUST also append the corresponding `run_test("<name>.py")` line to `.claude/features/contract/test/run.py` BEFORE the commit step. The contract suite's `test-run-invokes-all-active-tests.py` meta-test fails otherwise.

**R2 — Idempotency assertion in every test.** Each mutation API is idempotent. Every test file MUST include at least one explicit idempotency test case: invoke the API twice in succession, assert the second call returns `passed=True` AND its messages contain "no-op" (case-insensitive substring). This mirrors the publish-library pattern. (Task 7's `run_feature_script` is the one intentional exception — see Task 7 for the rationale.)

**R3 — repo_root / feature_dir injection.** All filesystem APIs accept `repo_root` (keyword-only) and resolve `path`/`file` relative to it. `run_feature_script` accepts `feature_dir` (keyword-only) and resolves `script` relative to it. Tests use `tempfile.TemporaryDirectory()` as a fake `repo_root` / `feature_dir` — no live filesystem state is touched.

---

## Task 1: Create `lib/mutation.py` skeleton + `write_marker`

**Files:**
- Create: `.claude/features/contract/lib/mutation.py`
- Create: `.claude/features/contract/test/test-mutation-write-marker.py`
- Modify: `.claude/features/contract/test/run.py`

- [ ] **Step 1: Write the failing test**

Create `.claude/features/contract/test/test-mutation-write-marker.py`:

```python
#!/usr/bin/env python3
"""test-mutation-write-marker.py — exercises write_marker: idempotent
creation of a marker file (path relative to repo_root) with given content.
"""

import os
import sys
import tempfile

FEATURE_DIR = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, FEATURE_DIR)

from lib.mutation import write_marker  # noqa: E402

FAIL = 0


def fail(msg):
    global FAIL
    print(f"FAIL: {msg}", file=sys.stderr)
    FAIL = 1


def ok(msg):
    print(f"PASS: {msg}")


# t1: create marker with content (fresh)
with tempfile.TemporaryDirectory() as root:
    r = write_marker(".my-marker", "session", repo_root=root)
    dest = os.path.join(root, ".my-marker")
    if not r.passed:
        fail(f"t1: write_marker failed: {r.messages}")
    elif not os.path.isfile(dest):
        fail("t1: marker file not created")
    elif open(dest).read() != "session":
        fail(f"t1: marker content mismatch: {open(dest).read()!r}")
    else:
        ok("t1: write_marker creates marker file with given content")

# t2: idempotent — second call with same content is no-op
with tempfile.TemporaryDirectory() as root:
    write_marker(".m", "x", repo_root=root)
    r = write_marker(".m", "x", repo_root=root)
    if not r.passed:
        fail(f"t2: second call failed: {r.messages}")
    elif not any("no-op" in m.lower() for m in r.messages):
        fail(f"t2: second call should report 'no-op', got: {r.messages}")
    else:
        ok("t2: idempotent — same content returns no-op")

# t3: content change — second call with different content overwrites
with tempfile.TemporaryDirectory() as root:
    write_marker(".m", "old", repo_root=root)
    r = write_marker(".m", "new", repo_root=root)
    dest = os.path.join(root, ".m")
    if not r.passed:
        fail(f"t3: overwrite failed: {r.messages}")
    elif open(dest).read() != "new":
        fail(f"t3: overwrite did not update content: {open(dest).read()!r}")
    else:
        ok("t3: changed content overwrites marker")

# t4: nested path — parent dirs created automatically
with tempfile.TemporaryDirectory() as root:
    r = write_marker("a/b/.deep-marker", "y", repo_root=root)
    dest = os.path.join(root, "a", "b", ".deep-marker")
    if not r.passed:
        fail(f"t4: nested path failed: {r.messages}")
    elif not os.path.isfile(dest):
        fail("t4: nested marker not created")
    else:
        ok("t4: parent directories created automatically")

# t5: empty content allowed
with tempfile.TemporaryDirectory() as root:
    r = write_marker(".empty", "", repo_root=root)
    dest = os.path.join(root, ".empty")
    if not r.passed:
        fail(f"t5: empty content failed: {r.messages}")
    elif open(dest).read() != "":
        fail(f"t5: empty marker has content: {open(dest).read()!r}")
    else:
        ok("t5: empty content allowed")

if FAIL:
    print("test-mutation-write-marker: FAIL", file=sys.stderr)
    sys.exit(1)
print("test-mutation-write-marker: all checks passed.")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 .claude/features/contract/test/test-mutation-write-marker.py`
Expected: FAIL with `ModuleNotFoundError: No module named 'lib.mutation'`

- [ ] **Step 3: Create `lib/mutation.py` with `write_marker`**

Create `.claude/features/contract/lib/mutation.py`:

```python
"""contract.lib.mutation — API library for state-mutation primitives used by
the rabbit-config dispatcher when a feature's CONFIGURATION declares a value
change.

Each function implements one mutation API call as declared in a feature's
CONFIGURATION section. Functions accept their declared args plus keyword-only
context params (repo_root for filesystem APIs; feature_dir for the script
escape hatch) and return CheckResult.

All mutations are idempotent: re-running with unchanged effective state
returns a CheckResult whose messages contain "no-op". (The
`run_feature_script` escape hatch delegates idempotency to the invoked
script.)

Version: 1.0.0
Owner: rabbit-workflow team (contract)
Deprecation criterion: when the rabbit CLI exposes native configuration mutation.
"""

import json
import os
import subprocess

from lib.checks import CheckResult


def write_marker(path: str, content: str, *, repo_root: str) -> CheckResult:
    """Write a marker file at path (repo-root-relative) with given content.

    Idempotent: if the marker already exists with identical content, returns
    passed=True with a 'no-op' message and does not touch the file.
    Parent directories are created automatically.
    """
    dst = os.path.join(repo_root, path)
    if os.path.isfile(dst):
        try:
            with open(dst) as f:
                if f.read() == content:
                    return CheckResult(True, [f"OK: {path} unchanged (no-op)"])
        except OSError:
            pass
    parent = os.path.dirname(dst)
    if parent:
        os.makedirs(parent, exist_ok=True)
    with open(dst, "w") as f:
        f.write(content)
    return CheckResult(True, [f"OK: {path} written"])
```

(All three top-level imports — `json`, `os`, `subprocess` — are added now so subsequent tasks only append functions, never edit the import block. `json` and `subprocess` are unused by `write_marker` itself but are used by Tasks 3-7. This avoids unrelated import-block churn in every subsequent commit.)

- [ ] **Step 4: Wire the test into `run.py`**

Open `.claude/features/contract/test/run.py`. After the last `run_test(...)` line (currently `run_test("test-publish-generated.py")`), append:

```python
run_test("test-mutation-write-marker.py")
```

- [ ] **Step 5: Run test to verify it passes, then full suite**

```bash
python3 .claude/features/contract/test/test-mutation-write-marker.py
python3 .claude/features/contract/test/run.py
```

Expected: both exit 0; full suite ends with `ALL TESTS PASSED`.

- [ ] **Step 6: Commit**

```bash
git add .claude/features/contract/lib/mutation.py .claude/features/contract/test/test-mutation-write-marker.py .claude/features/contract/test/run.py
git commit -m "feat(contract): lib/mutation.py — write_marker (idempotent marker write)

Plan B.3 — first of 7 mutation APIs. Module skeleton + write_marker:
creates path (repo-root-relative) with given content; no-op when
already present with matching content; auto-creates parent dirs.
Wired into test/run.py."
```

---

## Task 2: `delete_marker`

**Files:**
- Modify: `.claude/features/contract/lib/mutation.py` (append function)
- Create: `.claude/features/contract/test/test-mutation-delete-marker.py`
- Modify: `.claude/features/contract/test/run.py`

- [ ] **Step 1: Write the failing test**

Create `.claude/features/contract/test/test-mutation-delete-marker.py`:

```python
#!/usr/bin/env python3
"""test-mutation-delete-marker.py — exercises delete_marker: idempotent
removal of a marker file (no-op if already absent).
"""

import os
import sys
import tempfile

FEATURE_DIR = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, FEATURE_DIR)

from lib.mutation import delete_marker, write_marker  # noqa: E402

FAIL = 0


def fail(msg):
    global FAIL
    print(f"FAIL: {msg}", file=sys.stderr)
    FAIL = 1


def ok(msg):
    print(f"PASS: {msg}")


# t1: delete existing marker
with tempfile.TemporaryDirectory() as root:
    write_marker(".m", "x", repo_root=root)
    r = delete_marker(".m", repo_root=root)
    if not r.passed:
        fail(f"t1: delete failed: {r.messages}")
    elif os.path.exists(os.path.join(root, ".m")):
        fail("t1: marker still exists after delete")
    else:
        ok("t1: existing marker is removed")

# t2: idempotent — delete absent marker is no-op
with tempfile.TemporaryDirectory() as root:
    r = delete_marker(".never-existed", repo_root=root)
    if not r.passed:
        fail(f"t2: absent delete failed: {r.messages}")
    elif not any("no-op" in m.lower() for m in r.messages):
        fail(f"t2: absent delete should report 'no-op', got: {r.messages}")
    else:
        ok("t2: idempotent — delete of absent marker is no-op")

# t3: two deletes in a row — second is no-op
with tempfile.TemporaryDirectory() as root:
    write_marker(".m", "x", repo_root=root)
    delete_marker(".m", repo_root=root)
    r = delete_marker(".m", repo_root=root)
    if not r.passed:
        fail(f"t3: second delete failed: {r.messages}")
    elif not any("no-op" in m.lower() for m in r.messages):
        fail(f"t3: second delete should report 'no-op', got: {r.messages}")
    else:
        ok("t3: second consecutive delete is no-op")

# t4: nested path delete works
with tempfile.TemporaryDirectory() as root:
    write_marker("a/b/.m", "x", repo_root=root)
    r = delete_marker("a/b/.m", repo_root=root)
    if not r.passed:
        fail(f"t4: nested delete failed: {r.messages}")
    elif os.path.exists(os.path.join(root, "a", "b", ".m")):
        fail("t4: nested marker still exists")
    else:
        ok("t4: nested-path delete works")

if FAIL:
    print("test-mutation-delete-marker: FAIL", file=sys.stderr)
    sys.exit(1)
print("test-mutation-delete-marker: all checks passed.")
```

- [ ] **Step 2: Run to verify failure**

Run: `python3 .claude/features/contract/test/test-mutation-delete-marker.py`
Expected: FAIL with `ImportError: cannot import name 'delete_marker'`

- [ ] **Step 3: Append `delete_marker` to `lib/mutation.py`**

Append to `.claude/features/contract/lib/mutation.py`:

```python


def delete_marker(path: str, *, repo_root: str) -> CheckResult:
    """Delete a marker file at path (repo-root-relative).

    Idempotent: if the marker is already absent, returns passed=True with a
    'no-op' message and does not raise.
    """
    dst = os.path.join(repo_root, path)
    if not os.path.exists(dst):
        return CheckResult(True, [f"OK: {path} absent (no-op)"])
    os.remove(dst)
    return CheckResult(True, [f"OK: {path} deleted"])
```

- [ ] **Step 4: Wire test into `run.py`**

Append to `.claude/features/contract/test/run.py`:

```python
run_test("test-mutation-delete-marker.py")
```

- [ ] **Step 5: Run new test + full suite**

```bash
python3 .claude/features/contract/test/test-mutation-delete-marker.py
python3 .claude/features/contract/test/run.py
```

Expected: both exit 0.

- [ ] **Step 6: Commit**

```bash
git add .claude/features/contract/lib/mutation.py .claude/features/contract/test/test-mutation-delete-marker.py .claude/features/contract/test/run.py
git commit -m "feat(contract): delete_marker — idempotent marker removal

Removes a marker file at path (repo-root-relative). No-op if already
absent. Pairs with write_marker for the marker-file storage type
declared in the meta-contract configuration schema."
```

---

## Task 3: `set_json_key` with dotted key paths

**Files:**
- Modify: `.claude/features/contract/lib/mutation.py` (append helpers + function)
- Create: `.claude/features/contract/test/test-mutation-set-json-key.py`
- Modify: `.claude/features/contract/test/run.py`

- [ ] **Step 1: Write the failing test**

Create `.claude/features/contract/test/test-mutation-set-json-key.py`:

```python
#!/usr/bin/env python3
"""test-mutation-set-json-key.py — exercises set_json_key: write a value at
a dotted JSON-key path (e.g. 'permissions.defaultMode') in a JSON file.
Creates the file if absent. Creates intermediate objects as needed.
Idempotent on identical value.
"""

import os
import sys
import json
import tempfile

FEATURE_DIR = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, FEATURE_DIR)

from lib.mutation import set_json_key  # noqa: E402

FAIL = 0


def fail(msg):
    global FAIL
    print(f"FAIL: {msg}", file=sys.stderr)
    FAIL = 1


def ok(msg):
    print(f"PASS: {msg}")


def load(root, name):
    with open(os.path.join(root, name)) as f:
        return json.load(f)


# t1: set top-level key in fresh file
with tempfile.TemporaryDirectory() as root:
    r = set_json_key(".s.json", "model", "claude-opus-4-7", repo_root=root)
    if not r.passed:
        fail(f"t1: failed: {r.messages}")
    elif load(root, ".s.json") != {"model": "claude-opus-4-7"}:
        fail(f"t1: wrong content: {load(root, '.s.json')}")
    else:
        ok("t1: set top-level key in fresh file")

# t2: set dotted key (creates intermediate dict)
with tempfile.TemporaryDirectory() as root:
    r = set_json_key(".s.json", "permissions.defaultMode", "bypassPermissions", repo_root=root)
    if not r.passed:
        fail(f"t2: failed: {r.messages}")
    elif load(root, ".s.json") != {"permissions": {"defaultMode": "bypassPermissions"}}:
        fail(f"t2: wrong content: {load(root, '.s.json')}")
    else:
        ok("t2: dotted key creates intermediate dict")

# t3: idempotent — same value returns no-op
with tempfile.TemporaryDirectory() as root:
    set_json_key(".s.json", "a.b", 1, repo_root=root)
    r = set_json_key(".s.json", "a.b", 1, repo_root=root)
    if not r.passed:
        fail(f"t3: second call failed: {r.messages}")
    elif not any("no-op" in m.lower() for m in r.messages):
        fail(f"t3: should report no-op: {r.messages}")
    else:
        ok("t3: idempotent — same value is no-op")

# t4: changed value overwrites
with tempfile.TemporaryDirectory() as root:
    set_json_key(".s.json", "a.b", 1, repo_root=root)
    r = set_json_key(".s.json", "a.b", 2, repo_root=root)
    if not r.passed:
        fail(f"t4: overwrite failed: {r.messages}")
    elif load(root, ".s.json") != {"a": {"b": 2}}:
        fail(f"t4: wrong content: {load(root, '.s.json')}")
    else:
        ok("t4: changed value overwrites")

# t5: preserves sibling keys at every level
with tempfile.TemporaryDirectory() as root:
    path = os.path.join(root, ".s.json")
    with open(path, "w") as f:
        json.dump({"keep": "this", "permissions": {"allow": ["X"]}}, f)
    r = set_json_key(".s.json", "permissions.defaultMode", "bypassPermissions", repo_root=root)
    if not r.passed:
        fail(f"t5: failed: {r.messages}")
    else:
        d = load(root, ".s.json")
        if d.get("keep") != "this":
            fail(f"t5: lost sibling top-level key: {d}")
        elif d.get("permissions", {}).get("allow") != ["X"]:
            fail(f"t5: lost sibling nested key: {d}")
        elif d.get("permissions", {}).get("defaultMode") != "bypassPermissions":
            fail(f"t5: did not set new key: {d}")
        else:
            ok("t5: sibling keys (top-level and nested) preserved")

# t6: non-string value types (int, bool, list) round-trip correctly
with tempfile.TemporaryDirectory() as root:
    set_json_key(".s.json", "x.n", 42, repo_root=root)
    set_json_key(".s.json", "x.b", True, repo_root=root)
    set_json_key(".s.json", "x.l", [1, 2], repo_root=root)
    d = load(root, ".s.json")
    if d != {"x": {"n": 42, "b": True, "l": [1, 2]}}:
        fail(f"t6: non-string values broken: {d}")
    else:
        ok("t6: int, bool, list values round-trip")

# t7: malformed JSON file → fail, does NOT silently overwrite user data
with tempfile.TemporaryDirectory() as root:
    path = os.path.join(root, ".s.json")
    with open(path, "w") as f:
        f.write("not json at all {")
    r = set_json_key(".s.json", "a", 1, repo_root=root)
    if r.passed:
        fail("t7: malformed JSON should be rejected, not silently overwritten")
    elif not any("json" in m.lower() for m in r.messages):
        fail(f"t7: error message should mention JSON: {r.messages}")
    elif open(path).read() != "not json at all {":
        fail("t7: file contents changed despite failure")
    else:
        ok("t7: malformed JSON rejected; file contents preserved")

if FAIL:
    print("test-mutation-set-json-key: FAIL", file=sys.stderr)
    sys.exit(1)
print("test-mutation-set-json-key: all checks passed.")
```

- [ ] **Step 2: Run to verify failure**

Run: `python3 .claude/features/contract/test/test-mutation-set-json-key.py`
Expected: FAIL with ImportError.

- [ ] **Step 3: Append helpers + `set_json_key` to `lib/mutation.py`**

Append (helpers first, then the public API):

```python


def _load_json_or_empty(path: str) -> tuple:
    """Read JSON file. Returns (data, error_msg).

    Missing file -> ({}, None). Malformed JSON -> (None, "...").
    """
    if not os.path.isfile(path):
        return {}, None
    try:
        with open(path) as f:
            return json.load(f), None
    except json.JSONDecodeError as e:
        return None, f"ERROR: malformed JSON in {path}: {e}"


def _write_json(path: str, data) -> None:
    """Write data to path as indented JSON. Creates parent dirs."""
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f, indent=2)


def _set_nested(d: dict, key_path: str, value) -> None:
    """Set value at dotted key_path inside d, creating intermediate dicts.

    If an intermediate node exists but is not a dict, it is overwritten with
    a fresh dict. Mutates d in place.
    """
    parts = key_path.split(".")
    for p in parts[:-1]:
        if not isinstance(d.get(p), dict):
            d[p] = {}
        d = d[p]
    d[parts[-1]] = value


def _get_nested(d, key_path: str):
    """Return value at dotted key_path; raises KeyError if any segment is
    missing or any intermediate value is not a dict.
    """
    parts = key_path.split(".")
    for p in parts:
        if not isinstance(d, dict) or p not in d:
            raise KeyError(key_path)
        d = d[p]
    return d


def set_json_key(file: str, key: str, value, *, repo_root: str) -> CheckResult:
    """Set value at dotted JSON key path in file (repo-root-relative).

    Creates the file (and intermediate dicts) if absent. Preserves all sibling
    keys at every level. Idempotent: if the value already equals the new value,
    returns passed=True with a 'no-op' message and does not rewrite the file.

    On malformed JSON, returns passed=False without modifying the file.
    """
    path = os.path.join(repo_root, file)
    data, err = _load_json_or_empty(path)
    if err is not None:
        return CheckResult(False, [err])
    try:
        existing = _get_nested(data, key)
        if existing == value:
            return CheckResult(True, [f"OK: {file}::{key} unchanged (no-op)"])
    except KeyError:
        pass
    _set_nested(data, key, value)
    _write_json(path, data)
    return CheckResult(True, [f"OK: {file}::{key} set"])
```

- [ ] **Step 4: Wire test into `run.py`**

Append:
```python
run_test("test-mutation-set-json-key.py")
```

- [ ] **Step 5: Run new test + full suite**

```bash
python3 .claude/features/contract/test/test-mutation-set-json-key.py
python3 .claude/features/contract/test/run.py
```

Expected: both exit 0.

- [ ] **Step 6: Commit**

```bash
git add .claude/features/contract/lib/mutation.py .claude/features/contract/test/test-mutation-set-json-key.py .claude/features/contract/test/run.py
git commit -m "feat(contract): set_json_key — dotted-path JSON value setter

Supports dotted key paths (e.g. permissions.defaultMode), creates
intermediate dicts as needed, preserves sibling keys at every level.
Idempotent: unchanged value is a no-op. Malformed JSON file is
rejected without overwriting user data."
```

---

## Task 4: `delete_json_key` with dotted key paths

**Files:**
- Modify: `.claude/features/contract/lib/mutation.py`
- Create: `.claude/features/contract/test/test-mutation-delete-json-key.py`
- Modify: `.claude/features/contract/test/run.py`

- [ ] **Step 1: Write the failing test**

Create `.claude/features/contract/test/test-mutation-delete-json-key.py`:

```python
#!/usr/bin/env python3
"""test-mutation-delete-json-key.py — exercises delete_json_key: remove a
key at a dotted JSON path. Idempotent (no-op if key absent). Does not
remove the empty-parent object (preserves sibling keys at every level).
"""

import os
import sys
import json
import tempfile

FEATURE_DIR = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, FEATURE_DIR)

from lib.mutation import delete_json_key, set_json_key  # noqa: E402

FAIL = 0


def fail(msg):
    global FAIL
    print(f"FAIL: {msg}", file=sys.stderr)
    FAIL = 1


def ok(msg):
    print(f"PASS: {msg}")


def load(root, name):
    with open(os.path.join(root, name)) as f:
        return json.load(f)


# t1: delete existing top-level key
with tempfile.TemporaryDirectory() as root:
    set_json_key(".s.json", "x", 1, repo_root=root)
    r = delete_json_key(".s.json", "x", repo_root=root)
    if not r.passed:
        fail(f"t1: failed: {r.messages}")
    elif load(root, ".s.json") != {}:
        fail(f"t1: wrong content: {load(root, '.s.json')}")
    else:
        ok("t1: deletes existing top-level key")

# t2: delete dotted key, preserve siblings + parent
with tempfile.TemporaryDirectory() as root:
    set_json_key(".s.json", "permissions.defaultMode", "bypassPermissions", repo_root=root)
    set_json_key(".s.json", "permissions.allow", ["X"], repo_root=root)
    r = delete_json_key(".s.json", "permissions.defaultMode", repo_root=root)
    if not r.passed:
        fail(f"t2: failed: {r.messages}")
    else:
        d = load(root, ".s.json")
        if "permissions" not in d:
            fail(f"t2: parent object removed: {d}")
        elif "defaultMode" in d["permissions"]:
            fail(f"t2: key not deleted: {d}")
        elif d["permissions"].get("allow") != ["X"]:
            fail(f"t2: sibling key lost: {d}")
        else:
            ok("t2: deletes dotted key, preserves siblings and parent object")

# t3: idempotent — delete absent key
with tempfile.TemporaryDirectory() as root:
    set_json_key(".s.json", "other", 1, repo_root=root)
    r = delete_json_key(".s.json", "never.existed", repo_root=root)
    if not r.passed:
        fail(f"t3: absent-key delete failed: {r.messages}")
    elif not any("no-op" in m.lower() for m in r.messages):
        fail(f"t3: absent-key delete should be no-op: {r.messages}")
    else:
        ok("t3: idempotent — absent key delete is no-op")

# t4: missing intermediate dict → no-op (not error)
with tempfile.TemporaryDirectory() as root:
    set_json_key(".s.json", "a", 1, repo_root=root)
    r = delete_json_key(".s.json", "a.b.c", repo_root=root)
    if not r.passed:
        fail(f"t4: missing-intermediate failed: {r.messages}")
    elif not any("no-op" in m.lower() for m in r.messages):
        fail(f"t4: should report no-op: {r.messages}")
    elif load(root, ".s.json") != {"a": 1}:
        fail(f"t4: original data disturbed: {load(root, '.s.json')}")
    else:
        ok("t4: missing intermediate is no-op (data preserved)")

# t5: absent file is no-op (not error)
with tempfile.TemporaryDirectory() as root:
    r = delete_json_key(".s.json", "x", repo_root=root)
    if not r.passed:
        fail(f"t5: absent-file delete failed: {r.messages}")
    elif not any("no-op" in m.lower() for m in r.messages):
        fail(f"t5: absent-file delete should be no-op: {r.messages}")
    else:
        ok("t5: absent file is no-op")

# t6: malformed JSON → fail, no overwrite
with tempfile.TemporaryDirectory() as root:
    path = os.path.join(root, ".s.json")
    with open(path, "w") as f:
        f.write("{ not json")
    r = delete_json_key(".s.json", "a", repo_root=root)
    if r.passed:
        fail("t6: malformed JSON should be rejected")
    elif open(path).read() != "{ not json":
        fail("t6: file altered despite failure")
    else:
        ok("t6: malformed JSON rejected; file preserved")

if FAIL:
    print("test-mutation-delete-json-key: FAIL", file=sys.stderr)
    sys.exit(1)
print("test-mutation-delete-json-key: all checks passed.")
```

- [ ] **Step 2: Run to verify failure**

Run: `python3 .claude/features/contract/test/test-mutation-delete-json-key.py`
Expected: ImportError.

- [ ] **Step 3: Append `delete_json_key` to `lib/mutation.py`**

Append:

```python


def _delete_nested(d: dict, key_path: str) -> bool:
    """Delete leaf at dotted key_path inside d. Returns True if deleted,
    False if any segment was missing (no-op).
    """
    parts = key_path.split(".")
    for p in parts[:-1]:
        if not isinstance(d, dict) or p not in d or not isinstance(d[p], dict):
            return False
        d = d[p]
    if isinstance(d, dict) and parts[-1] in d:
        del d[parts[-1]]
        return True
    return False


def delete_json_key(file: str, key: str, *, repo_root: str) -> CheckResult:
    """Delete key at dotted JSON path in file (repo-root-relative).

    Idempotent: missing file, missing key, or missing intermediate dict
    is a no-op. The empty parent object is preserved (sibling keys at
    every level are untouched).

    On malformed JSON, returns passed=False without modifying the file.
    """
    path = os.path.join(repo_root, file)
    if not os.path.isfile(path):
        return CheckResult(True, [f"OK: {file} absent (no-op)"])
    data, err = _load_json_or_empty(path)
    if err is not None:
        return CheckResult(False, [err])
    if not _delete_nested(data, key):
        return CheckResult(True, [f"OK: {file}::{key} absent (no-op)"])
    _write_json(path, data)
    return CheckResult(True, [f"OK: {file}::{key} deleted"])
```

- [ ] **Step 4: Wire test into `run.py`**

Append:
```python
run_test("test-mutation-delete-json-key.py")
```

- [ ] **Step 5: Run new test + full suite**

```bash
python3 .claude/features/contract/test/test-mutation-delete-json-key.py
python3 .claude/features/contract/test/run.py
```

Expected: both exit 0.

- [ ] **Step 6: Commit**

```bash
git add .claude/features/contract/lib/mutation.py .claude/features/contract/test/test-mutation-delete-json-key.py .claude/features/contract/test/run.py
git commit -m "feat(contract): delete_json_key — dotted-path JSON key remover

Removes leaf key at dotted path; preserves the parent object and all
sibling keys. Idempotent across absent file, absent key, and missing
intermediate dict. Malformed JSON rejected without overwrite."
```

---

## Task 5: `append_json_array` (idempotent on duplicates)

**Files:**
- Modify: `.claude/features/contract/lib/mutation.py`
- Create: `.claude/features/contract/test/test-mutation-append-json-array.py`
- Modify: `.claude/features/contract/test/run.py`

- [ ] **Step 1: Write the failing test**

Create `.claude/features/contract/test/test-mutation-append-json-array.py`:

```python
#!/usr/bin/env python3
"""test-mutation-append-json-array.py — exercises append_json_array:
append a value to a JSON array at a dotted path. Creates the array (and
file) if absent. Idempotent on duplicate values (does not re-append).
"""

import os
import sys
import json
import tempfile

FEATURE_DIR = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, FEATURE_DIR)

from lib.mutation import append_json_array, set_json_key  # noqa: E402

FAIL = 0


def fail(msg):
    global FAIL
    print(f"FAIL: {msg}", file=sys.stderr)
    FAIL = 1


def ok(msg):
    print(f"PASS: {msg}")


def load(root, name):
    with open(os.path.join(root, name)) as f:
        return json.load(f)


# t1: append to absent file creates file + array
with tempfile.TemporaryDirectory() as root:
    r = append_json_array(".s.json", "permissions.allow", "Bash(ls:*)", repo_root=root)
    if not r.passed:
        fail(f"t1: failed: {r.messages}")
    elif load(root, ".s.json") != {"permissions": {"allow": ["Bash(ls:*)"]}}:
        fail(f"t1: wrong content: {load(root, '.s.json')}")
    else:
        ok("t1: append to absent file creates array")

# t2: append to existing array
with tempfile.TemporaryDirectory() as root:
    set_json_key(".s.json", "permissions.allow", ["A"], repo_root=root)
    r = append_json_array(".s.json", "permissions.allow", "B", repo_root=root)
    if not r.passed:
        fail(f"t2: failed: {r.messages}")
    elif load(root, ".s.json")["permissions"]["allow"] != ["A", "B"]:
        fail(f"t2: wrong array: {load(root, '.s.json')}")
    else:
        ok("t2: append to existing array")

# t3: idempotent — duplicate value is no-op (does not re-append)
with tempfile.TemporaryDirectory() as root:
    set_json_key(".s.json", "permissions.allow", ["A"], repo_root=root)
    r = append_json_array(".s.json", "permissions.allow", "A", repo_root=root)
    if not r.passed:
        fail(f"t3: failed: {r.messages}")
    elif not any("no-op" in m.lower() for m in r.messages):
        fail(f"t3: duplicate should be no-op: {r.messages}")
    elif load(root, ".s.json")["permissions"]["allow"] != ["A"]:
        fail(f"t3: array changed: {load(root, '.s.json')}")
    else:
        ok("t3: idempotent — duplicate value is no-op")

# t4: existing non-array value at key → error (do not coerce)
with tempfile.TemporaryDirectory() as root:
    set_json_key(".s.json", "x", "not-an-array", repo_root=root)
    r = append_json_array(".s.json", "x", "B", repo_root=root)
    if r.passed:
        fail("t4: non-array key should be rejected (would lose data)")
    elif not any("array" in m.lower() for m in r.messages):
        fail(f"t4: error should mention array: {r.messages}")
    else:
        ok("t4: existing non-array value rejected (data preserved)")

# t5: preserves sibling top-level keys
with tempfile.TemporaryDirectory() as root:
    set_json_key(".s.json", "keep", "this", repo_root=root)
    set_json_key(".s.json", "permissions.allow", ["A"], repo_root=root)
    r = append_json_array(".s.json", "permissions.allow", "B", repo_root=root)
    d = load(root, ".s.json")
    if not r.passed:
        fail(f"t5: failed: {r.messages}")
    elif d.get("keep") != "this":
        fail(f"t5: sibling key lost: {d}")
    elif d["permissions"]["allow"] != ["A", "B"]:
        fail(f"t5: wrong array: {d}")
    else:
        ok("t5: preserves sibling keys")

if FAIL:
    print("test-mutation-append-json-array: FAIL", file=sys.stderr)
    sys.exit(1)
print("test-mutation-append-json-array: all checks passed.")
```

- [ ] **Step 2: Run to verify failure**

Run: `python3 .claude/features/contract/test/test-mutation-append-json-array.py`
Expected: ImportError.

- [ ] **Step 3: Append `append_json_array` to `lib/mutation.py`**

Append:

```python


def append_json_array(file: str, key: str, value, *, repo_root: str) -> CheckResult:
    """Append value to a JSON array at dotted key path in file.

    Creates the file, intermediate dicts, and the array if absent. Idempotent:
    if value is already present in the array, returns passed=True with a
    'no-op' message and does not re-append.

    If an existing value at the key is not an array, returns passed=False
    without modifying the file (data preservation).
    """
    path = os.path.join(repo_root, file)
    data, err = _load_json_or_empty(path)
    if err is not None:
        return CheckResult(False, [err])
    try:
        existing = _get_nested(data, key)
    except KeyError:
        existing = None
    if existing is None:
        _set_nested(data, key, [value])
    elif not isinstance(existing, list):
        return CheckResult(False, [
            f"ERROR: {file}::{key} exists but is not an array (type={type(existing).__name__}); refusing to overwrite"
        ])
    elif value in existing:
        return CheckResult(True, [f"OK: {file}::{key} already contains value (no-op)"])
    else:
        existing.append(value)
    _write_json(path, data)
    return CheckResult(True, [f"OK: {file}::{key} appended"])
```

- [ ] **Step 4: Wire test into `run.py`**

Append:
```python
run_test("test-mutation-append-json-array.py")
```

- [ ] **Step 5: Run new test + full suite**

```bash
python3 .claude/features/contract/test/test-mutation-append-json-array.py
python3 .claude/features/contract/test/run.py
```

Expected: both exit 0.

- [ ] **Step 6: Commit**

```bash
git add .claude/features/contract/lib/mutation.py .claude/features/contract/test/test-mutation-append-json-array.py .claude/features/contract/test/run.py
git commit -m "feat(contract): append_json_array — idempotent array append

Appends value at dotted JSON key path. Creates file/intermediate dicts/
array if absent. Idempotent on duplicate value (no-op, no re-append).
Refuses to overwrite an existing non-array value to preserve user data."
```

---

## Task 6: `remove_json_array_value`

**Files:**
- Modify: `.claude/features/contract/lib/mutation.py`
- Create: `.claude/features/contract/test/test-mutation-remove-json-array-value.py`
- Modify: `.claude/features/contract/test/run.py`

- [ ] **Step 1: Write the failing test**

Create `.claude/features/contract/test/test-mutation-remove-json-array-value.py`:

```python
#!/usr/bin/env python3
"""test-mutation-remove-json-array-value.py — exercises
remove_json_array_value: remove a single value from a JSON array at a
dotted path. Idempotent (no-op on absent file/key/value). Empty array
remains as []; key is not auto-removed.
"""

import os
import sys
import json
import tempfile

FEATURE_DIR = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, FEATURE_DIR)

from lib.mutation import remove_json_array_value, set_json_key  # noqa: E402

FAIL = 0


def fail(msg):
    global FAIL
    print(f"FAIL: {msg}", file=sys.stderr)
    FAIL = 1


def ok(msg):
    print(f"PASS: {msg}")


def load(root, name):
    with open(os.path.join(root, name)) as f:
        return json.load(f)


# t1: remove existing value from array
with tempfile.TemporaryDirectory() as root:
    set_json_key(".s.json", "permissions.allow", ["A", "B", "C"], repo_root=root)
    r = remove_json_array_value(".s.json", "permissions.allow", "B", repo_root=root)
    if not r.passed:
        fail(f"t1: failed: {r.messages}")
    elif load(root, ".s.json")["permissions"]["allow"] != ["A", "C"]:
        fail(f"t1: wrong array: {load(root, '.s.json')}")
    else:
        ok("t1: removes existing value")

# t2: idempotent — absent value is no-op
with tempfile.TemporaryDirectory() as root:
    set_json_key(".s.json", "p", ["A"], repo_root=root)
    r = remove_json_array_value(".s.json", "p", "Z", repo_root=root)
    if not r.passed:
        fail(f"t2: failed: {r.messages}")
    elif not any("no-op" in m.lower() for m in r.messages):
        fail(f"t2: should be no-op: {r.messages}")
    elif load(root, ".s.json")["p"] != ["A"]:
        fail(f"t2: array changed: {load(root, '.s.json')}")
    else:
        ok("t2: idempotent — absent value is no-op")

# t3: absent file is no-op (not error)
with tempfile.TemporaryDirectory() as root:
    r = remove_json_array_value(".s.json", "p", "X", repo_root=root)
    if not r.passed:
        fail(f"t3: absent-file failed: {r.messages}")
    elif not any("no-op" in m.lower() for m in r.messages):
        fail(f"t3: absent file should be no-op: {r.messages}")
    else:
        ok("t3: absent file is no-op")

# t4: absent key is no-op
with tempfile.TemporaryDirectory() as root:
    set_json_key(".s.json", "other", 1, repo_root=root)
    r = remove_json_array_value(".s.json", "never.existed", "X", repo_root=root)
    if not r.passed:
        fail(f"t4: absent-key failed: {r.messages}")
    elif not any("no-op" in m.lower() for m in r.messages):
        fail(f"t4: absent key should be no-op: {r.messages}")
    else:
        ok("t4: absent key is no-op")

# t5: removing only value leaves empty array (key NOT auto-removed)
with tempfile.TemporaryDirectory() as root:
    set_json_key(".s.json", "p", ["A"], repo_root=root)
    r = remove_json_array_value(".s.json", "p", "A", repo_root=root)
    if not r.passed:
        fail(f"t5: failed: {r.messages}")
    elif load(root, ".s.json") != {"p": []}:
        fail(f"t5: empty array not preserved: {load(root, '.s.json')}")
    else:
        ok("t5: empty array remains; key not auto-removed")

# t6: duplicate values — removes only first occurrence (deterministic)
with tempfile.TemporaryDirectory() as root:
    set_json_key(".s.json", "p", ["A", "B", "A"], repo_root=root)
    r = remove_json_array_value(".s.json", "p", "A", repo_root=root)
    if not r.passed:
        fail(f"t6: failed: {r.messages}")
    elif load(root, ".s.json")["p"] != ["B", "A"]:
        fail(f"t6: wrong array (expected single-occurrence removal): {load(root, '.s.json')}")
    else:
        ok("t6: removes first occurrence only (single-removal semantics)")

# t7: existing non-array value at key → error
with tempfile.TemporaryDirectory() as root:
    set_json_key(".s.json", "x", "string-not-array", repo_root=root)
    r = remove_json_array_value(".s.json", "x", "Z", repo_root=root)
    if r.passed:
        fail("t7: non-array key should be rejected")
    elif not any("array" in m.lower() for m in r.messages):
        fail(f"t7: error should mention array: {r.messages}")
    else:
        ok("t7: non-array value rejected (data preserved)")

if FAIL:
    print("test-mutation-remove-json-array-value: FAIL", file=sys.stderr)
    sys.exit(1)
print("test-mutation-remove-json-array-value: all checks passed.")
```

- [ ] **Step 2: Run to verify failure**

Run: `python3 .claude/features/contract/test/test-mutation-remove-json-array-value.py`
Expected: ImportError.

- [ ] **Step 3: Append `remove_json_array_value` to `lib/mutation.py`**

Append:

```python


def remove_json_array_value(file: str, key: str, value, *, repo_root: str) -> CheckResult:
    """Remove value from JSON array at dotted key path in file.

    Idempotent: absent file, absent key, and absent value are all no-ops.
    Removes the first occurrence only (deterministic single-removal). The
    empty array is preserved; the key is not auto-removed.

    If an existing value at the key is not an array, returns passed=False
    without modifying the file (data preservation).
    """
    path = os.path.join(repo_root, file)
    if not os.path.isfile(path):
        return CheckResult(True, [f"OK: {file} absent (no-op)"])
    data, err = _load_json_or_empty(path)
    if err is not None:
        return CheckResult(False, [err])
    try:
        existing = _get_nested(data, key)
    except KeyError:
        return CheckResult(True, [f"OK: {file}::{key} absent (no-op)"])
    if not isinstance(existing, list):
        return CheckResult(False, [
            f"ERROR: {file}::{key} exists but is not an array (type={type(existing).__name__}); refusing to modify"
        ])
    if value not in existing:
        return CheckResult(True, [f"OK: {file}::{key} does not contain value (no-op)"])
    existing.remove(value)
    _write_json(path, data)
    return CheckResult(True, [f"OK: {file}::{key} value removed"])
```

- [ ] **Step 4: Wire test into `run.py`**

Append:
```python
run_test("test-mutation-remove-json-array-value.py")
```

- [ ] **Step 5: Run new test + full suite**

```bash
python3 .claude/features/contract/test/test-mutation-remove-json-array-value.py
python3 .claude/features/contract/test/run.py
```

Expected: both exit 0.

- [ ] **Step 6: Commit**

```bash
git add .claude/features/contract/lib/mutation.py .claude/features/contract/test/test-mutation-remove-json-array-value.py .claude/features/contract/test/run.py
git commit -m "feat(contract): remove_json_array_value — idempotent array element remover

Removes first occurrence of value from JSON array at dotted key path.
Idempotent across absent file, absent key, and absent value. Empty
array preserved (key not auto-removed). Non-array value rejected."
```

---

## Task 7: `run_feature_script` (escape hatch)

**Files:**
- Modify: `.claude/features/contract/lib/mutation.py`
- Create: `.claude/features/contract/test/test-mutation-run-feature-script.py`
- Modify: `.claude/features/contract/test/run.py`

This is the one mutation API that is *intentionally* NOT idempotent at the library layer — idempotency is delegated to the invoked feature script. Rationale: the escape hatch exists precisely for mutations that don't fit standard primitives (e.g. chmod for repo-permissions), and the script author owns the correct idempotency semantics for the operation. Forcing a fake "no-op" wrapper here would either be a lie (returning success for ops we didn't actually inspect) or require us to re-inspect the side effect from the outside (defeats the purpose of the escape hatch).

- [ ] **Step 1: Write the failing test**

Create `.claude/features/contract/test/test-mutation-run-feature-script.py`:

```python
#!/usr/bin/env python3
"""test-mutation-run-feature-script.py — exercises run_feature_script: the
mutation API escape hatch. Invokes a feature-owned script (feature-dir-
relative path) with given args. Returns CheckResult based on exit code:
passed=True iff exit 0. Captures stdout/stderr into messages.
"""

import os
import sys
import stat
import tempfile

FEATURE_DIR = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, FEATURE_DIR)

from lib.mutation import run_feature_script  # noqa: E402

FAIL = 0


def fail(msg):
    global FAIL
    print(f"FAIL: {msg}", file=sys.stderr)
    FAIL = 1


def ok(msg):
    print(f"PASS: {msg}")


def write_script(feat, relpath, body):
    p = os.path.join(feat, relpath)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w") as f:
        f.write(body)
    os.chmod(p, os.stat(p).st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return p


# t1: successful exit-0 script
with tempfile.TemporaryDirectory() as feat:
    write_script(feat, "scripts/ok.py",
                 "#!/usr/bin/env python3\nimport sys\nprint('did the thing')\nsys.exit(0)\n")
    r = run_feature_script("scripts/ok.py", [], feature_dir=feat)
    if not r.passed:
        fail(f"t1: exit-0 script failed: {r.messages}")
    elif not any("did the thing" in m for m in r.messages):
        fail(f"t1: stdout not captured: {r.messages}")
    else:
        ok("t1: exit-0 script returns passed=True with stdout in messages")

# t2: exit-1 script → passed=False with stderr captured
with tempfile.TemporaryDirectory() as feat:
    write_script(feat, "scripts/bad.py",
                 "#!/usr/bin/env python3\nimport sys\nprint('oops', file=sys.stderr)\nsys.exit(1)\n")
    r = run_feature_script("scripts/bad.py", [], feature_dir=feat)
    if r.passed:
        fail("t2: exit-1 script should return passed=False")
    elif not any("oops" in m for m in r.messages):
        fail(f"t2: stderr not captured: {r.messages}")
    else:
        ok("t2: exit-1 script returns passed=False with stderr captured")

# t3: args forwarded
with tempfile.TemporaryDirectory() as feat:
    write_script(feat, "scripts/echo.py",
                 "#!/usr/bin/env python3\nimport sys\nprint(' '.join(sys.argv[1:]))\n")
    r = run_feature_script("scripts/echo.py", ["lock", "x"], feature_dir=feat)
    if not r.passed:
        fail(f"t3: echo failed: {r.messages}")
    elif not any("lock x" in m for m in r.messages):
        fail(f"t3: args not forwarded: {r.messages}")
    else:
        ok("t3: args forwarded to script")

# t4: missing script → passed=False with descriptive error (not raise)
with tempfile.TemporaryDirectory() as feat:
    r = run_feature_script("scripts/nope.py", [], feature_dir=feat)
    if r.passed:
        fail("t4: missing script should return passed=False")
    elif not any(
        s in " ".join(r.messages).lower()
        for s in ("not found", "missing", "no such")
    ):
        fail(f"t4: error should mention missing script: {r.messages}")
    else:
        ok("t4: missing script returns passed=False with descriptive error")

# t5: empty args list works (covers "no args" branch)
with tempfile.TemporaryDirectory() as feat:
    write_script(feat, "scripts/noargs.py",
                 "#!/usr/bin/env python3\nprint('hello')\n")
    r = run_feature_script("scripts/noargs.py", [], feature_dir=feat)
    if not r.passed:
        fail(f"t5: no-args invocation failed: {r.messages}")
    else:
        ok("t5: empty args list works")

if FAIL:
    print("test-mutation-run-feature-script: FAIL", file=sys.stderr)
    sys.exit(1)
print("test-mutation-run-feature-script: all checks passed.")
```

- [ ] **Step 2: Run to verify failure**

Run: `python3 .claude/features/contract/test/test-mutation-run-feature-script.py`
Expected: ImportError.

- [ ] **Step 3: Append `run_feature_script` to `lib/mutation.py`**

Append:

```python


def run_feature_script(script: str, args: list, *, feature_dir: str) -> CheckResult:
    """Escape hatch: invoke a feature-owned script with given args.

    script — feature-dir-relative path to the script (must be executable).
    args   — list of string arguments to forward.

    Returns CheckResult(passed=True) iff the script exits 0. stdout and
    stderr are captured into the messages list (one entry each, only if
    non-empty). Missing script returns passed=False without raising.

    Intentionally NOT idempotent at this layer — idempotency is the
    responsibility of the invoked script. The escape hatch exists for the
    minority of mutations that don't fit standard primitives (e.g. chmod
    for repo-permissions); new standard primitives are preferred.
    """
    script_path = os.path.join(feature_dir, script)
    if not os.path.isfile(script_path):
        return CheckResult(False, [f"ERROR: script not found: {script_path}"])
    proc = subprocess.run([script_path, *args], capture_output=True, text=True)
    messages = []
    if proc.stdout:
        messages.append(f"stdout: {proc.stdout.rstrip()}")
    if proc.stderr:
        messages.append(f"stderr: {proc.stderr.rstrip()}")
    if proc.returncode != 0:
        messages.insert(0, f"ERROR: {script} exited {proc.returncode}")
        return CheckResult(False, messages)
    messages.insert(0, f"OK: {script} succeeded")
    return CheckResult(True, messages)
```

- [ ] **Step 4: Wire test into `run.py`**

Append:
```python
run_test("test-mutation-run-feature-script.py")
```

- [ ] **Step 5: Run new test + full suite**

```bash
python3 .claude/features/contract/test/test-mutation-run-feature-script.py
python3 .claude/features/contract/test/run.py
```

Expected: both exit 0.

- [ ] **Step 6: Commit**

```bash
git add .claude/features/contract/lib/mutation.py .claude/features/contract/test/test-mutation-run-feature-script.py .claude/features/contract/test/run.py
git commit -m "feat(contract): run_feature_script — escape-hatch script invoker

Invokes a feature-owned script (feature-dir-relative) with given args
via subprocess. passed=True iff exit 0; stdout/stderr captured in
messages. Idempotency is delegated to the invoked script.

This is the meta-contract escape hatch for mutations that don't fit
standard primitives (e.g. chmod for repo-permissions).

Completes Plan B.3 — lib/mutation.py now exports all 7 mutation APIs.

NOTE: contract spec invariant + version bump for Plan B.3 are pending
in the merge commit that combines this branch with ws43's parallel
B.2 (runtime APIs) work. Spec/feature.json deliberately untouched here
to avoid merge conflicts."
```

---

## Plan complete — final verification

- [ ] **Run the full contract test suite**

```bash
python3 .claude/features/contract/test/run.py
```

Expected: every test PASS; final line `ALL TESTS PASSED`. The 7 new mutation tests (`test-mutation-*.py`) appear after the publish tests.

- [ ] **Confirm git log shows 7 commits in order**

```bash
git log --oneline feature/meta-contract-api-libraries..HEAD
```

Expected: 7 commits, one per task (write_marker → delete_marker → set_json_key → delete_json_key → append_json_array → remove_json_array_value → run_feature_script).

- [ ] **Confirm scope-protected files were NOT modified**

```bash
git diff --name-only feature/meta-contract-api-libraries..HEAD | grep -E '^\.claude/features/contract/(feature\.json|docs/spec/spec\.md)$' && echo "FAIL: scope-protected file touched" || echo "OK: scope-protected files preserved"
```

Expected: `OK: scope-protected files preserved`.

- [ ] **Push branch**

```bash
git push -u origin feature/meta-contract-mutation-api
```

---

## What this plan does NOT do (deferred to merge commit / later plans)

- **Contract spec invariant for `lib/mutation.py`** — added in the merge commit that combines B.2 and B.3 (one new invariant per library, plus one version bump).
- **`feature.json` version bump** — same merge commit.
- **Wiring mutation APIs into `/rabbit-config`** — `rabbit-config` feature does not exist yet (Plan D).
- **Per-feature CONFIGURATION declarations** — Plan E migration sweep.
- **Validation that mutation calls in a CONFIGURATION block reference args that match the API signature** — currently the configuration-arm validator only checks the API name is in the enum; per-API arg validation is deferred until needed.
