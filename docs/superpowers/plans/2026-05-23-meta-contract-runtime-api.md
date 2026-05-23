# Meta-Contract Runtime API Implementation Plan (Plan B.2)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement `contract.lib.runtime` — eight runtime API functions invoked by per-event dispatcher hooks (Stop, SessionStart, UserPromptSubmit) with full behavior + unit tests. Each API returns one or more typed values (`print | inject | ok | error`).

**Architecture:** New module `.claude/features/contract/lib/runtime.py`. Stdlib only. Late-imports `lib.producers` (Plan B.4 sibling) and `lib.publish` inside any function that needs them so this module is importable independently. Test files follow the per-API split that the publish/mutation/producers siblings used. Tests inject stubs for `lib.producers` and for sibling-feature `feature.json` files via temp directories — no real-feature coupling.

**Tech Stack:** Python 3 (stdlib only). Test pattern matches `test-publish-*.py` and `test-publish-generated.py`: per-test `tempfile.TemporaryDirectory()`, in-test `sys.modules` stubbing for cross-module deps, manual `FAIL`/`fail`/`ok` helpers, `sys.exit(1)` on any failure.

---

## Cross-branch merge-conflict avoidance

Three sibling branches off the same base (`feature/meta-contract-api-libraries`) are landing in parallel:
- `feature/meta-contract-mutation-api` — adds `lib/mutation.py` (DONE)
- `feature/meta-contract-producers-api` — adds `lib/producers.py` (DONE)
- this branch — adds `lib/runtime.py`

To keep the four branches mergeable without rewrites:

1. **DO NOT touch `.claude/features/contract/feature.json`** — no version bump in this branch. The integration commit that lands after all four B.x branches merge will bump the version.
2. **DO NOT touch `.claude/features/contract/docs/spec/spec.md`** — no invariant additions in this branch. New invariants for B.2/B.3/B.4 will be added together in the integration commit.
3. **`test/run.py` IS touched** (append-only `run_test("...")` lines). Merge conflicts here are trivial — each branch appends its own block at end of file; resolve by accepting both blocks.
4. **`CHANGELOG.md` is touched** (append-only). Same conflict resolution as `run.py`.

The final task's commit message must include a note that the version bump + new invariants are pending the integration commit.

---

## Return-type contract

`lib/runtime.py` exposes four module-level factory helpers that callers (the per-event dispatchers) consume. Each builds a tagged dict. Using plain dicts (not dataclasses) keeps JSON-serializable returns trivial — dispatchers will marshal them straight to stdout.

```python
def print_result(text: str, icon: str, color: str) -> dict:
    return {"type": "print", "text": text, "icon": icon, "color": color}

def inject_result(content: str) -> dict:
    return {"type": "inject", "content": content}

def ok_result() -> dict:
    return {"type": "ok"}

def error_result(message: str) -> dict:
    return {"type": "error", "message": message}
```

**API return shapes (the contract every API in this module follows):**

| API | Return shape on hit | Return shape on no-hit | Return shape on error |
|---|---|---|---|
| `check_drift_regenerate` | `[print_result, inject_result]` (list, len 2) | `ok_result()` | `error_result(...)` |
| `check_manifest_drift` | `print_result(...)` | `ok_result()` | `error_result(...)` |
| `check_marker_alert` | `print_result(...)` | `ok_result()` | n/a |
| `check_marker_consume_alert` | `print_result(...)` | `ok_result()` | n/a |
| `check_counter_threshold_refresh` | `inject_result(...)` | `ok_result()` | `error_result(...)` |
| `welcome_with_policy` | `[print_result, inject_result]` (list, len 2) | n/a | `error_result(...)` |
| `iterate_configurables_alerts` | `[print_result, ...]` (list, possibly empty) | `[]` | n/a |
| `iterate_configurables_banner` | `[print_result, ...]` (list, possibly empty) | `[]` | n/a |

Functions that may return either a single result or a list (`check_drift_regenerate`, `welcome_with_policy`) always return a list when they produce both `print` and `inject`. The single-result APIs always return a single dict. The iterate APIs always return a list (possibly empty).

---

## Argument convention

Every API accepts its declared args (the `args` dict from a RUNTIME entry, unpacked as kwargs) plus keyword-only context params:

- `repo_root: str` — absolute path to repository root. Always passed.
- `feature_dir: str` — absolute path to the declaring feature's directory. Passed only to APIs that need feature-local file resolution (currently only `check_drift_regenerate` because it calls producers; the rest are repo-root-only).

Path resolution: every path arg in this module is **repo-root-relative** unless explicitly noted. This differs from `lib.producers` (which accepts feature-dir-relative or `.claude/`-anchored paths). Runtime APIs operate at the workspace level — the declaring feature's path on disk is incidental.

---

## Stubbing pattern for cross-module deps

`lib.producers` is built on the sibling B.4 branch. APIs that call producers (`check_drift_regenerate`) use late import so the module loads without it:

```python
def check_drift_regenerate(target, producer, alert, *, feature_dir, repo_root):
    try:
        from lib import producers  # noqa: PLC0415
    except ImportError as e:
        return error_result(f"lib.producers unavailable: {e}")
    ...
```

Tests inject `lib.producers` via `sys.modules` **before** `from lib.runtime import ...`, exactly the pattern `test-publish-generated.py` uses.

For `iterate_configurables_*` APIs (which read every feature's `feature.json`), tests build a fake repo tree under a `TemporaryDirectory()` with hand-rolled `feature.json` files under `.claude/features/<name>/feature.json`. No real-feature coupling.

---

## Files to be created/modified

**Create:**
- `.claude/features/contract/lib/runtime.py`
- `.claude/features/contract/test/test-runtime-result-helpers.py`
- `.claude/features/contract/test/test-runtime-check-drift-regenerate.py`
- `.claude/features/contract/test/test-runtime-check-manifest-drift.py`
- `.claude/features/contract/test/test-runtime-check-marker-alert.py`
- `.claude/features/contract/test/test-runtime-check-marker-consume-alert.py`
- `.claude/features/contract/test/test-runtime-check-counter-threshold-refresh.py`
- `.claude/features/contract/test/test-runtime-welcome-with-policy.py`
- `.claude/features/contract/test/test-runtime-iterate-configurables-alerts.py`
- `.claude/features/contract/test/test-runtime-iterate-configurables-banner.py`

**Modify (additive only):**
- `.claude/features/contract/test/run.py` — append 9 `run_test(...)` lines (the 9 new test files)
- `.claude/features/contract/CHANGELOG.md` — one entry describing the runtime API library landing

**Explicitly NOT touched:**
- `.claude/features/contract/feature.json`
- `.claude/features/contract/docs/spec/spec.md`

---

## Task 1: Module skeleton + result helpers

**Files:**
- Create: `.claude/features/contract/lib/runtime.py`
- Create: `.claude/features/contract/test/test-runtime-result-helpers.py`
- Modify: `.claude/features/contract/test/run.py`

- [ ] **Step 1: Write the failing test**

Create `.claude/features/contract/test/test-runtime-result-helpers.py`:

```python
#!/usr/bin/env python3
"""test-runtime-result-helpers.py — verifies the four result-factory helpers
(print_result, inject_result, ok_result, error_result) produce tagged dicts
matching the runtime API contract.
"""

import os
import sys

FEATURE_DIR = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, FEATURE_DIR)

from lib.runtime import print_result, inject_result, ok_result, error_result  # noqa: E402

FAIL = 0


def fail(msg):
    global FAIL
    print(f"FAIL: {msg}", file=sys.stderr)
    FAIL = 1


def ok(msg):
    print(f"PASS: {msg}")


# t1: print_result returns the documented tagged dict
r = print_result("hello", "warn", "red")
if r == {"type": "print", "text": "hello", "icon": "warn", "color": "red"}:
    ok("t1: print_result returns tagged dict with text/icon/color")
else:
    fail(f"t1: unexpected print_result: {r!r}")

# t2: inject_result returns the documented tagged dict
r = inject_result("policy text\n")
if r == {"type": "inject", "content": "policy text\n"}:
    ok("t2: inject_result returns tagged dict with content")
else:
    fail(f"t2: unexpected inject_result: {r!r}")

# t3: ok_result returns the documented tagged dict
r = ok_result()
if r == {"type": "ok"}:
    ok("t3: ok_result returns tagged dict with only type")
else:
    fail(f"t3: unexpected ok_result: {r!r}")

# t4: error_result returns the documented tagged dict
r = error_result("something broke")
if r == {"type": "error", "message": "something broke"}:
    ok("t4: error_result returns tagged dict with message")
else:
    fail(f"t4: unexpected error_result: {r!r}")

if FAIL:
    print("test-runtime-result-helpers: FAIL", file=sys.stderr)
    sys.exit(1)
print("test-runtime-result-helpers: all checks passed.")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 .claude/features/contract/test/test-runtime-result-helpers.py`
Expected: FAIL with `ModuleNotFoundError: No module named 'lib.runtime'`

- [ ] **Step 3: Create `lib/runtime.py` with the four helpers**

Create `.claude/features/contract/lib/runtime.py`:

```python
"""contract.lib.runtime — API library for the runtime APIs invoked by the
per-event dispatcher hooks (Stop, SessionStart, UserPromptSubmit). Each
function implements one runtime API call declared in a feature's RUNTIME
section and returns one or more typed result dicts.

Return-type vocabulary (built via the four factory helpers below):
    print   {"type": "print",  "text": str, "icon": str, "color": str}
    inject  {"type": "inject", "content": str}
    ok      {"type": "ok"}
    error   {"type": "error", "message": str}

Functions that may emit both a print and an inject return a list of two
results in [print, inject] order. The single-result APIs return one dict.
The iterate_configurables_* APIs always return a (possibly empty) list of
print results.

Path-arg convention: every path arg accepted by these APIs is repo-root-
relative unless explicitly noted. (This differs from lib.producers, which
resolves relative paths against feature_dir.)

Version: 1.0.0
Owner: rabbit-workflow team (contract)
Deprecation criterion: when the rabbit CLI exposes native per-event
    dispatchers that subsume this library.
"""


def print_result(text: str, icon: str, color: str) -> dict:
    """Tagged dict for an alert line that the dispatcher renders via
    rabbit_print and joins into the Stop hook systemMessage."""
    return {"type": "print", "text": text, "icon": icon, "color": color}


def inject_result(content: str) -> dict:
    """Tagged dict for additional context the dispatcher attaches to the
    Stop/SessionStart/UserPromptSubmit additionalContext field."""
    return {"type": "inject", "content": content}


def ok_result() -> dict:
    """Tagged dict for the no-op case — dispatcher drops these."""
    return {"type": "ok"}


def error_result(message: str) -> dict:
    """Tagged dict for an internal failure — dispatcher logs to stderr and
    does NOT surface to Claude."""
    return {"type": "error", "message": message}
```

- [ ] **Step 4: Wire the new test into `run.py`**

Edit `.claude/features/contract/test/run.py`, append at end of file (before the `print("ALL TESTS PASSED")` line):

```python
run_test("test-runtime-result-helpers.py")
```

- [ ] **Step 5: Run test to verify it passes**

Run: `python3 .claude/features/contract/test/test-runtime-result-helpers.py`
Expected: `test-runtime-result-helpers: all checks passed.`

- [ ] **Step 6: Run the full contract test suite**

Run: `python3 .claude/features/contract/test/run.py`
Expected: `ALL TESTS PASSED`

- [ ] **Step 7: Commit**

```bash
git add .claude/features/contract/lib/runtime.py \
        .claude/features/contract/test/test-runtime-result-helpers.py \
        .claude/features/contract/test/run.py
git commit -m "feat(contract): lib/runtime.py skeleton + result helpers

Module docstring + the four tagged-dict factory helpers
(print_result, inject_result, ok_result, error_result) that
every runtime API will compose its return value from.

Part of CONTRACT-BACKLOG-36 Plan B.2."
```

---

## Task 2: `check_marker_alert(path, content, alert)`

**Files:**
- Modify: `.claude/features/contract/lib/runtime.py`
- Create: `.claude/features/contract/test/test-runtime-check-marker-alert.py`
- Modify: `.claude/features/contract/test/run.py`

**Behavior:** If the marker file at `path` (repo-root-relative) exists, return a print result built from `alert`. If `content` is non-None, the marker must also have that exact content; if file content does not match, treat as absent. If the file is missing, return `ok_result()`.

- [ ] **Step 1: Write the failing test**

Create `.claude/features/contract/test/test-runtime-check-marker-alert.py`:

```python
#!/usr/bin/env python3
"""test-runtime-check-marker-alert.py — exercises check_marker_alert: emits
a print result if the marker file exists (optionally content-matched),
otherwise returns ok.
"""

import os
import sys
import tempfile

FEATURE_DIR = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, FEATURE_DIR)

from lib.runtime import check_marker_alert  # noqa: E402

FAIL = 0


def fail(msg):
    global FAIL
    print(f"FAIL: {msg}", file=sys.stderr)
    FAIL = 1


def ok(msg):
    print(f"PASS: {msg}")


ALERT = {"text": "SCOPE OVERRIDE ACTIVE", "icon": "unlock", "color": "red"}

# t1: marker absent -> ok_result
with tempfile.TemporaryDirectory() as td:
    r = check_marker_alert(".rabbit-scope-override", None, ALERT, repo_root=td)
    if r == {"type": "ok"}:
        ok("t1: missing marker returns ok_result")
    else:
        fail(f"t1: expected ok, got {r!r}")

# t2: marker present, no content filter -> print_result built from alert
with tempfile.TemporaryDirectory() as td:
    with open(os.path.join(td, ".rabbit-scope-override"), "w") as f:
        f.write("anything")
    r = check_marker_alert(".rabbit-scope-override", None, ALERT, repo_root=td)
    if r == {"type": "print", "text": "SCOPE OVERRIDE ACTIVE",
             "icon": "unlock", "color": "red"}:
        ok("t2: present marker without content filter returns print_result")
    else:
        fail(f"t2: unexpected result {r!r}")

# t3: marker present, content matches filter -> print_result
with tempfile.TemporaryDirectory() as td:
    with open(os.path.join(td, ".rabbit-scope-override"), "w") as f:
        f.write("session")
    r = check_marker_alert(".rabbit-scope-override", "session", ALERT, repo_root=td)
    if r.get("type") == "print":
        ok("t3: content match returns print_result")
    else:
        fail(f"t3: expected print, got {r!r}")

# t4: marker present but content does NOT match filter -> ok_result
with tempfile.TemporaryDirectory() as td:
    with open(os.path.join(td, ".rabbit-scope-override"), "w") as f:
        f.write("permanent")
    r = check_marker_alert(".rabbit-scope-override", "session", ALERT, repo_root=td)
    if r == {"type": "ok"}:
        ok("t4: content mismatch returns ok_result")
    else:
        fail(f"t4: expected ok, got {r!r}")

# t5: marker is a directory (not a regular file) -> treated as absent
with tempfile.TemporaryDirectory() as td:
    os.makedirs(os.path.join(td, ".rabbit-scope-override"))
    r = check_marker_alert(".rabbit-scope-override", None, ALERT, repo_root=td)
    if r == {"type": "ok"}:
        ok("t5: directory at marker path treated as absent")
    else:
        fail(f"t5: expected ok, got {r!r}")

if FAIL:
    print("test-runtime-check-marker-alert: FAIL", file=sys.stderr)
    sys.exit(1)
print("test-runtime-check-marker-alert: all checks passed.")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 .claude/features/contract/test/test-runtime-check-marker-alert.py`
Expected: FAIL with `ImportError: cannot import name 'check_marker_alert'`

- [ ] **Step 3: Implement `check_marker_alert`**

Add `import os` at the top of `.claude/features/contract/lib/runtime.py` (after the module docstring), then append the function:

```python
def check_marker_alert(path: str, content, alert: dict, *, repo_root: str) -> dict:
    """If the marker at `path` (repo-root-relative) exists, return a print
    result built from `alert` ({text, icon, color}). If `content` is not
    None, the marker file must also contain exactly that string; otherwise
    treat as absent.
    """
    full = os.path.join(repo_root, path)
    if not os.path.isfile(full):
        return ok_result()
    if content is not None:
        try:
            with open(full) as f:
                if f.read() != content:
                    return ok_result()
        except OSError:
            return ok_result()
    return print_result(alert["text"], alert["icon"], alert["color"])
```

- [ ] **Step 4: Wire the new test into `run.py`**

Append to `.claude/features/contract/test/run.py` (before the `print("ALL TESTS PASSED")` line):

```python
run_test("test-runtime-check-marker-alert.py")
```

- [ ] **Step 5: Run test to verify it passes**

Run: `python3 .claude/features/contract/test/test-runtime-check-marker-alert.py`
Expected: `test-runtime-check-marker-alert: all checks passed.`

- [ ] **Step 6: Run the full contract test suite**

Run: `python3 .claude/features/contract/test/run.py`
Expected: `ALL TESTS PASSED`

- [ ] **Step 7: Commit**

```bash
git add .claude/features/contract/lib/runtime.py \
        .claude/features/contract/test/test-runtime-check-marker-alert.py \
        .claude/features/contract/test/run.py
git commit -m "feat(contract): check_marker_alert — marker-present alert

Returns print_result built from alert dict when the marker file
exists at the repo-root-relative path. Optional content filter
suppresses the alert if file content does not match exactly.
Missing file (or directory at path) returns ok_result.

Part of CONTRACT-BACKLOG-36 Plan B.2."
```

---

## Task 3: `check_marker_consume_alert(path, alert)`

**Files:**
- Modify: `.claude/features/contract/lib/runtime.py`
- Create: `.claude/features/contract/test/test-runtime-check-marker-consume-alert.py`
- Modify: `.claude/features/contract/test/run.py`

**Behavior:** If the marker file exists, delete it and return a print result built from `alert`. If `alert.text` contains the literal substring `{marker-content}`, substitute the (stripped) file content into it BEFORE deletion. If the marker is missing, return `ok_result()`.

- [ ] **Step 1: Write the failing test**

Create `.claude/features/contract/test/test-runtime-check-marker-consume-alert.py`:

```python
#!/usr/bin/env python3
"""test-runtime-check-marker-consume-alert.py — exercises
check_marker_consume_alert: deletes the marker after emitting a print
result; supports {marker-content} interpolation into alert text.
"""

import os
import sys
import tempfile

FEATURE_DIR = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, FEATURE_DIR)

from lib.runtime import check_marker_consume_alert  # noqa: E402

FAIL = 0


def fail(msg):
    global FAIL
    print(f"FAIL: {msg}", file=sys.stderr)
    FAIL = 1


def ok(msg):
    print(f"PASS: {msg}")


PLAIN = {"text": "SCOPE BYPASSED", "icon": "unlock", "color": "red"}
INTERPOLATED = {"text": "Skills updated: {marker-content}",
                "icon": "sparkle", "color": "green"}

# t1: missing marker -> ok_result, no error
with tempfile.TemporaryDirectory() as td:
    r = check_marker_consume_alert(".rabbit-skills-updated", PLAIN, repo_root=td)
    if r == {"type": "ok"}:
        ok("t1: missing marker returns ok_result")
    else:
        fail(f"t1: expected ok, got {r!r}")

# t2: present marker -> print_result emitted AND marker is deleted
with tempfile.TemporaryDirectory() as td:
    p = os.path.join(td, ".rabbit-scope-override-used")
    with open(p, "w") as f:
        f.write("anything")
    r = check_marker_consume_alert(".rabbit-scope-override-used", PLAIN, repo_root=td)
    if r != {"type": "print", "text": "SCOPE BYPASSED",
             "icon": "unlock", "color": "red"}:
        fail(f"t2: unexpected result {r!r}")
    elif os.path.exists(p):
        fail("t2: marker still present after consume")
    else:
        ok("t2: present marker emits print and is consumed")

# t3: {marker-content} substitution uses stripped file content
with tempfile.TemporaryDirectory() as td:
    p = os.path.join(td, ".rabbit-skills-updated")
    with open(p, "w") as f:
        f.write("rabbit-foo, rabbit-bar\n")
    r = check_marker_consume_alert(".rabbit-skills-updated", INTERPOLATED, repo_root=td)
    if r.get("text") == "Skills updated: rabbit-foo, rabbit-bar":
        ok("t3: {marker-content} substitution uses stripped file content")
    else:
        fail(f"t3: unexpected text {r!r}")

# t4: alert dict is not mutated (caller reuses across invocations)
with tempfile.TemporaryDirectory() as td:
    p = os.path.join(td, ".rabbit-skills-updated")
    with open(p, "w") as f:
        f.write("payload\n")
    alert_copy = dict(INTERPOLATED)
    check_marker_consume_alert(".rabbit-skills-updated", INTERPOLATED, repo_root=td)
    if INTERPOLATED == alert_copy:
        ok("t4: alert dict not mutated by call")
    else:
        fail(f"t4: alert dict mutated; now {INTERPOLATED!r}")

if FAIL:
    print("test-runtime-check-marker-consume-alert: FAIL", file=sys.stderr)
    sys.exit(1)
print("test-runtime-check-marker-consume-alert: all checks passed.")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 .claude/features/contract/test/test-runtime-check-marker-consume-alert.py`
Expected: FAIL with `ImportError: cannot import name 'check_marker_consume_alert'`

- [ ] **Step 3: Implement `check_marker_consume_alert`**

Append to `.claude/features/contract/lib/runtime.py`:

```python
def check_marker_consume_alert(path: str, alert: dict, *, repo_root: str) -> dict:
    """If the marker at `path` (repo-root-relative) exists, delete it and
    return a print result built from `alert`. If `alert.text` contains the
    literal substring `{marker-content}`, the (stripped) marker contents
    are substituted in before deletion. Missing marker returns ok_result.
    Does not mutate the caller's `alert` dict.
    """
    full = os.path.join(repo_root, path)
    if not os.path.isfile(full):
        return ok_result()
    text = alert["text"]
    if "{marker-content}" in text:
        try:
            with open(full) as f:
                marker_content = f.read().strip()
        except OSError:
            marker_content = ""
        text = text.replace("{marker-content}", marker_content)
    try:
        os.remove(full)
    except OSError:
        pass
    return print_result(text, alert["icon"], alert["color"])
```

- [ ] **Step 4: Wire the new test into `run.py`**

Append to `.claude/features/contract/test/run.py` (before the final print line):

```python
run_test("test-runtime-check-marker-consume-alert.py")
```

- [ ] **Step 5: Run test to verify it passes**

Run: `python3 .claude/features/contract/test/test-runtime-check-marker-consume-alert.py`
Expected: `test-runtime-check-marker-consume-alert: all checks passed.`

- [ ] **Step 6: Run the full contract test suite**

Run: `python3 .claude/features/contract/test/run.py`
Expected: `ALL TESTS PASSED`

- [ ] **Step 7: Commit**

```bash
git add .claude/features/contract/lib/runtime.py \
        .claude/features/contract/test/test-runtime-check-marker-consume-alert.py \
        .claude/features/contract/test/run.py
git commit -m "feat(contract): check_marker_consume_alert — one-time alert

Deletes the marker file after emitting a print result. Supports
{marker-content} interpolation: if alert.text contains that
literal substring, the stripped marker contents replace it
before deletion. Missing marker returns ok_result.

Part of CONTRACT-BACKLOG-36 Plan B.2."
```

---

## Task 4: `check_counter_threshold_refresh(counter, env_var, source)`

**Files:**
- Modify: `.claude/features/contract/lib/runtime.py`
- Create: `.claude/features/contract/test/test-runtime-check-counter-threshold-refresh.py`
- Modify: `.claude/features/contract/test/run.py`

**Behavior:** Read integer counter from file at `counter` (repo-root-relative). Read threshold from `os.environ[env_var]` (default `20` if env var missing or non-int). Increment the counter file each invocation (creating it if missing). If the new value is < threshold, return `ok_result()`. If the new value is >= threshold, reset counter file to `0` and return `inject_result` whose content is the result of reading the file at `source` (repo-root-relative path; may also be a directory, in which case concat every `*.md` in alphabetical order). Producer-free — this API does NOT call `lib.producers`; it does its own file reads.

- [ ] **Step 1: Write the failing test**

Create `.claude/features/contract/test/test-runtime-check-counter-threshold-refresh.py`:

```python
#!/usr/bin/env python3
"""test-runtime-check-counter-threshold-refresh.py — exercises
check_counter_threshold_refresh: increments a counter file each
invocation; on threshold, resets counter to 0 and returns inject_result
with the contents of `source` (file or directory of *.md files
concatenated alphabetically).
"""

import os
import sys
import tempfile

FEATURE_DIR = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, FEATURE_DIR)

from lib.runtime import check_counter_threshold_refresh  # noqa: E402

FAIL = 0


def fail(msg):
    global FAIL
    print(f"FAIL: {msg}", file=sys.stderr)
    FAIL = 1


def ok(msg):
    print(f"PASS: {msg}")


def read_counter(td):
    p = os.path.join(td, ".rabbit-prompt-counter")
    if not os.path.isfile(p):
        return None
    return int(open(p).read().strip())


# t1: counter file missing -> created at 1, returns ok_result (below threshold)
with tempfile.TemporaryDirectory() as td:
    os.environ["RABBIT_TEST_THRESH"] = "5"
    src = os.path.join(td, "policy.md")
    with open(src, "w") as f:
        f.write("POLICY\n")
    r = check_counter_threshold_refresh(
        ".rabbit-prompt-counter", "RABBIT_TEST_THRESH", "policy.md", repo_root=td
    )
    if r != {"type": "ok"}:
        fail(f"t1: expected ok, got {r!r}")
    elif read_counter(td) != 1:
        fail(f"t1: counter not created at 1; got {read_counter(td)!r}")
    else:
        ok("t1: missing counter created at 1, returns ok")
    del os.environ["RABBIT_TEST_THRESH"]

# t2: counter below threshold -> incremented, ok
with tempfile.TemporaryDirectory() as td:
    os.environ["RABBIT_TEST_THRESH"] = "5"
    with open(os.path.join(td, ".rabbit-prompt-counter"), "w") as f:
        f.write("2")
    with open(os.path.join(td, "policy.md"), "w") as f:
        f.write("POLICY\n")
    r = check_counter_threshold_refresh(
        ".rabbit-prompt-counter", "RABBIT_TEST_THRESH", "policy.md", repo_root=td
    )
    if r == {"type": "ok"} and read_counter(td) == 3:
        ok("t2: below threshold: counter incremented, ok returned")
    else:
        fail(f"t2: result={r!r}, counter={read_counter(td)!r}")
    del os.environ["RABBIT_TEST_THRESH"]

# t3: counter reaches threshold -> reset to 0, returns inject_result with source content
with tempfile.TemporaryDirectory() as td:
    os.environ["RABBIT_TEST_THRESH"] = "5"
    with open(os.path.join(td, ".rabbit-prompt-counter"), "w") as f:
        f.write("4")
    with open(os.path.join(td, "policy.md"), "w") as f:
        f.write("POLICY-TEXT\n")
    r = check_counter_threshold_refresh(
        ".rabbit-prompt-counter", "RABBIT_TEST_THRESH", "policy.md", repo_root=td
    )
    if r == {"type": "inject", "content": "POLICY-TEXT\n"} and read_counter(td) == 0:
        ok("t3: at threshold (4+1=5): reset to 0 and inject_result returned")
    else:
        fail(f"t3: result={r!r}, counter={read_counter(td)!r}")
    del os.environ["RABBIT_TEST_THRESH"]

# t4: source is a directory -> concat every *.md in alphabetical order
with tempfile.TemporaryDirectory() as td:
    os.environ["RABBIT_TEST_THRESH"] = "1"
    pol = os.path.join(td, "policy")
    os.makedirs(pol)
    with open(os.path.join(pol, "b.md"), "w") as f:
        f.write("BBB\n")
    with open(os.path.join(pol, "a.md"), "w") as f:
        f.write("AAA\n")
    with open(os.path.join(pol, "ignored.txt"), "w") as f:
        f.write("nope\n")
    # counter missing -> increments to 1, hits threshold 1 -> refresh
    r = check_counter_threshold_refresh(
        ".rabbit-prompt-counter", "RABBIT_TEST_THRESH", "policy", repo_root=td
    )
    if r == {"type": "inject", "content": "AAA\nBBB\n"}:
        ok("t4: directory source: *.md files concatenated alphabetically")
    else:
        fail(f"t4: unexpected: {r!r}")
    del os.environ["RABBIT_TEST_THRESH"]

# t5: missing env var -> default threshold 20
with tempfile.TemporaryDirectory() as td:
    if "RABBIT_TEST_THRESH" in os.environ:
        del os.environ["RABBIT_TEST_THRESH"]
    with open(os.path.join(td, ".rabbit-prompt-counter"), "w") as f:
        f.write("18")
    with open(os.path.join(td, "policy.md"), "w") as f:
        f.write("P\n")
    r = check_counter_threshold_refresh(
        ".rabbit-prompt-counter", "RABBIT_TEST_THRESH", "policy.md", repo_root=td
    )
    if r == {"type": "ok"} and read_counter(td) == 19:
        ok("t5: missing env var: default threshold 20 honored (18 -> 19, no refresh)")
    else:
        fail(f"t5: result={r!r}, counter={read_counter(td)!r}")

# t6: non-int env var -> falls back to default 20
with tempfile.TemporaryDirectory() as td:
    os.environ["RABBIT_TEST_THRESH"] = "not-an-int"
    with open(os.path.join(td, ".rabbit-prompt-counter"), "w") as f:
        f.write("18")
    with open(os.path.join(td, "policy.md"), "w") as f:
        f.write("P\n")
    r = check_counter_threshold_refresh(
        ".rabbit-prompt-counter", "RABBIT_TEST_THRESH", "policy.md", repo_root=td
    )
    if r == {"type": "ok"} and read_counter(td) == 19:
        ok("t6: non-int env var falls back to default 20")
    else:
        fail(f"t6: result={r!r}, counter={read_counter(td)!r}")
    del os.environ["RABBIT_TEST_THRESH"]

# t7: missing source file -> error_result
with tempfile.TemporaryDirectory() as td:
    os.environ["RABBIT_TEST_THRESH"] = "1"
    r = check_counter_threshold_refresh(
        ".rabbit-prompt-counter", "RABBIT_TEST_THRESH", "missing.md", repo_root=td
    )
    if r.get("type") == "error":
        ok("t7: missing source returns error_result")
    else:
        fail(f"t7: expected error, got {r!r}")
    del os.environ["RABBIT_TEST_THRESH"]

if FAIL:
    print("test-runtime-check-counter-threshold-refresh: FAIL", file=sys.stderr)
    sys.exit(1)
print("test-runtime-check-counter-threshold-refresh: all checks passed.")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 .claude/features/contract/test/test-runtime-check-counter-threshold-refresh.py`
Expected: FAIL with `ImportError: cannot import name 'check_counter_threshold_refresh'`

- [ ] **Step 3: Implement `check_counter_threshold_refresh`**

Append to `.claude/features/contract/lib/runtime.py`:

```python
DEFAULT_REFRESH_THRESHOLD = 20


def _read_threshold(env_var: str) -> int:
    raw = os.environ.get(env_var)
    if raw is None:
        return DEFAULT_REFRESH_THRESHOLD
    try:
        return int(raw)
    except ValueError:
        return DEFAULT_REFRESH_THRESHOLD


def _read_source(full_source: str) -> str:
    """Read source content. If full_source is a directory, concat every
    *.md file inside it in alphabetical filename order. Raises
    FileNotFoundError or OSError if the path does not exist.
    """
    if os.path.isdir(full_source):
        parts = []
        for name in sorted(os.listdir(full_source)):
            if name.endswith(".md"):
                with open(os.path.join(full_source, name)) as f:
                    parts.append(f.read())
        return "".join(parts)
    with open(full_source) as f:
        return f.read()


def check_counter_threshold_refresh(counter: str, env_var: str, source: str,
                                    *, repo_root: str) -> dict:
    """Increment counter file each invocation; on threshold, reset counter
    to 0 and return inject_result whose content is read from `source`
    (repo-root-relative file, OR a directory whose *.md files are
    concatenated alphabetically). Below threshold returns ok_result.
    Missing or unreadable source returns error_result.
    """
    counter_full = os.path.join(repo_root, counter)
    threshold = _read_threshold(env_var)

    current = 0
    if os.path.isfile(counter_full):
        try:
            current = int(open(counter_full).read().strip())
        except (OSError, ValueError):
            current = 0
    new_val = current + 1

    if new_val < threshold:
        parent = os.path.dirname(counter_full)
        if parent:
            os.makedirs(parent, exist_ok=True)
        with open(counter_full, "w") as f:
            f.write(str(new_val))
        return ok_result()

    # at or above threshold: reset and inject
    source_full = os.path.join(repo_root, source)
    try:
        content = _read_source(source_full)
    except (FileNotFoundError, OSError) as e:
        return error_result(f"counter refresh source unreadable: {e}")
    with open(counter_full, "w") as f:
        f.write("0")
    return inject_result(content)
```

- [ ] **Step 4: Wire the new test into `run.py`**

Append to `.claude/features/contract/test/run.py` (before the final print line):

```python
run_test("test-runtime-check-counter-threshold-refresh.py")
```

- [ ] **Step 5: Run test to verify it passes**

Run: `python3 .claude/features/contract/test/test-runtime-check-counter-threshold-refresh.py`
Expected: `test-runtime-check-counter-threshold-refresh: all checks passed.`

- [ ] **Step 6: Run the full contract test suite**

Run: `python3 .claude/features/contract/test/run.py`
Expected: `ALL TESTS PASSED`

- [ ] **Step 7: Commit**

```bash
git add .claude/features/contract/lib/runtime.py \
        .claude/features/contract/test/test-runtime-check-counter-threshold-refresh.py \
        .claude/features/contract/test/run.py
git commit -m "feat(contract): check_counter_threshold_refresh — periodic refresh

Increments a counter file each invocation; on reaching the
threshold (env var, default 20) resets to 0 and returns
inject_result with the contents of source. Source may be a
single file or a directory of *.md files (concatenated in
alphabetical order). Missing source returns error_result.

Part of CONTRACT-BACKLOG-36 Plan B.2."
```

---

## Task 5: `welcome_with_policy(policy_source)`

**Files:**
- Modify: `.claude/features/contract/lib/runtime.py`
- Create: `.claude/features/contract/test/test-runtime-welcome-with-policy.py`
- Modify: `.claude/features/contract/test/run.py`

**Behavior:** Returns a 2-element list `[print_result, inject_result]`. The print is a fixed welcome banner (`text="Rabbit workflow ready"`, `icon="rabbit"`, `color="green"`). The inject contains the policy text read from `policy_source` (repo-root-relative path; same single-file-or-dir-of-*.md semantics as `check_counter_threshold_refresh` — reuse `_read_source`). Returns `error_result(...)` (single dict, not list) if `policy_source` is unreadable.

- [ ] **Step 1: Write the failing test**

Create `.claude/features/contract/test/test-runtime-welcome-with-policy.py`:

```python
#!/usr/bin/env python3
"""test-runtime-welcome-with-policy.py — exercises welcome_with_policy:
returns [print_result (welcome banner), inject_result (policy text)] on
success; single error_result if policy_source is unreadable.
"""

import os
import sys
import tempfile

FEATURE_DIR = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, FEATURE_DIR)

from lib.runtime import welcome_with_policy  # noqa: E402

FAIL = 0


def fail(msg):
    global FAIL
    print(f"FAIL: {msg}", file=sys.stderr)
    FAIL = 1


def ok(msg):
    print(f"PASS: {msg}")


# t1: file source -> [print, inject]
with tempfile.TemporaryDirectory() as td:
    with open(os.path.join(td, "policy.md"), "w") as f:
        f.write("POLICY-BODY\n")
    r = welcome_with_policy("policy.md", repo_root=td)
    if not isinstance(r, list) or len(r) != 2:
        fail(f"t1: expected 2-element list, got {r!r}")
    elif r[0]["type"] != "print" or r[1]["type"] != "inject":
        fail(f"t1: expected [print, inject], got types {[x.get('type') for x in r]}")
    elif r[1]["content"] != "POLICY-BODY\n":
        fail(f"t1: inject content mismatch: {r[1]!r}")
    else:
        ok("t1: file source returns [print_banner, inject_policy]")

# t2: directory source -> concat *.md in alphabetical order
with tempfile.TemporaryDirectory() as td:
    pol = os.path.join(td, "policy")
    os.makedirs(pol)
    with open(os.path.join(pol, "2-coding.md"), "w") as f:
        f.write("CODING\n")
    with open(os.path.join(pol, "1-philosophy.md"), "w") as f:
        f.write("PHILOSOPHY\n")
    r = welcome_with_policy("policy", repo_root=td)
    if r[1]["content"] == "PHILOSOPHY\nCODING\n":
        ok("t2: directory source concatenates *.md alphabetically")
    else:
        fail(f"t2: unexpected inject content: {r[1]!r}")

# t3: welcome banner has fixed text/icon/color
with tempfile.TemporaryDirectory() as td:
    with open(os.path.join(td, "p.md"), "w") as f:
        f.write("x")
    r = welcome_with_policy("p.md", repo_root=td)
    p = r[0]
    if (p["text"] == "Rabbit workflow ready"
            and p["icon"] == "rabbit"
            and p["color"] == "green"):
        ok("t3: welcome banner has fixed text/icon/color")
    else:
        fail(f"t3: unexpected banner: {p!r}")

# t4: missing source -> single error_result (not a list)
with tempfile.TemporaryDirectory() as td:
    r = welcome_with_policy("missing.md", repo_root=td)
    if isinstance(r, dict) and r.get("type") == "error":
        ok("t4: missing source returns single error_result")
    else:
        fail(f"t4: expected error dict, got {r!r}")

if FAIL:
    print("test-runtime-welcome-with-policy: FAIL", file=sys.stderr)
    sys.exit(1)
print("test-runtime-welcome-with-policy: all checks passed.")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 .claude/features/contract/test/test-runtime-welcome-with-policy.py`
Expected: FAIL with `ImportError: cannot import name 'welcome_with_policy'`

- [ ] **Step 3: Implement `welcome_with_policy`**

Append to `.claude/features/contract/lib/runtime.py`:

```python
WELCOME_BANNER = {"text": "Rabbit workflow ready", "icon": "rabbit", "color": "green"}


def welcome_with_policy(policy_source: str, *, repo_root: str):
    """Return [welcome banner print_result, policy inject_result].

    policy_source is repo-root-relative; may be a single file or a
    directory whose *.md files are concatenated alphabetically (same
    semantics as check_counter_threshold_refresh source).

    On unreadable source returns a single error_result (NOT a list).
    """
    full = os.path.join(repo_root, policy_source)
    try:
        content = _read_source(full)
    except (FileNotFoundError, OSError) as e:
        return error_result(f"welcome policy source unreadable: {e}")
    return [
        print_result(WELCOME_BANNER["text"],
                     WELCOME_BANNER["icon"],
                     WELCOME_BANNER["color"]),
        inject_result(content),
    ]
```

- [ ] **Step 4: Wire the new test into `run.py`**

Append to `.claude/features/contract/test/run.py` (before the final print line):

```python
run_test("test-runtime-welcome-with-policy.py")
```

- [ ] **Step 5: Run test to verify it passes**

Run: `python3 .claude/features/contract/test/test-runtime-welcome-with-policy.py`
Expected: `test-runtime-welcome-with-policy: all checks passed.`

- [ ] **Step 6: Run the full contract test suite**

Run: `python3 .claude/features/contract/test/run.py`
Expected: `ALL TESTS PASSED`

- [ ] **Step 7: Commit**

```bash
git add .claude/features/contract/lib/runtime.py \
        .claude/features/contract/test/test-runtime-welcome-with-policy.py \
        .claude/features/contract/test/run.py
git commit -m "feat(contract): welcome_with_policy — SessionStart banner+policy

Returns [welcome banner print_result, policy inject_result] on
success. policy_source is a file or directory of *.md files
(concatenated alphabetically). Missing source returns a single
error_result (not a list).

Part of CONTRACT-BACKLOG-36 Plan B.2."
```

---

## Task 6: `check_drift_regenerate(target, producer, alert)`

**Files:**
- Modify: `.claude/features/contract/lib/runtime.py`
- Create: `.claude/features/contract/test/test-runtime-check-drift-regenerate.py`
- Modify: `.claude/features/contract/test/run.py`

**Behavior:** Run the named content producer via `lib.producers.call_producer(producer, args={}, feature_dir, repo_root)`. Compare its output to the contents of `target` (repo-root-relative). If equal, return `ok_result()`. If different (or target missing), write the producer output to target and return `[print_result, inject_result]`: the print is built from `alert` ({text, icon, color}); the inject contains the regenerated content.

The producer is invoked with empty args (`{}`); the producer name alone is enough — for `generate-claude-md` this means the producer must already have any required args declared elsewhere, but for this API the runtime entry only carries `target`, `producer`, and `alert`. (If a future producer needs args, the schema would extend; defer until needed.)

- [ ] **Step 1: Write the failing test**

Create `.claude/features/contract/test/test-runtime-check-drift-regenerate.py`:

```python
#!/usr/bin/env python3
"""test-runtime-check-drift-regenerate.py — exercises
check_drift_regenerate: invokes a content producer, compares to target on
disk, regenerates + emits print+inject on drift, returns ok on match.

lib.producers is stubbed via sys.modules BEFORE importing lib.runtime so
the lazy import inside check_drift_regenerate resolves to the stub.
"""

import os
import sys
import tempfile
import types

FEATURE_DIR = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, FEATURE_DIR)

_producers_stub = types.ModuleType("lib.producers")
_producers_stub.call_producer = lambda name, args, feature_dir, repo_root: (
    "PRODUCED-BY-" + name + "\n"
)
sys.modules["lib.producers"] = _producers_stub

from lib.runtime import check_drift_regenerate  # noqa: E402

FAIL = 0


def fail(msg):
    global FAIL
    print(f"FAIL: {msg}", file=sys.stderr)
    FAIL = 1


def ok(msg):
    print(f"PASS: {msg}")


ALERT = {"text": "CLAUDE.md regenerated", "icon": "warn", "color": "red"}

# t1: target missing -> regenerate, return [print, inject]
with tempfile.TemporaryDirectory() as td:
    feat = os.path.join(td, "feature")
    root = os.path.join(td, "repo")
    os.makedirs(feat)
    os.makedirs(root)
    r = check_drift_regenerate("CLAUDE.md", "generate-claude-md", ALERT,
                                feature_dir=feat, repo_root=root)
    if (isinstance(r, list) and len(r) == 2
            and r[0]["type"] == "print" and r[1]["type"] == "inject"):
        target = os.path.join(root, "CLAUDE.md")
        if open(target).read() == "PRODUCED-BY-generate-claude-md\n":
            ok("t1: missing target regenerated + [print, inject] returned")
        else:
            fail(f"t1: target content wrong: {open(target).read()!r}")
    else:
        fail(f"t1: expected [print, inject] list, got {r!r}")

# t2: target matches producer output -> ok_result, no write
with tempfile.TemporaryDirectory() as td:
    feat = os.path.join(td, "feature")
    root = os.path.join(td, "repo")
    os.makedirs(feat)
    os.makedirs(root)
    target = os.path.join(root, "CLAUDE.md")
    with open(target, "w") as f:
        f.write("PRODUCED-BY-generate-claude-md\n")
    mtime_before = os.stat(target).st_mtime_ns
    r = check_drift_regenerate("CLAUDE.md", "generate-claude-md", ALERT,
                                feature_dir=feat, repo_root=root)
    mtime_after = os.stat(target).st_mtime_ns
    if r == {"type": "ok"} and mtime_before == mtime_after:
        ok("t2: match returns ok_result without rewriting target")
    else:
        fail(f"t2: result={r!r}, mtime_changed={mtime_before != mtime_after}")

# t3: target drifted -> regenerate, return [print, inject], target updated
with tempfile.TemporaryDirectory() as td:
    feat = os.path.join(td, "feature")
    root = os.path.join(td, "repo")
    os.makedirs(feat)
    os.makedirs(root)
    target = os.path.join(root, "CLAUDE.md")
    with open(target, "w") as f:
        f.write("STALE\n")
    r = check_drift_regenerate("CLAUDE.md", "generate-claude-md", ALERT,
                                feature_dir=feat, repo_root=root)
    if (isinstance(r, list) and r[0]["text"] == "CLAUDE.md regenerated"
            and open(target).read() == "PRODUCED-BY-generate-claude-md\n"):
        ok("t3: drift detected: target overwritten + alert returned")
    else:
        fail(f"t3: unexpected: result={r!r}, target={open(target).read()!r}")

# t4: print result uses alert text/icon/color verbatim
with tempfile.TemporaryDirectory() as td:
    feat = os.path.join(td, "feature")
    root = os.path.join(td, "repo")
    os.makedirs(feat)
    os.makedirs(root)
    r = check_drift_regenerate("CLAUDE.md", "generate-claude-md", ALERT,
                                feature_dir=feat, repo_root=root)
    p = r[0]
    if (p["text"] == ALERT["text"] and p["icon"] == ALERT["icon"]
            and p["color"] == ALERT["color"]):
        ok("t4: print result uses alert text/icon/color verbatim")
    else:
        fail(f"t4: print result {p!r} != alert {ALERT!r}")

# t5: producer failure -> error_result
def _boom(name, args, feature_dir, repo_root):
    raise RuntimeError("producer exploded")


_producers_stub.call_producer = _boom
with tempfile.TemporaryDirectory() as td:
    feat = os.path.join(td, "feature")
    root = os.path.join(td, "repo")
    os.makedirs(feat)
    os.makedirs(root)
    r = check_drift_regenerate("CLAUDE.md", "generate-claude-md", ALERT,
                                feature_dir=feat, repo_root=root)
    if isinstance(r, dict) and r.get("type") == "error":
        ok("t5: producer exception caught and returned as error_result")
    else:
        fail(f"t5: expected error dict, got {r!r}")

# Restore stub for any later code (none here, but defensive).
_producers_stub.call_producer = lambda name, args, feature_dir, repo_root: (
    "PRODUCED-BY-" + name + "\n"
)

if FAIL:
    print("test-runtime-check-drift-regenerate: FAIL", file=sys.stderr)
    sys.exit(1)
print("test-runtime-check-drift-regenerate: all checks passed.")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 .claude/features/contract/test/test-runtime-check-drift-regenerate.py`
Expected: FAIL with `ImportError: cannot import name 'check_drift_regenerate'`

- [ ] **Step 3: Implement `check_drift_regenerate`**

Append to `.claude/features/contract/lib/runtime.py`:

```python
def check_drift_regenerate(target: str, producer: str, alert: dict,
                            *, feature_dir: str, repo_root: str):
    """Run the named content producer and compare to target on disk.

    On match: return ok_result(). On drift (or missing target): write
    producer output to target and return [print_result, inject_result].
    On producer exception or import failure: return error_result(...).

    Lazy-imports lib.producers so this module loads even before the
    producers sibling lands.
    """
    try:
        from lib import producers  # noqa: PLC0415
    except ImportError as e:
        return error_result(f"lib.producers unavailable: {e}")
    try:
        content = producers.call_producer(producer, {},
                                          feature_dir=feature_dir,
                                          repo_root=repo_root)
    except Exception as e:  # noqa: BLE001 - dispatcher catches any producer fault
        return error_result(f"producer {producer!r} failed: {e}")

    full_target = os.path.join(repo_root, target)
    current = ""
    if os.path.isfile(full_target):
        try:
            with open(full_target) as f:
                current = f.read()
        except OSError as e:
            return error_result(f"target unreadable: {e}")
    if content == current:
        return ok_result()

    parent = os.path.dirname(full_target)
    if parent:
        os.makedirs(parent, exist_ok=True)
    with open(full_target, "w") as f:
        f.write(content)
    return [
        print_result(alert["text"], alert["icon"], alert["color"]),
        inject_result(content),
    ]
```

- [ ] **Step 4: Wire the new test into `run.py`**

Append to `.claude/features/contract/test/run.py` (before the final print line):

```python
run_test("test-runtime-check-drift-regenerate.py")
```

- [ ] **Step 5: Run test to verify it passes**

Run: `python3 .claude/features/contract/test/test-runtime-check-drift-regenerate.py`
Expected: `test-runtime-check-drift-regenerate: all checks passed.`

- [ ] **Step 6: Run the full contract test suite**

Run: `python3 .claude/features/contract/test/run.py`
Expected: `ALL TESTS PASSED`

- [ ] **Step 7: Commit**

```bash
git add .claude/features/contract/lib/runtime.py \
        .claude/features/contract/test/test-runtime-check-drift-regenerate.py \
        .claude/features/contract/test/run.py
git commit -m "feat(contract): check_drift_regenerate — content-producer drift

Invokes a content producer via lib.producers.call_producer,
compares output to the target file on disk. On match returns
ok_result; on drift (or missing target) writes producer output
to target and returns [print_result, inject_result]. Producer
exception or import failure returns error_result.

Late-imports lib.producers so this module loads before B.4 lands.

Part of CONTRACT-BACKLOG-36 Plan B.2."
```

---

## Task 7: `check_manifest_drift(alert)` (+ shared `_enumerate_features` helper)

**Files:**
- Modify: `.claude/features/contract/lib/runtime.py`
- Create: `.claude/features/contract/test/test-runtime-check-manifest-drift.py`
- Modify: `.claude/features/contract/test/run.py`

**Behavior:** Re-runs every feature's MANIFEST via the publish APIs. For each feature found at `.claude/features/<name>/feature.json`, read its `manifest` array (skip if empty/missing). For each entry, dispatch `lib.publish.<api>(**args, feature_dir=<that feature's dir>, repo_root=repo_root)`. Collect the names of any features whose publish calls produced a non-no-op CheckResult (i.e., a real write happened, not just "unchanged"). If at least one feature rebuilt, return a single `print_result` whose text comes from `alert['text']` with `{names}` substituted by comma-joined feature names. Otherwise return `ok_result()`. Publish errors are aggregated into the names list as well (so the alert surfaces them). Lazy-imports `lib.publish`.

The "non-no-op" signal: a CheckResult.messages line that does NOT contain the substring `"no-op"`. This matches the publish APIs' own convention (`"OK: ... unchanged (no-op)"` vs `"OK: ... published"`).

Also introduces a private helper `_enumerate_features(repo_root)` (used by Tasks 8 and 9 too).

- [ ] **Step 1: Write the failing test**

Create `.claude/features/contract/test/test-runtime-check-manifest-drift.py`:

```python
#!/usr/bin/env python3
"""test-runtime-check-manifest-drift.py — exercises check_manifest_drift:
walks every feature's MANIFEST, re-runs publish APIs, returns a print_result
naming any feature that produced a non-no-op result (i.e., real write).

lib.publish is the real module here (no stub) — this test builds a fake
repo tree with a publish_file MANIFEST entry and verifies drift detection.
"""

import json
import os
import sys
import tempfile

FEATURE_DIR = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, FEATURE_DIR)

from lib.runtime import check_manifest_drift  # noqa: E402

FAIL = 0


def fail(msg):
    global FAIL
    print(f"FAIL: {msg}", file=sys.stderr)
    FAIL = 1


def ok(msg):
    print(f"PASS: {msg}")


ALERT = {"text": "Surface drift detected — rebuilt: {names}",
         "icon": "rebuild", "color": "red"}


def make_feature(root, name, manifest, files):
    """Create .claude/features/<name>/feature.json with manifest +
    auxiliary source files (dict path -> content) under that feature dir."""
    fdir = os.path.join(root, ".claude", "features", name)
    os.makedirs(fdir, exist_ok=True)
    with open(os.path.join(fdir, "feature.json"), "w") as f:
        json.dump({"name": name, "version": "1.0.0", "owner": "x",
                   "manifest": manifest}, f)
    for relpath, content in files.items():
        full = os.path.join(fdir, relpath)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "w") as f:
            f.write(content)


# t1: no features -> ok_result
with tempfile.TemporaryDirectory() as td:
    os.makedirs(os.path.join(td, ".claude", "features"))
    r = check_manifest_drift(ALERT, repo_root=td)
    if r == {"type": "ok"}:
        ok("t1: no features returns ok_result")
    else:
        fail(f"t1: expected ok, got {r!r}")

# t2: feature with manifest but destination matches source -> ok_result
with tempfile.TemporaryDirectory() as td:
    make_feature(td, "feat-a",
                 [{"api": "publish_file",
                   "args": {"source": "src/foo.txt", "dest": "deployed/foo.txt"}}],
                 {"src/foo.txt": "hello\n"})
    # pre-deploy a matching file so the publish_file call is a no-op
    os.makedirs(os.path.join(td, "deployed"))
    with open(os.path.join(td, "deployed", "foo.txt"), "w") as f:
        f.write("hello\n")
    r = check_manifest_drift(ALERT, repo_root=td)
    if r == {"type": "ok"}:
        ok("t2: all features no-op returns ok_result")
    else:
        fail(f"t2: expected ok, got {r!r}")

# t3: feature with manifest and missing destination -> print_result names feature
with tempfile.TemporaryDirectory() as td:
    make_feature(td, "feat-a",
                 [{"api": "publish_file",
                   "args": {"source": "src/foo.txt", "dest": "deployed/foo.txt"}}],
                 {"src/foo.txt": "hello\n"})
    r = check_manifest_drift(ALERT, repo_root=td)
    if (r.get("type") == "print"
            and "feat-a" in r["text"]
            and r["text"].startswith("Surface drift detected — rebuilt:")):
        ok("t3: drift returns print_result with feature name substituted")
    else:
        fail(f"t3: unexpected: {r!r}")
    # verify destination was actually rebuilt
    if not os.path.isfile(os.path.join(td, "deployed", "foo.txt")):
        fail("t3: destination not rebuilt by re-publish")

# t4: multiple drifted features -> comma-joined alphabetical names
with tempfile.TemporaryDirectory() as td:
    make_feature(td, "b-feat",
                 [{"api": "publish_file",
                   "args": {"source": "src/a.txt", "dest": "out/b.txt"}}],
                 {"src/a.txt": "B\n"})
    make_feature(td, "a-feat",
                 [{"api": "publish_file",
                   "args": {"source": "src/a.txt", "dest": "out/a.txt"}}],
                 {"src/a.txt": "A\n"})
    r = check_manifest_drift(ALERT, repo_root=td)
    if r.get("type") == "print" and r["text"].endswith("a-feat, b-feat"):
        ok("t4: multiple drifted features comma-joined alphabetically")
    else:
        fail(f"t4: unexpected: {r!r}")

# t5: feature without manifest field -> skipped silently
with tempfile.TemporaryDirectory() as td:
    fdir = os.path.join(td, ".claude", "features", "no-manifest")
    os.makedirs(fdir)
    with open(os.path.join(fdir, "feature.json"), "w") as f:
        json.dump({"name": "no-manifest", "version": "1.0.0", "owner": "x"}, f)
    r = check_manifest_drift(ALERT, repo_root=td)
    if r == {"type": "ok"}:
        ok("t5: feature without manifest section skipped")
    else:
        fail(f"t5: expected ok, got {r!r}")

# t6: malformed feature.json -> that feature skipped (not crash)
with tempfile.TemporaryDirectory() as td:
    fdir = os.path.join(td, ".claude", "features", "broken")
    os.makedirs(fdir)
    with open(os.path.join(fdir, "feature.json"), "w") as f:
        f.write("{ not json")
    r = check_manifest_drift(ALERT, repo_root=td)
    if r == {"type": "ok"}:
        ok("t6: malformed feature.json skipped (no crash)")
    else:
        fail(f"t6: expected ok, got {r!r}")

if FAIL:
    print("test-runtime-check-manifest-drift: FAIL", file=sys.stderr)
    sys.exit(1)
print("test-runtime-check-manifest-drift: all checks passed.")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 .claude/features/contract/test/test-runtime-check-manifest-drift.py`
Expected: FAIL with `ImportError: cannot import name 'check_manifest_drift'`

- [ ] **Step 3: Implement helper + `check_manifest_drift`**

Add `import json` to the top of `.claude/features/contract/lib/runtime.py` (alongside `import os`), then append:

```python
def _enumerate_features(repo_root: str):
    """Yield (feature_name, feature_dir, feature_json_dict) for every
    feature directory under .claude/features/. Skips malformed
    feature.json files silently. Order: alphabetical by feature name.
    Shared helper for check_manifest_drift and iterate_configurables_*.
    """
    features_root = os.path.join(repo_root, ".claude", "features")
    if not os.path.isdir(features_root):
        return
    for name in sorted(os.listdir(features_root)):
        fdir = os.path.join(features_root, name)
        fj = os.path.join(fdir, "feature.json")
        if not os.path.isfile(fj):
            continue
        try:
            with open(fj) as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(data, dict):
            continue
        yield name, fdir, data


def check_manifest_drift(alert: dict, *, repo_root: str) -> dict:
    """Re-run every feature's MANIFEST via the publish APIs. Return a
    print_result naming features whose publish calls produced a non-no-op
    write (substring "no-op" absent from CheckResult.messages). On all-noop
    return ok_result. {names} in alert.text is substituted by the
    comma-joined feature names in alphabetical order.

    Lazy-imports lib.publish so this module can be loaded standalone.
    """
    try:
        from lib import publish  # noqa: PLC0415
    except ImportError as e:
        return error_result(f"lib.publish unavailable: {e}")

    drifted = []
    for name, fdir, data in _enumerate_features(repo_root):
        manifest = data.get("manifest")
        if not isinstance(manifest, list) or not manifest:
            continue
        for entry in manifest:
            api_name = entry.get("api")
            args = entry.get("args", {}) or {}
            fn = getattr(publish, api_name, None)
            if fn is None:
                drifted.append(name)
                break
            try:
                result = fn(**args, feature_dir=fdir, repo_root=repo_root)
            except Exception:  # noqa: BLE001
                drifted.append(name)
                break
            messages = getattr(result, "messages", []) or []
            if not any("no-op" in m for m in messages):
                drifted.append(name)
                break

    if not drifted:
        return ok_result()
    names = ", ".join(sorted(set(drifted)))
    return print_result(alert["text"].replace("{names}", names),
                        alert["icon"], alert["color"])
```

- [ ] **Step 4: Wire the new test into `run.py`**

Append to `.claude/features/contract/test/run.py` (before the final print line):

```python
run_test("test-runtime-check-manifest-drift.py")
```

- [ ] **Step 5: Run test to verify it passes**

Run: `python3 .claude/features/contract/test/test-runtime-check-manifest-drift.py`
Expected: `test-runtime-check-manifest-drift: all checks passed.`

- [ ] **Step 6: Run the full contract test suite**

Run: `python3 .claude/features/contract/test/run.py`
Expected: `ALL TESTS PASSED`

- [ ] **Step 7: Commit**

```bash
git add .claude/features/contract/lib/runtime.py \
        .claude/features/contract/test/test-runtime-check-manifest-drift.py \
        .claude/features/contract/test/run.py
git commit -m "feat(contract): check_manifest_drift — surface drift detector

Walks every .claude/features/*/feature.json (via the new shared
_enumerate_features helper), re-runs each feature's MANIFEST
entries via lib.publish, and returns a print_result naming
features whose publish produced a non-no-op write. {names} in
alert.text is substituted by comma-joined feature names
(alphabetical). Malformed feature.json is skipped silently.
Lazy-imports lib.publish.

Part of CONTRACT-BACKLOG-36 Plan B.2."
```

---

## Task 8: `iterate_configurables_alerts()`

**Files:**
- Modify: `.claude/features/contract/lib/runtime.py`
- Create: `.claude/features/contract/test/test-runtime-iterate-configurables-alerts.py`
- Modify: `.claude/features/contract/test/run.py`

**Behavior:** Walk every feature's CONFIGURATION array. For each configurable, evaluate its current value against `alert-on`. If they match, emit `alert-message` as a `print_result`. Returns a list (possibly empty) of print results in iteration order (alphabetical feature name × declaration order within each feature).

**Value resolution** depends on `storage.type`:

| storage.type | Current value semantic |
|---|---|
| `marker-file` | `"true"` if `<repo_root>/<path>` is **absent**, `"false"` if **present**. (Per the rabbit-cage `human-approval` configurable: `values.true => delete_marker`, `values.false => write_marker` — i.e., marker-present means the `"false"` mutation was applied.) |
| `json-key` | Stringified value at `storage.key` (dotted path) in `<repo_root>/<storage.file>`; absent or unreadable -> the configurable's `default`. Booleans stringify to `"true"`/`"false"`. |
| `json-array` / `json-array-templated` | These are action-style; no scalar value applies; skip these for the alert sweep |

Configurables without `alert-on` or without `alert-message` are skipped.

- [ ] **Step 1: Write the failing test**

Create `.claude/features/contract/test/test-runtime-iterate-configurables-alerts.py`:

```python
#!/usr/bin/env python3
"""test-runtime-iterate-configurables-alerts.py — exercises
iterate_configurables_alerts: walks every feature's CONFIGURATION array,
evaluates the current value against `alert-on`, returns a list of
print_results for matching configurables.
"""

import json
import os
import sys
import tempfile

FEATURE_DIR = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, FEATURE_DIR)

from lib.runtime import iterate_configurables_alerts  # noqa: E402

FAIL = 0


def fail(msg):
    global FAIL
    print(f"FAIL: {msg}", file=sys.stderr)
    FAIL = 1


def ok(msg):
    print(f"PASS: {msg}")


def make_feature(root, name, configuration):
    fdir = os.path.join(root, ".claude", "features", name)
    os.makedirs(fdir, exist_ok=True)
    with open(os.path.join(fdir, "feature.json"), "w") as f:
        json.dump({"name": name, "version": "1.0.0", "owner": "x",
                   "configuration": configuration}, f)


HA_CONF = {
    "id": "human-approval",
    "subcommand": "human-approval",
    "storage": {"type": "marker-file", "path": ".rabbit-human-approval-bypass"},
    "values": {"true": {"api": "delete_marker", "args": {}},
                "false": {"api": "write_marker", "args": {}}},
    "default": "true",
    "alert-on": "false",
    "alert-message": {"text": "HUMAN APPROVAL BYPASS ACTIVE",
                       "icon": "key", "color": "red"},
}

BP_CONF = {
    "id": "bypass-permissions",
    "subcommand": "bypass-permissions",
    "storage": {"type": "json-key",
                 "file": ".claude/settings.local.json",
                 "key": "permissions.defaultMode"},
    "values": {"true": {"api": "set_json_key", "args": {}},
                "false": {"api": "delete_json_key", "args": {}}},
    "default": "false",
    "alert-on": "true",
    "alert-message": {"text": "BYPASS-PERMISSIONS MODE ACTIVE",
                       "icon": "siren", "color": "red"},
}

# t1: no features -> empty list
with tempfile.TemporaryDirectory() as td:
    os.makedirs(os.path.join(td, ".claude", "features"))
    r = iterate_configurables_alerts(repo_root=td)
    if r == []:
        ok("t1: no features returns empty list")
    else:
        fail(f"t1: expected [], got {r!r}")

# t2: marker absent (value "true") with alert-on "false" -> no alert
with tempfile.TemporaryDirectory() as td:
    make_feature(td, "rabbit-cage", [HA_CONF])
    r = iterate_configurables_alerts(repo_root=td)
    if r == []:
        ok("t2: marker absent: value=true, alert-on=false: no alert")
    else:
        fail(f"t2: expected [], got {r!r}")

# t3: marker present (value "false") with alert-on "false" -> one alert
with tempfile.TemporaryDirectory() as td:
    make_feature(td, "rabbit-cage", [HA_CONF])
    with open(os.path.join(td, ".rabbit-human-approval-bypass"), "w") as f:
        f.write("session")
    r = iterate_configurables_alerts(repo_root=td)
    if (len(r) == 1 and r[0]["type"] == "print"
            and r[0]["text"] == "HUMAN APPROVAL BYPASS ACTIVE"
            and r[0]["color"] == "red"):
        ok("t3: marker present: value=false matches alert-on -> print emitted")
    else:
        fail(f"t3: unexpected {r!r}")

# t4: json-key absent -> uses default; default doesn't match alert-on -> no alert
with tempfile.TemporaryDirectory() as td:
    make_feature(td, "rabbit-cage", [BP_CONF])
    r = iterate_configurables_alerts(repo_root=td)
    if r == []:
        ok("t4: json-key absent: default 'false' != alert-on 'true' -> no alert")
    else:
        fail(f"t4: expected [], got {r!r}")

# t5: json-key value literally matches alert-on -> alert
with tempfile.TemporaryDirectory() as td:
    custom = {
        "id": "demo",
        "subcommand": "demo",
        "storage": {"type": "json-key", "file": "cfg.json", "key": "mode"},
        "values": {"on": {"api": "set_json_key", "args": {}},
                    "off": {"api": "delete_json_key", "args": {}}},
        "default": "off",
        "alert-on": "on",
        "alert-message": {"text": "DEMO MODE ACTIVE", "icon": "info", "color": "yellow"},
    }
    make_feature(td, "demo-feat", [custom])
    with open(os.path.join(td, "cfg.json"), "w") as f:
        json.dump({"mode": "on"}, f)
    r = iterate_configurables_alerts(repo_root=td)
    if len(r) == 1 and r[0]["text"] == "DEMO MODE ACTIVE":
        ok("t5: json-key literal match to alert-on emits alert")
    else:
        fail(f"t5: unexpected {r!r}")

# t6: json-key non-matching string -> no alert (strict literal match)
with tempfile.TemporaryDirectory() as td:
    make_feature(td, "rabbit-cage", [BP_CONF])
    sf = os.path.join(td, ".claude", "settings.local.json")
    os.makedirs(os.path.dirname(sf), exist_ok=True)
    with open(sf, "w") as f:
        json.dump({"permissions": {"defaultMode": "bypassPermissions"}}, f)
    r = iterate_configurables_alerts(repo_root=td)
    # alert-on is "true"; current resolved value is "bypassPermissions" (literal
    # string at that key). Strict equality: no alert.
    if r == []:
        ok("t6: non-matching json-key string: no alert (literal match)")
    else:
        fail(f"t6: expected [], got {r!r}")

# t7: configurable without alert-on is skipped
with tempfile.TemporaryDirectory() as td:
    no_alert = {
        "id": "x", "subcommand": "x",
        "storage": {"type": "marker-file", "path": ".x"},
        "values": {"true": {"api": "delete_marker", "args": {}},
                    "false": {"api": "write_marker", "args": {}}},
        "default": "true",
    }
    make_feature(td, "f", [no_alert])
    with open(os.path.join(td, ".x"), "w") as f:
        f.write("")
    r = iterate_configurables_alerts(repo_root=td)
    if r == []:
        ok("t7: configurable without alert-on skipped")
    else:
        fail(f"t7: expected [], got {r!r}")

# t8: action-style (json-array) configurable is skipped (no values to check)
with tempfile.TemporaryDirectory() as td:
    arr = {
        "id": "tools", "subcommand": "allowed-tools",
        "storage": {"type": "json-array", "file": "x.json", "key": "perms"},
        "actions": {"add": {"api": "append_json_array", "args": {}}},
    }
    make_feature(td, "f", [arr])
    r = iterate_configurables_alerts(repo_root=td)
    if r == []:
        ok("t8: json-array (action-style) configurable skipped")
    else:
        fail(f"t8: expected [], got {r!r}")

# t9: iteration order alphabetical by feature name
with tempfile.TemporaryDirectory() as td:
    make_feature(td, "z-feat", [
        {**HA_CONF, "id": "z-hap", "alert-message":
            {"text": "Z", "icon": "z", "color": "red"}}])
    make_feature(td, "a-feat", [
        {**HA_CONF, "id": "a-hap", "alert-message":
            {"text": "A", "icon": "a", "color": "red"}}])
    # marker shared path, so both fire
    with open(os.path.join(td, ".rabbit-human-approval-bypass"), "w") as f:
        f.write("session")
    r = iterate_configurables_alerts(repo_root=td)
    texts = [x["text"] for x in r]
    if texts == ["A", "Z"]:
        ok("t9: features iterated alphabetically (A before Z)")
    else:
        fail(f"t9: order unexpected: {texts}")

if FAIL:
    print("test-runtime-iterate-configurables-alerts: FAIL", file=sys.stderr)
    sys.exit(1)
print("test-runtime-iterate-configurables-alerts: all checks passed.")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 .claude/features/contract/test/test-runtime-iterate-configurables-alerts.py`
Expected: FAIL with `ImportError: cannot import name 'iterate_configurables_alerts'`

- [ ] **Step 3: Implement `iterate_configurables_alerts` + value-resolver helpers**

Append to `.claude/features/contract/lib/runtime.py`:

```python
def _resolve_marker_value(repo_root: str, storage: dict) -> str:
    """marker-file semantics: present -> 'false', absent -> 'true'.
    Matches the rabbit-cage human-approval CONFIGURATION example
    (values.true => delete_marker, values.false => write_marker).
    """
    path = storage.get("path")
    if not path:
        return ""
    return "false" if os.path.isfile(os.path.join(repo_root, path)) else "true"


def _resolve_json_key_value(repo_root: str, storage: dict, default: str) -> str:
    """Read storage.key (dotted path) from storage.file. Returns stringified
    value, or `default` if file is missing, unreadable, or key absent.
    Booleans stringify to 'true' / 'false'.
    """
    file_rel = storage.get("file")
    key_path = storage.get("key")
    if not file_rel or not key_path:
        return default
    full = os.path.join(repo_root, file_rel)
    if not os.path.isfile(full):
        return default
    try:
        with open(full) as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        return default
    cursor = data
    for part in key_path.split("."):
        if not isinstance(cursor, dict) or part not in cursor:
            return default
        cursor = cursor[part]
    if isinstance(cursor, bool):
        return "true" if cursor else "false"
    return str(cursor)


def _resolve_current_value(repo_root: str, configurable: dict):
    """Return the current string value of a configurable for alert-on
    comparison, or None if storage type is action-style (json-array*).
    """
    storage = configurable.get("storage") or {}
    stype = storage.get("type")
    default = configurable.get("default", "")
    if stype == "marker-file":
        return _resolve_marker_value(repo_root, storage)
    if stype == "json-key":
        return _resolve_json_key_value(repo_root, storage, default)
    # json-array / json-array-templated are action-style; no scalar value
    return None


def iterate_configurables_alerts(*, repo_root: str):
    """Walk every feature's CONFIGURATION array; for each configurable whose
    current value matches alert-on, return its alert-message as a
    print_result. Order: alphabetical by feature name × declaration order.
    Returns a list (possibly empty).
    """
    out = []
    for name, fdir, data in _enumerate_features(repo_root):
        configuration = data.get("configuration")
        if not isinstance(configuration, list):
            continue
        for cfg in configuration:
            alert_on = cfg.get("alert-on")
            alert_msg = cfg.get("alert-message")
            if alert_on is None or not isinstance(alert_msg, dict):
                continue
            current = _resolve_current_value(repo_root, cfg)
            if current is None:
                continue
            if current == alert_on:
                out.append(print_result(alert_msg["text"],
                                        alert_msg["icon"],
                                        alert_msg["color"]))
    return out
```

- [ ] **Step 4: Wire the new test into `run.py`**

Append to `.claude/features/contract/test/run.py` (before the final print line):

```python
run_test("test-runtime-iterate-configurables-alerts.py")
```

- [ ] **Step 5: Run test to verify it passes**

Run: `python3 .claude/features/contract/test/test-runtime-iterate-configurables-alerts.py`
Expected: `test-runtime-iterate-configurables-alerts: all checks passed.`

- [ ] **Step 6: Run the full contract test suite**

Run: `python3 .claude/features/contract/test/run.py`
Expected: `ALL TESTS PASSED`

- [ ] **Step 7: Commit**

```bash
git add .claude/features/contract/lib/runtime.py \
        .claude/features/contract/test/test-runtime-iterate-configurables-alerts.py \
        .claude/features/contract/test/run.py
git commit -m "feat(contract): iterate_configurables_alerts — Stop sweep

Walks every feature's CONFIGURATION array. For each configurable
whose current value matches alert-on, emits its alert-message
as a print_result. Value resolution: marker-file (present=>
'false', absent=>'true'), json-key (stringified read with
fallback to default). Action-style configurables (json-array*)
are skipped. Iteration order is alphabetical by feature name.

Part of CONTRACT-BACKLOG-36 Plan B.2."
```

---

## Task 9: `iterate_configurables_banner()`

**Files:**
- Modify: `.claude/features/contract/lib/runtime.py`
- Create: `.claude/features/contract/test/test-runtime-iterate-configurables-banner.py`
- Modify: `.claude/features/contract/test/run.py`

**Behavior:** Like `iterate_configurables_alerts` but for SessionStart. For each configurable whose current value matches `alert-on`, emit a multi-line print_result whose `text` is:

```
<alert.text>
  revoke with: /rabbit-config <subcommand> <default>
```

Icon and color come from `alert-message`. The result is a list of print_results (possibly empty), one per active override.

If a configurable has no `default`, fall back to literal text `<unknown>`.

- [ ] **Step 1: Write the failing test**

Create `.claude/features/contract/test/test-runtime-iterate-configurables-banner.py`:

```python
#!/usr/bin/env python3
"""test-runtime-iterate-configurables-banner.py — exercises
iterate_configurables_banner: like iterate_configurables_alerts but the
print_result.text is multi-line and includes a canonical revoke command.
"""

import json
import os
import sys
import tempfile

FEATURE_DIR = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, FEATURE_DIR)

from lib.runtime import iterate_configurables_banner  # noqa: E402

FAIL = 0


def fail(msg):
    global FAIL
    print(f"FAIL: {msg}", file=sys.stderr)
    FAIL = 1


def ok(msg):
    print(f"PASS: {msg}")


def make_feature(root, name, configuration):
    fdir = os.path.join(root, ".claude", "features", name)
    os.makedirs(fdir, exist_ok=True)
    with open(os.path.join(fdir, "feature.json"), "w") as f:
        json.dump({"name": name, "version": "1.0.0", "owner": "x",
                   "configuration": configuration}, f)


HA = {
    "id": "human-approval",
    "subcommand": "human-approval",
    "storage": {"type": "marker-file", "path": ".rabbit-human-approval-bypass"},
    "default": "true",
    "alert-on": "false",
    "alert-message": {"text": "HUMAN APPROVAL BYPASS ACTIVE",
                       "icon": "key", "color": "red"},
}

# t1: no overrides active -> empty list
with tempfile.TemporaryDirectory() as td:
    make_feature(td, "rabbit-cage", [HA])
    r = iterate_configurables_banner(repo_root=td)
    if r == []:
        ok("t1: no active overrides returns empty list")
    else:
        fail(f"t1: expected [], got {r!r}")

# t2: one active override -> one print with multi-line text + revoke hint
with tempfile.TemporaryDirectory() as td:
    make_feature(td, "rabbit-cage", [HA])
    with open(os.path.join(td, ".rabbit-human-approval-bypass"), "w") as f:
        f.write("session")
    r = iterate_configurables_banner(repo_root=td)
    if len(r) != 1 or r[0]["type"] != "print":
        fail(f"t2: expected one print, got {r!r}")
    else:
        expected_revoke = "revoke with: /rabbit-config human-approval true"
        if (r[0]["text"].startswith("HUMAN APPROVAL BYPASS ACTIVE")
                and expected_revoke in r[0]["text"]):
            ok("t2: active override emits print with header line + revoke hint")
        else:
            fail(f"t2: text content unexpected: {r[0]['text']!r}")

# t3: icon and color come from alert-message
with tempfile.TemporaryDirectory() as td:
    make_feature(td, "rabbit-cage", [HA])
    with open(os.path.join(td, ".rabbit-human-approval-bypass"), "w") as f:
        f.write("session")
    r = iterate_configurables_banner(repo_root=td)
    if r[0]["icon"] == "key" and r[0]["color"] == "red":
        ok("t3: icon/color taken from alert-message")
    else:
        fail(f"t3: icon/color wrong: {r[0]!r}")

# t4: configurable without default -> revoke target is <unknown>
with tempfile.TemporaryDirectory() as td:
    no_default = dict(HA)
    no_default.pop("default")
    make_feature(td, "rabbit-cage", [no_default])
    with open(os.path.join(td, ".rabbit-human-approval-bypass"), "w") as f:
        f.write("session")
    r = iterate_configurables_banner(repo_root=td)
    # marker present resolves to "false" regardless of default, matches alert-on
    if r and "<unknown>" in r[0]["text"]:
        ok("t4: missing default falls back to <unknown> in revoke hint")
    else:
        fail(f"t4: unexpected: {r!r}")

if FAIL:
    print("test-runtime-iterate-configurables-banner: FAIL", file=sys.stderr)
    sys.exit(1)
print("test-runtime-iterate-configurables-banner: all checks passed.")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 .claude/features/contract/test/test-runtime-iterate-configurables-banner.py`
Expected: FAIL with `ImportError: cannot import name 'iterate_configurables_banner'`

- [ ] **Step 3: Implement `iterate_configurables_banner`**

Append to `.claude/features/contract/lib/runtime.py`:

```python
def iterate_configurables_banner(*, repo_root: str):
    """Like iterate_configurables_alerts but for SessionStart. Each active
    override emits a multi-line print_result whose text is

        <alert.text>
          revoke with: /rabbit-config <subcommand> <default>

    If the configurable has no `default`, the revoke target falls back to
    the literal string '<unknown>'. Icon and color come from
    alert-message. Returns a list (possibly empty).
    """
    out = []
    for name, fdir, data in _enumerate_features(repo_root):
        configuration = data.get("configuration")
        if not isinstance(configuration, list):
            continue
        for cfg in configuration:
            alert_on = cfg.get("alert-on")
            alert_msg = cfg.get("alert-message")
            if alert_on is None or not isinstance(alert_msg, dict):
                continue
            current = _resolve_current_value(repo_root, cfg)
            if current is None or current != alert_on:
                continue
            subcommand = cfg.get("subcommand", cfg.get("id", "?"))
            revoke_value = cfg.get("default", "<unknown>")
            text = (f"{alert_msg['text']}\n"
                    f"  revoke with: /rabbit-config {subcommand} {revoke_value}")
            out.append(print_result(text, alert_msg["icon"], alert_msg["color"]))
    return out
```

- [ ] **Step 4: Wire the new test into `run.py`**

Append to `.claude/features/contract/test/run.py` (before the final print line):

```python
run_test("test-runtime-iterate-configurables-banner.py")
```

- [ ] **Step 5: Run test to verify it passes**

Run: `python3 .claude/features/contract/test/test-runtime-iterate-configurables-banner.py`
Expected: `test-runtime-iterate-configurables-banner: all checks passed.`

- [ ] **Step 6: Run the full contract test suite**

Run: `python3 .claude/features/contract/test/run.py`
Expected: `ALL TESTS PASSED`

- [ ] **Step 7: Commit**

```bash
git add .claude/features/contract/lib/runtime.py \
        .claude/features/contract/test/test-runtime-iterate-configurables-banner.py \
        .claude/features/contract/test/run.py
git commit -m "feat(contract): iterate_configurables_banner — SessionStart

Same selection rule as iterate_configurables_alerts; per-match
print_result.text is multi-line: header (alert.text) followed by
'  revoke with: /rabbit-config <subcommand> <default>'. If the
configurable has no default, the revoke target falls back to
'<unknown>'. Icon and color from alert-message.

Part of CONTRACT-BACKLOG-36 Plan B.2."
```

---

## Task 10: CHANGELOG entry + integration note + push

**Files:**
- Modify: `.claude/features/contract/CHANGELOG.md`

- [ ] **Step 1: Run the full contract test suite one more time**

Run: `python3 .claude/features/contract/test/run.py`
Expected: `ALL TESTS PASSED`

- [ ] **Step 2: Append a CHANGELOG entry**

Read `.claude/features/contract/CHANGELOG.md` first to learn the entry format. Add a new entry at the top of the entries list (matching surrounding style). Entry content:

```
- 2026-05-23 — feat(lib/runtime): meta-contract runtime API library landed.
  Eight runtime APIs (check_drift_regenerate, check_manifest_drift,
  check_marker_alert, check_marker_consume_alert,
  check_counter_threshold_refresh, welcome_with_policy,
  iterate_configurables_alerts, iterate_configurables_banner) +
  four result-factory helpers (print_result, inject_result, ok_result,
  error_result). Stdlib only. Late-imports lib.publish and lib.producers
  so the module loads standalone.
  Pending: feature.json version bump + invariants will be added in the
  integration commit after B.2/B.3/B.4 branches merge.
  (CONTRACT-BACKLOG-36 Plan B.2)
```

(Match the surrounding entry format exactly — if the file uses a different bullet style, header, or date format, conform to it.)

- [ ] **Step 3: Commit**

```bash
git add .claude/features/contract/CHANGELOG.md
git commit -m "docs(contract): CHANGELOG entry for lib/runtime.py

Notes pending integration-commit work: feature.json version
bump + new invariants for B.2/B.3/B.4 land together after all
four sibling branches merge.

Part of CONTRACT-BACKLOG-36 Plan B.2."
```

- [ ] **Step 4: Push the branch**

```bash
git push -u origin feature/meta-contract-runtime-api
```

---

## Self-review checklist

- [x] Every API in the prompt has a dedicated task (Tasks 2–9 cover the eight runtime APIs; Task 1 covers the result-helpers).
- [x] No task touches `.claude/features/contract/feature.json` or `docs/spec/spec.md` (merge-conflict avoidance honored).
- [x] Every test file is wired into `run.py` in the same commit that creates it.
- [x] Every commit message names CONTRACT-BACKLOG-36 Plan B.2.
- [x] Result-helper return shapes match the contract table in the header.
- [x] APIs that call into a sibling module (`lib.producers`, `lib.publish`) use late import so this branch's module loads even before the siblings land.
- [x] Path-arg convention (repo-root-relative) is documented at the top of `lib/runtime.py` and honored by every API.
- [x] Shared `_enumerate_features` helper is introduced in Task 7 (its first user) and reused by Tasks 8 and 9.
