# Meta-Contract Content Producers (Plan B.4) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement `contract.lib.producers` — the content-producer half of the meta-contract API libraries. Land three producers (`read-file`, `expand-at-imports`, `generate-claude-md`) plus a `call_producer` dispatcher so the already-wired `publish_generated` API stops needing a sys.modules stub in tests.

**Architecture:** A single new module `.claude/features/contract/lib/producers.py` exporting (a) one Python function per producer, (b) a name→function registry mapping the kebab-case producer names declared in MANIFESTs to the snake-case Python functions, and (c) a `call_producer(name, args, *, feature_dir, repo_root)` dispatcher that publish_generated already late-imports (see `lib/publish.py:146-148`). Stdlib only; no shelling out to the existing `rabbit-cage/scripts/generate-claude-md.py`. Path-arg resolution uses a single helper: paths starting with `.claude/` resolve repo-root-relative, all other relative paths resolve feature-dir-relative, absolute paths pass through.

**Tech Stack:** Python 3 (stdlib only — `os`, `json`, no third-party deps).

---

## Universal Rules (carried from foundation plan)

These rules apply to every task below — apply them in the primary commit, not as a follow-up.

**Rule R1 — Every new test file must be wired into `test/run.py` in the same commit.** The contract suite's meta-test `test-run-invokes-all-active-tests.py` fails if any `test-*.py` exists in the directory but is not invoked by `run.py`. So each task that creates a new test file must also append a line of the shape

```python
run_test("<new-test-name>.py")
```

to `.claude/features/contract/test/run.py` BEFORE the commit step. Append at the end of the existing `run_test(...)` sequence (just before `print("ALL TESTS PASSED")`).

**Rule R2 — Code under `.claude/features/contract/scripts/` and `.claude/features/contract/lib/` must carry a module docstring with `Version:`, `Owner:`, `Deprecation criterion:` fields per spec-rules.md.** The `test-contract-scripts-have-docstrings.py` test enforces this. The new `lib/producers.py` must include such a docstring at the top of Task 1.

**Rule R3 — Merge-conflict avoidance with parallel branches.** Per the user briefing:
- Do NOT touch `.claude/features/contract/feature.json` (no version bump in this branch).
- Do NOT touch `.claude/features/contract/docs/spec/spec.md` (no invariant additions in this branch).
- Touching `test/run.py` IS allowed (additive appends — resolvable on merge).
- The version bump and the new invariant for B.4 will land in a follow-on merge commit AFTER all four B.x branches integrate. Note this pending-work item in Task 5's commit message.

---

## Files to be created/modified

**Created:**
- `.claude/features/contract/lib/producers.py` — Producer functions + dispatcher (the entire deliverable).
- `.claude/features/contract/test/test-producers-dispatch.py` — Tests for `call_producer`, the registry, and path resolution. (Task 1)
- `.claude/features/contract/test/test-producers-read-file.py` — Tests for `read-file`. (Task 2)
- `.claude/features/contract/test/test-producers-expand-at-imports.py` — Tests for `expand-at-imports`. (Task 3)
- `.claude/features/contract/test/test-producers-generate-claude-md.py` — Tests for `generate-claude-md`. (Task 4)
- `.claude/features/contract/test/test-producers-publish-generated-integration.py` — End-to-end test: real `publish_generated` invoking real producers (no `sys.modules` stub). (Task 5)

**Modified:**
- `.claude/features/contract/test/run.py` — Append five new `run_test(...)` lines (one per task).

**NOT touched in this branch:**
- `.claude/features/contract/feature.json` (per R3)
- `.claude/features/contract/docs/spec/spec.md` (per R3)
- `.claude/features/contract/lib/publish.py` (already wired; needs no changes — the late-import will start resolving once `lib/producers.py` exists)

---

## Module shape (reference — implemented across Tasks 1-4)

`.claude/features/contract/lib/producers.py` final shape:

```python
"""contract.lib.producers — content producers for publish_generated.

Each producer takes producer-specific named args (forwarded from a feature's
MANIFEST entry) plus keyword-only `feature_dir` and `repo_root` context, and
returns generated content as a string. The producer registry maps the
kebab-case producer names declared in MANIFESTs to these Python functions;
`call_producer(name, args, *, feature_dir, repo_root)` is the dispatcher
that lib.publish.publish_generated invokes.

Path-arg convention (applies to every producer's path args):
  - Absolute paths pass through unchanged.
  - Relative paths starting with ".claude/" resolve against repo_root.
  - All other relative paths resolve against feature_dir.

Future producers documented but not implemented here:
  - compose-template(template, args) — template substitution. Deferred per
    the meta-contract design doc until first concrete need.

Version: 1.0.0
Owner: rabbit-workflow team (contract)
Deprecation criterion: when the rabbit CLI exposes native content producers.
"""

import json
import os


def _resolve(path: str, feature_dir: str, repo_root: str) -> str:
    """Resolve a producer arg path per the module-level convention."""
    if os.path.isabs(path):
        return path
    if path.startswith(".claude/"):
        return os.path.join(repo_root, path)
    return os.path.join(feature_dir, path)


def read_file(path: str, *, feature_dir: str, repo_root: str) -> str:
    """Return the contents of `path` as a string."""
    with open(_resolve(path, feature_dir, repo_root)) as f:
        return f.read()


def expand_at_imports(file: str, *, feature_dir: str, repo_root: str) -> str:
    """Read `file` and expand every line of the form `@<path>` (one path
    per line, no surrounding whitespace inside the path) by substituting
    the contents of <path>. Non-import lines pass through unchanged.
    Expansion is one level deep; imported content is NOT recursively
    re-scanned for further @-imports (matches Claude Code's @-import
    semantics).
    """
    with open(_resolve(file, feature_dir, repo_root)) as f:
        content = f.read()
    out = []
    for line in content.splitlines(keepends=True):
        stripped = line.strip()
        if (
            stripped.startswith("@")
            and len(stripped) > 1
            and not any(c.isspace() for c in stripped)
        ):
            imported = open(_resolve(stripped[1:], feature_dir, repo_root)).read()
            if not imported.endswith("\n"):
                imported += "\n"
            out.append(imported)
        else:
            out.append(line)
    return "".join(out)


def generate_claude_md(policy_source: str, header_source: str, *,
                       feature_dir: str, repo_root: str) -> str:
    """Compose a CLAUDE.md by emitting the header text from `header_source`
    (a JSON file with a top-level `header` string) followed by a blank line
    and one `@<path>` line per `.md` file found under `policy_source`. The
    @-import paths in the output are written repo-root-relative (the form
    Claude Code expects). Policy files are emitted in alphabetical filename
    order — callers can control order via filename prefixes if needed.
    """
    header_path = _resolve(header_source, feature_dir, repo_root)
    with open(header_path) as f:
        header = json.load(f)["header"]

    policy_dir = _resolve(policy_source, feature_dir, repo_root)
    policy_files = sorted(
        f for f in os.listdir(policy_dir) if f.endswith(".md")
    )
    rel_policy_dir = os.path.relpath(policy_dir, repo_root)
    imports = "\n".join(f"@{rel_policy_dir}/{f}" for f in policy_files)
    return f"{header}\n\n{imports}\n"


# Registry: MANIFEST kebab-case producer names → Python functions.
# To add a new producer, implement the function above and register it here.
PRODUCERS = {
    "read-file": read_file,
    "expand-at-imports": expand_at_imports,
    "generate-claude-md": generate_claude_md,
    # "compose-template": deferred — see module docstring.
}


def call_producer(name: str, args: dict, *,
                  feature_dir: str, repo_root: str) -> str:
    """Dispatch `name` to its registered producer with `args` (forwarded as
    kwargs) plus the keyword-only context params. Returns the producer's
    generated content as a string. Raises KeyError if `name` is not in the
    registry — feature MANIFEST authors are responsible for using valid
    producer names.
    """
    if name not in PRODUCERS:
        raise KeyError(f"unknown producer: {name}")
    return PRODUCERS[name](feature_dir=feature_dir, repo_root=repo_root, **args)
```

Tasks 1-4 build this module incrementally. Each task adds one producer (or the dispatcher) plus its tests. Task 5 verifies the un-stubbed end-to-end path through `publish_generated`.

---

### Task 1: Module skeleton + path-resolution helper + `call_producer` dispatcher

**Files:**
- Create: `.claude/features/contract/lib/producers.py` (module docstring, `_resolve`, empty `PRODUCERS` registry, `call_producer`).
- Create: `.claude/features/contract/test/test-producers-dispatch.py`.
- Modify: `.claude/features/contract/test/run.py` (append one `run_test(...)`).

- [ ] **Step 1: Write the failing test**

File `.claude/features/contract/test/test-producers-dispatch.py`:

```python
#!/usr/bin/env python3
"""test-producers-dispatch.py — exercises lib.producers dispatcher surface:
the call_producer entry point, the PRODUCERS registry, and the _resolve
helper's path conventions (feature-dir vs repo-root).
"""

import os
import sys
import tempfile

FEATURE_DIR = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, FEATURE_DIR)

from lib import producers  # noqa: E402

FAIL = 0


def fail(msg):
    global FAIL
    print(f"FAIL: {msg}", file=sys.stderr)
    FAIL = 1


def ok(msg):
    print(f"PASS: {msg}")


# t1: PRODUCERS registry is a dict (entries populated by later tasks)
if not isinstance(producers.PRODUCERS, dict):
    fail("t1: PRODUCERS is not a dict")
else:
    ok("t1: PRODUCERS is a dict")

# t2: call_producer raises KeyError on unknown name
try:
    producers.call_producer("nope", {}, feature_dir="/tmp", repo_root="/tmp")
    fail("t2: expected KeyError, got success")
except KeyError as e:
    if "nope" in str(e):
        ok("t2: call_producer raises KeyError naming the unknown producer")
    else:
        fail(f"t2: KeyError raised but message does not mention name: {e}")

# t3: _resolve — absolute path passes through
abs_path = "/tmp/some-abs-path"
got = producers._resolve(abs_path, "/feat", "/repo")
if got != abs_path:
    fail(f"t3: absolute path not preserved: {got}")
else:
    ok("t3: _resolve preserves absolute paths unchanged")

# t4: _resolve — relative path starting with .claude/ resolves repo-root
got = producers._resolve(".claude/features/policy/", "/feat", "/repo")
if got != os.path.join("/repo", ".claude/features/policy/"):
    fail(f"t4: .claude/ path did not resolve repo-root-relative: {got}")
else:
    ok("t4: _resolve treats '.claude/'-prefixed paths as repo-root-relative")

# t5: _resolve — other relative paths resolve feature-dir
got = producers._resolve("policy-header.json", "/feat", "/repo")
if got != os.path.join("/feat", "policy-header.json"):
    fail(f"t5: bare path did not resolve feature-dir-relative: {got}")
else:
    ok("t5: _resolve treats bare paths as feature-dir-relative")

# t6: call_producer forwards feature_dir/repo_root and args as kwargs
# Inject a sentinel producer to verify forwarding.
captured = {}


def _sentinel(*, feature_dir, repo_root, alpha, beta):
    captured["feature_dir"] = feature_dir
    captured["repo_root"] = repo_root
    captured["alpha"] = alpha
    captured["beta"] = beta
    return "sentinel-output"


producers.PRODUCERS["__sentinel__"] = _sentinel
try:
    result = producers.call_producer(
        "__sentinel__", {"alpha": 1, "beta": "two"},
        feature_dir="/F", repo_root="/R",
    )
    if (result == "sentinel-output"
            and captured == {"feature_dir": "/F", "repo_root": "/R",
                             "alpha": 1, "beta": "two"}):
        ok("t6: call_producer forwards args + context kwargs to registered fn")
    else:
        fail(f"t6: unexpected dispatch behaviour: result={result!r} captured={captured}")
finally:
    del producers.PRODUCERS["__sentinel__"]

if FAIL:
    print("test-producers-dispatch: FAIL", file=sys.stderr)
    sys.exit(1)
print("test-producers-dispatch: all checks passed.")
```

(t1 is intentionally loose for Task 1's commit — Tasks 2/3/4 tighten it each time a producer is registered. Final form at the end of Task 4 asserts exactly the three real producer names.)

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 .claude/features/contract/test/test-producers-dispatch.py`
Expected: FAIL — `ModuleNotFoundError: No module named 'lib.producers'`.

- [ ] **Step 3: Create the producers module (skeleton)**

File `.claude/features/contract/lib/producers.py`:

```python
"""contract.lib.producers — content producers for publish_generated.

Each producer takes producer-specific named args (forwarded from a feature's
MANIFEST entry) plus keyword-only `feature_dir` and `repo_root` context, and
returns generated content as a string. The producer registry maps the
kebab-case producer names declared in MANIFESTs to these Python functions;
`call_producer(name, args, *, feature_dir, repo_root)` is the dispatcher
that lib.publish.publish_generated invokes.

Path-arg convention (applies to every producer's path args):
  - Absolute paths pass through unchanged.
  - Relative paths starting with ".claude/" resolve against repo_root.
  - All other relative paths resolve against feature_dir.

Future producers documented but not implemented here:
  - compose-template(template, args) — template substitution. Deferred per
    the meta-contract design doc until first concrete need.

Version: 1.0.0
Owner: rabbit-workflow team (contract)
Deprecation criterion: when the rabbit CLI exposes native content producers.
"""

import os


def _resolve(path: str, feature_dir: str, repo_root: str) -> str:
    """Resolve a producer arg path per the module-level convention."""
    if os.path.isabs(path):
        return path
    if path.startswith(".claude/"):
        return os.path.join(repo_root, path)
    return os.path.join(feature_dir, path)


# Registry: MANIFEST kebab-case producer names → Python functions.
# Populated by Tasks 2-4 (read-file, expand-at-imports, generate-claude-md).
PRODUCERS = {
    # populated by later tasks
}


def call_producer(name: str, args: dict, *,
                  feature_dir: str, repo_root: str) -> str:
    """Dispatch `name` to its registered producer with `args` (forwarded as
    kwargs) plus the keyword-only context params. Returns the producer's
    generated content as a string. Raises KeyError if `name` is not in the
    registry — feature MANIFEST authors are responsible for using valid
    producer names.
    """
    if name not in PRODUCERS:
        raise KeyError(f"unknown producer: {name}")
    return PRODUCERS[name](feature_dir=feature_dir, repo_root=repo_root, **args)
```

- [ ] **Step 4: Wire the new test into run.py**

Edit `.claude/features/contract/test/run.py` — append immediately before `print("ALL TESTS PASSED")`:

```python
run_test("test-producers-dispatch.py")
```

- [ ] **Step 5: Run test + full suite to verify they pass**

Run: `python3 .claude/features/contract/test/test-producers-dispatch.py`
Expected: PASS (all 6 assertions — t1 in its loose form).

Run: `python3 .claude/features/contract/test/run.py`
Expected: PASS — the meta-test `test-run-invokes-all-active-tests.py` sees the new line and is happy; the docstring meta-test sees the new lib module's docstring fields.

- [ ] **Step 6: Commit**

```bash
git add .claude/features/contract/lib/producers.py \
        .claude/features/contract/test/test-producers-dispatch.py \
        .claude/features/contract/test/run.py
git commit -m "feat(contract): lib.producers skeleton + call_producer dispatcher

Adds the producer module shell with the path-resolution helper and the
dispatcher entry point already late-imported by lib.publish.publish_generated.
Registry is empty in this commit; populated by the three follow-up tasks
(read-file, expand-at-imports, generate-claude-md).

Part of CONTRACT-BACKLOG-36 Plan B.4."
```

---

### Task 2: `read-file` producer

**Files:**
- Modify: `.claude/features/contract/lib/producers.py` (add `read_file` function + register).
- Create: `.claude/features/contract/test/test-producers-read-file.py`.
- Modify: `.claude/features/contract/test/run.py` (append one `run_test(...)`).
- Modify: `.claude/features/contract/test/test-producers-dispatch.py` (tighten t1 to expect `"read-file"` in registry).

- [ ] **Step 1: Write the failing test**

File `.claude/features/contract/test/test-producers-read-file.py`:

```python
#!/usr/bin/env python3
"""test-producers-read-file.py — exercises the read-file producer:
returns the raw contents of the file pointed to by its `path` arg,
honoring the module-level path-resolution convention.
"""

import os
import sys
import tempfile

FEATURE_DIR = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, FEATURE_DIR)

from lib import producers  # noqa: E402

FAIL = 0


def fail(msg):
    global FAIL
    print(f"FAIL: {msg}", file=sys.stderr)
    FAIL = 1


def ok(msg):
    print(f"PASS: {msg}")


# t1: read-file returns raw contents (feature-dir-relative path)
with tempfile.TemporaryDirectory() as td:
    feat = os.path.join(td, "feature")
    root = os.path.join(td, "repo")
    os.makedirs(feat)
    os.makedirs(root)
    target = os.path.join(feat, "blob.txt")
    with open(target, "w") as f:
        f.write("hello world\n")
    out = producers.call_producer(
        "read-file", {"path": "blob.txt"},
        feature_dir=feat, repo_root=root,
    )
    if out != "hello world\n":
        fail(f"t1: read-file output mismatch: {out!r}")
    else:
        ok("t1: read-file returns raw contents for feature-dir-relative path")

# t2: read-file handles repo-root-relative path (".claude/" prefix)
with tempfile.TemporaryDirectory() as td:
    feat = os.path.join(td, "feature")
    root = os.path.join(td, "repo")
    os.makedirs(feat)
    repo_target = os.path.join(root, ".claude", "shared.txt")
    os.makedirs(os.path.dirname(repo_target))
    with open(repo_target, "w") as f:
        f.write("repo-rooted\n")
    out = producers.call_producer(
        "read-file", {"path": ".claude/shared.txt"},
        feature_dir=feat, repo_root=root,
    )
    if out != "repo-rooted\n":
        fail(f"t2: read-file repo-root-relative output mismatch: {out!r}")
    else:
        ok("t2: read-file resolves '.claude/'-prefixed path repo-root-relative")

# t3: missing file raises FileNotFoundError
with tempfile.TemporaryDirectory() as td:
    feat = os.path.join(td, "feature")
    root = os.path.join(td, "repo")
    os.makedirs(feat)
    os.makedirs(root)
    try:
        producers.call_producer(
            "read-file", {"path": "missing.txt"},
            feature_dir=feat, repo_root=root,
        )
        fail("t3: expected FileNotFoundError, got success")
    except FileNotFoundError:
        ok("t3: read-file raises FileNotFoundError on missing path")

if FAIL:
    print("test-producers-read-file: FAIL", file=sys.stderr)
    sys.exit(1)
print("test-producers-read-file: all checks passed.")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 .claude/features/contract/test/test-producers-read-file.py`
Expected: FAIL — `KeyError: unknown producer: read-file` (the dispatcher exists, the registration does not yet).

- [ ] **Step 3: Implement `read_file` + register it**

Edit `.claude/features/contract/lib/producers.py`:

Add the function above the `PRODUCERS` dict (after `_resolve`):

```python
def read_file(path: str, *, feature_dir: str, repo_root: str) -> str:
    """Return the contents of `path` (resolved per the module-level
    convention) as a string. Raises FileNotFoundError if the file is
    missing — caller (typically publish_generated) propagates the error.
    """
    with open(_resolve(path, feature_dir, repo_root)) as f:
        return f.read()
```

Add to the `PRODUCERS` dict:

```python
PRODUCERS = {
    "read-file": read_file,
}
```

- [ ] **Step 4: Tighten t1 in test-producers-dispatch.py**

Change t1 in `.claude/features/contract/test/test-producers-dispatch.py` from the loose dict-shape check to:

```python
# t1: PRODUCERS registry contains read-file
if "read-file" not in producers.PRODUCERS:
    fail("t1: registry missing 'read-file'")
else:
    ok("t1: PRODUCERS registry contains 'read-file'")
```

(Tasks 3 and 4 will further tighten this.)

- [ ] **Step 5: Wire the new test into run.py**

Edit `.claude/features/contract/test/run.py` — append immediately before `print("ALL TESTS PASSED")`:

```python
run_test("test-producers-read-file.py")
```

- [ ] **Step 6: Run tests to verify green**

Run: `python3 .claude/features/contract/test/test-producers-read-file.py`
Expected: PASS (t1 + t2 + t3).

Run: `python3 .claude/features/contract/test/test-producers-dispatch.py`
Expected: PASS (tightened t1 + t2-t6).

Run: `python3 .claude/features/contract/test/run.py`
Expected: PASS — full suite.

- [ ] **Step 7: Commit**

```bash
git add .claude/features/contract/lib/producers.py \
        .claude/features/contract/test/test-producers-read-file.py \
        .claude/features/contract/test/test-producers-dispatch.py \
        .claude/features/contract/test/run.py
git commit -m "feat(contract): read-file producer + dispatcher registration

Trivial producer that returns raw file contents under the standard path
convention. Exists so publish_generated's producer dispatch surface is
uniform across all generated artifacts.

Part of CONTRACT-BACKLOG-36 Plan B.4."
```

---

### Task 3: `expand-at-imports` producer

**Files:**
- Modify: `.claude/features/contract/lib/producers.py` (add `expand_at_imports` + register).
- Create: `.claude/features/contract/test/test-producers-expand-at-imports.py`.
- Modify: `.claude/features/contract/test/run.py` (append one `run_test(...)`).
- Modify: `.claude/features/contract/test/test-producers-dispatch.py` (tighten t1 to also expect `"expand-at-imports"`).

- [ ] **Step 1: Write the failing test**

File `.claude/features/contract/test/test-producers-expand-at-imports.py`:

```python
#!/usr/bin/env python3
"""test-producers-expand-at-imports.py — exercises the expand-at-imports
producer: reads `file`, expands each line of the form `@<path>` (one path
per line, no whitespace inside the path) into the contents of <path>.
Expansion is one level only — imported content is not recursively
re-scanned. Mirrors Claude Code's @-import semantics.
"""

import os
import sys
import tempfile

FEATURE_DIR = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, FEATURE_DIR)

from lib import producers  # noqa: E402

FAIL = 0


def fail(msg):
    global FAIL
    print(f"FAIL: {msg}", file=sys.stderr)
    FAIL = 1


def ok(msg):
    print(f"PASS: {msg}")


# t1: single @-import line is replaced with referenced file contents
with tempfile.TemporaryDirectory() as td:
    feat = os.path.join(td, "feature")
    root = os.path.join(td, "repo")
    os.makedirs(feat)
    os.makedirs(root)
    inner = os.path.join(feat, "inner.txt")
    with open(inner, "w") as f:
        f.write("INNER\n")
    outer = os.path.join(feat, "outer.txt")
    with open(outer, "w") as f:
        f.write("@inner.txt\n")
    out = producers.call_producer(
        "expand-at-imports", {"file": "outer.txt"},
        feature_dir=feat, repo_root=root,
    )
    if out != "INNER\n":
        fail(f"t1: single-import expansion mismatch: {out!r}")
    else:
        ok("t1: single @-import line is replaced with imported file contents")

# t2: non-import lines pass through unchanged; mixed content composes correctly
with tempfile.TemporaryDirectory() as td:
    feat = os.path.join(td, "feature")
    root = os.path.join(td, "repo")
    os.makedirs(feat)
    os.makedirs(root)
    with open(os.path.join(feat, "a.md"), "w") as f:
        f.write("A-content\n")
    with open(os.path.join(feat, "b.md"), "w") as f:
        f.write("B-content\n")
    with open(os.path.join(feat, "doc.md"), "w") as f:
        f.write("# Title\n\n@a.md\n\nMiddle prose.\n\n@b.md\n")
    out = producers.call_producer(
        "expand-at-imports", {"file": "doc.md"},
        feature_dir=feat, repo_root=root,
    )
    expected = "# Title\n\nA-content\n\nMiddle prose.\n\nB-content\n"
    if out != expected:
        fail(f"t2: mixed content output mismatch.\nexpected={expected!r}\nactual={out!r}")
    else:
        ok("t2: non-import lines pass through; imports interpolated in place")

# t3: expansion is one level only — imported file's own @-imports are NOT expanded
with tempfile.TemporaryDirectory() as td:
    feat = os.path.join(td, "feature")
    root = os.path.join(td, "repo")
    os.makedirs(feat)
    os.makedirs(root)
    with open(os.path.join(feat, "leaf.txt"), "w") as f:
        f.write("LEAF\n")
    with open(os.path.join(feat, "mid.txt"), "w") as f:
        f.write("@leaf.txt\n")  # contains a nested import
    with open(os.path.join(feat, "top.txt"), "w") as f:
        f.write("@mid.txt\n")
    out = producers.call_producer(
        "expand-at-imports", {"file": "top.txt"},
        feature_dir=feat, repo_root=root,
    )
    # Expansion expands top→mid (one level). mid's content is "@leaf.txt\n"
    # which is NOT further expanded.
    if out != "@leaf.txt\n":
        fail(f"t3: expected one-level expansion, got: {out!r}")
    else:
        ok("t3: expansion is one level only — nested @-imports stay literal")

# t4: lines that look @-like but contain whitespace are NOT treated as imports
with tempfile.TemporaryDirectory() as td:
    feat = os.path.join(td, "feature")
    root = os.path.join(td, "repo")
    os.makedirs(feat)
    os.makedirs(root)
    with open(os.path.join(feat, "doc.txt"), "w") as f:
        f.write("See @some/path for details.\n")
    out = producers.call_producer(
        "expand-at-imports", {"file": "doc.txt"},
        feature_dir=feat, repo_root=root,
    )
    if out != "See @some/path for details.\n":
        fail(f"t4: line with embedded @ should be unchanged, got: {out!r}")
    else:
        ok("t4: in-prose @-references are not expanded (require bare @path line)")

# t5: imported file without trailing newline is normalized (appends \n)
with tempfile.TemporaryDirectory() as td:
    feat = os.path.join(td, "feature")
    root = os.path.join(td, "repo")
    os.makedirs(feat)
    os.makedirs(root)
    with open(os.path.join(feat, "noeol.txt"), "w") as f:
        f.write("no-trailing-newline")  # no \n
    with open(os.path.join(feat, "top.txt"), "w") as f:
        f.write("@noeol.txt\nafter\n")
    out = producers.call_producer(
        "expand-at-imports", {"file": "top.txt"},
        feature_dir=feat, repo_root=root,
    )
    if out != "no-trailing-newline\nafter\n":
        fail(f"t5: trailing newline not normalized: {out!r}")
    else:
        ok("t5: imported file without trailing newline gets one appended")

# t6: import path with .claude/ prefix resolves repo-root-relative
with tempfile.TemporaryDirectory() as td:
    feat = os.path.join(td, "feature")
    root = os.path.join(td, "repo")
    os.makedirs(feat)
    rooted = os.path.join(root, ".claude", "shared.md")
    os.makedirs(os.path.dirname(rooted))
    with open(rooted, "w") as f:
        f.write("SHARED\n")
    with open(os.path.join(feat, "doc.txt"), "w") as f:
        f.write("@.claude/shared.md\n")
    out = producers.call_producer(
        "expand-at-imports", {"file": "doc.txt"},
        feature_dir=feat, repo_root=root,
    )
    if out != "SHARED\n":
        fail(f"t6: .claude/ import did not resolve repo-root: {out!r}")
    else:
        ok("t6: @-import with '.claude/' prefix resolves repo-root-relative")

if FAIL:
    print("test-producers-expand-at-imports: FAIL", file=sys.stderr)
    sys.exit(1)
print("test-producers-expand-at-imports: all checks passed.")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 .claude/features/contract/test/test-producers-expand-at-imports.py`
Expected: FAIL — `KeyError: unknown producer: expand-at-imports`.

- [ ] **Step 3: Implement `expand_at_imports` + register it**

Edit `.claude/features/contract/lib/producers.py`:

Add the function (after `read_file`):

```python
def expand_at_imports(file: str, *, feature_dir: str, repo_root: str) -> str:
    """Read `file` and expand every line of the form `@<path>` (one path
    per line, no whitespace inside the path) by substituting the contents
    of <path>. Non-import lines pass through unchanged. Expansion is one
    level deep — imported content is NOT recursively re-scanned for
    further @-imports (matches Claude Code's @-import semantics). If an
    imported file lacks a trailing newline, one is appended so the
    composed output keeps clean line structure.
    """
    with open(_resolve(file, feature_dir, repo_root)) as f:
        content = f.read()
    out = []
    for line in content.splitlines(keepends=True):
        stripped = line.strip()
        if (
            stripped.startswith("@")
            and len(stripped) > 1
            and not any(c.isspace() for c in stripped)
        ):
            imported = open(_resolve(stripped[1:], feature_dir, repo_root)).read()
            if not imported.endswith("\n"):
                imported += "\n"
            out.append(imported)
        else:
            out.append(line)
    return "".join(out)
```

Update the registry:

```python
PRODUCERS = {
    "read-file": read_file,
    "expand-at-imports": expand_at_imports,
}
```

- [ ] **Step 4: Tighten t1 in test-producers-dispatch.py**

Change t1 in `.claude/features/contract/test/test-producers-dispatch.py`:

```python
# t1: PRODUCERS registry contains read-file and expand-at-imports
missing = [n for n in ("read-file", "expand-at-imports") if n not in producers.PRODUCERS]
if missing:
    fail(f"t1: registry missing {missing!r}")
else:
    ok("t1: PRODUCERS registry contains read-file and expand-at-imports")
```

- [ ] **Step 5: Wire the new test into run.py**

Append to `.claude/features/contract/test/run.py` immediately before `print("ALL TESTS PASSED")`:

```python
run_test("test-producers-expand-at-imports.py")
```

- [ ] **Step 6: Run tests to verify green**

Run: `python3 .claude/features/contract/test/test-producers-expand-at-imports.py`
Expected: PASS (all 6 assertions).

Run: `python3 .claude/features/contract/test/run.py`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add .claude/features/contract/lib/producers.py \
        .claude/features/contract/test/test-producers-expand-at-imports.py \
        .claude/features/contract/test/test-producers-dispatch.py \
        .claude/features/contract/test/run.py
git commit -m "feat(contract): expand-at-imports producer

One-level @-import expansion matching Claude Code's @-import semantics:
bare '@<path>' lines (no whitespace) are replaced with the contents of
<path>; other lines pass through unchanged. Imported content is not
recursively re-scanned. Imported files without trailing newline get one
appended for clean composition.

Part of CONTRACT-BACKLOG-36 Plan B.4."
```

---

### Task 4: `generate-claude-md` producer

**Files:**
- Modify: `.claude/features/contract/lib/producers.py` (add `generate_claude_md` + register, add `json` import if not already there).
- Create: `.claude/features/contract/test/test-producers-generate-claude-md.py`.
- Modify: `.claude/features/contract/test/run.py` (append one `run_test(...)`).
- Modify: `.claude/features/contract/test/test-producers-dispatch.py` (tighten t1 to expect all three).

- [ ] **Step 1: Write the failing test**

File `.claude/features/contract/test/test-producers-generate-claude-md.py`:

```python
#!/usr/bin/env python3
"""test-producers-generate-claude-md.py — exercises the generate-claude-md
producer: composes a CLAUDE.md from a policy header JSON (a JSON file with
a top-level `header` string) plus one @-import line per `.md` file under
`policy_source`. @-import paths are emitted repo-root-relative; policy
files are emitted in alphabetical order; non-.md files in policy_source
are ignored.
"""

import json
import os
import sys
import tempfile

FEATURE_DIR = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, FEATURE_DIR)

from lib import producers  # noqa: E402

FAIL = 0


def fail(msg):
    global FAIL
    print(f"FAIL: {msg}", file=sys.stderr)
    FAIL = 1


def ok(msg):
    print(f"PASS: {msg}")


def _write(path, content):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write(content)


# t1: composes header + blank line + @-imports for each .md file
with tempfile.TemporaryDirectory() as td:
    feat = os.path.join(td, "feature")
    root = os.path.join(td, "repo")
    os.makedirs(feat)
    os.makedirs(root)
    _write(os.path.join(feat, "policy-header.json"),
           json.dumps({"header": "# Project\n\nLine two."}))
    policy_dir = os.path.join(root, ".claude/features/policy")
    _write(os.path.join(policy_dir, "alpha.md"), "alpha")
    _write(os.path.join(policy_dir, "beta.md"), "beta")
    out = producers.call_producer(
        "generate-claude-md",
        {"policy_source": ".claude/features/policy/",
         "header_source": "policy-header.json"},
        feature_dir=feat, repo_root=root,
    )
    expected = (
        "# Project\n\nLine two.\n"
        "\n"
        "@.claude/features/policy/alpha.md\n"
        "@.claude/features/policy/beta.md\n"
    )
    if out != expected:
        fail(f"t1: composition mismatch.\nexpected={expected!r}\nactual={out!r}")
    else:
        ok("t1: composes header + blank line + @-imports for each .md")

# t2: policy files are emitted in alphabetical order regardless of FS order
with tempfile.TemporaryDirectory() as td:
    feat = os.path.join(td, "feature")
    root = os.path.join(td, "repo")
    os.makedirs(feat)
    os.makedirs(root)
    _write(os.path.join(feat, "h.json"), json.dumps({"header": "H"}))
    policy_dir = os.path.join(root, ".claude/features/policy")
    for name in ("zulu.md", "alpha.md", "mike.md"):
        _write(os.path.join(policy_dir, name), name)
    out = producers.call_producer(
        "generate-claude-md",
        {"policy_source": ".claude/features/policy/", "header_source": "h.json"},
        feature_dir=feat, repo_root=root,
    )
    # Imports must appear in alphabetical order: alpha, mike, zulu.
    expected_imports = (
        "@.claude/features/policy/alpha.md\n"
        "@.claude/features/policy/mike.md\n"
        "@.claude/features/policy/zulu.md\n"
    )
    if not out.endswith(expected_imports):
        fail(f"t2: imports not in alphabetical order. tail={out[-200:]!r}")
    else:
        ok("t2: policy files emitted in alphabetical order")

# t3: non-.md files in policy_source are ignored
with tempfile.TemporaryDirectory() as td:
    feat = os.path.join(td, "feature")
    root = os.path.join(td, "repo")
    os.makedirs(feat)
    os.makedirs(root)
    _write(os.path.join(feat, "h.json"), json.dumps({"header": "H"}))
    policy_dir = os.path.join(root, ".claude/features/policy")
    _write(os.path.join(policy_dir, "real.md"), "x")
    _write(os.path.join(policy_dir, "README.txt"), "ignored")
    _write(os.path.join(policy_dir, "config.json"), "{}")
    out = producers.call_producer(
        "generate-claude-md",
        {"policy_source": ".claude/features/policy/", "header_source": "h.json"},
        feature_dir=feat, repo_root=root,
    )
    if ("README.txt" in out) or ("config.json" in out):
        fail(f"t3: non-.md files leaked into output: {out!r}")
    elif "@.claude/features/policy/real.md\n" not in out:
        fail(f"t3: real .md file missing from output: {out!r}")
    else:
        ok("t3: non-.md files in policy_source are ignored")

# t4: header_source resolves feature-dir-relative; policy_source repo-root-relative
# (regression test for the path-resolution convention specifically applied here)
with tempfile.TemporaryDirectory() as td:
    feat = os.path.join(td, "feature")
    root = os.path.join(td, "repo")
    os.makedirs(feat)
    os.makedirs(root)
    # header lives inside the feature
    _write(os.path.join(feat, "policy-header.json"),
           json.dumps({"header": "HEAD"}))
    # policy_source uses .claude/ → repo-root-relative
    policy_dir = os.path.join(root, ".claude/features/policy")
    _write(os.path.join(policy_dir, "one.md"), "one")
    out = producers.call_producer(
        "generate-claude-md",
        {"policy_source": ".claude/features/policy/",
         "header_source": "policy-header.json"},
        feature_dir=feat, repo_root=root,
    )
    if out != "HEAD\n\n@.claude/features/policy/one.md\n":
        fail(f"t4: path-convention output unexpected: {out!r}")
    else:
        ok("t4: header_source resolves feature-dir; policy_source resolves repo-root")

if FAIL:
    print("test-producers-generate-claude-md: FAIL", file=sys.stderr)
    sys.exit(1)
print("test-producers-generate-claude-md: all checks passed.")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 .claude/features/contract/test/test-producers-generate-claude-md.py`
Expected: FAIL — `KeyError: unknown producer: generate-claude-md`.

- [ ] **Step 3: Implement `generate_claude_md` + register it**

Edit `.claude/features/contract/lib/producers.py`:

Add `import json` to the imports at the top (it isn't there yet — the module only imports `os` so far):

```python
import json
import os
```

Add the function (after `expand_at_imports`):

```python
def generate_claude_md(policy_source: str, header_source: str, *,
                       feature_dir: str, repo_root: str) -> str:
    """Compose a CLAUDE.md by emitting the header text from `header_source`
    (a JSON file with a top-level `header` string) followed by a blank line
    and one `@<path>` line per `.md` file found under `policy_source`. The
    @-import paths in the output are written repo-root-relative (the form
    Claude Code expects). Policy files are emitted in alphabetical filename
    order — callers control order via filename prefixes if needed.
    """
    header_path = _resolve(header_source, feature_dir, repo_root)
    with open(header_path) as f:
        header = json.load(f)["header"]

    policy_dir = _resolve(policy_source, feature_dir, repo_root)
    policy_files = sorted(
        f for f in os.listdir(policy_dir) if f.endswith(".md")
    )
    rel_policy_dir = os.path.relpath(policy_dir, repo_root)
    imports = "\n".join(f"@{rel_policy_dir}/{f}" for f in policy_files)
    return f"{header}\n\n{imports}\n"
```

Update the registry to include all three real producers:

```python
PRODUCERS = {
    "read-file": read_file,
    "expand-at-imports": expand_at_imports,
    "generate-claude-md": generate_claude_md,
    # "compose-template": deferred — see module docstring.
}
```

- [ ] **Step 4: Tighten t1 in test-producers-dispatch.py to the final shape**

Restore t1 in `.claude/features/contract/test/test-producers-dispatch.py` to:

```python
# t1: PRODUCERS registry has exactly the three expected producer names
expected = {"read-file", "expand-at-imports", "generate-claude-md"}
actual = set(producers.PRODUCERS.keys())
if actual != expected:
    fail(f"t1: registry keys mismatch. expected={expected} actual={actual}")
else:
    ok("t1: PRODUCERS registry has exactly the three expected producer names")
```

- [ ] **Step 5: Wire the new test into run.py**

Append to `.claude/features/contract/test/run.py` immediately before `print("ALL TESTS PASSED")`:

```python
run_test("test-producers-generate-claude-md.py")
```

- [ ] **Step 6: Run tests to verify green**

Run: `python3 .claude/features/contract/test/test-producers-generate-claude-md.py`
Expected: PASS (t1-t4).

Run: `python3 .claude/features/contract/test/run.py`
Expected: PASS — full suite.

- [ ] **Step 7: Commit**

```bash
git add .claude/features/contract/lib/producers.py \
        .claude/features/contract/test/test-producers-generate-claude-md.py \
        .claude/features/contract/test/test-producers-dispatch.py \
        .claude/features/contract/test/run.py
git commit -m "feat(contract): generate-claude-md producer

Pure-Python composer for CLAUDE.md: reads a header from a JSON file,
emits header text followed by one @-import line per .md file under the
policy source directory. Filenames sorted alphabetically; non-.md files
ignored. Output paths emitted repo-root-relative (the form Claude Code
expects).

Reference: .claude/features/rabbit-cage/scripts/generate-claude-md.py
remains in place for the existing CLAUDE.md regeneration loop; the
rabbit-cage MANIFEST migration to this producer is a separate later
task per the meta-contract design.

Part of CONTRACT-BACKLOG-36 Plan B.4."
```

---

### Task 5: End-to-end integration — publish_generated × real producers (no stub)

**Files:**
- Create: `.claude/features/contract/test/test-producers-publish-generated-integration.py`.
- Modify: `.claude/features/contract/test/run.py` (append one `run_test(...)`).

**Why:** `test-publish-generated.py` (Plan B.1) installs a `sys.modules` stub for `lib.producers` because the module did not yet exist. Now that it does, we add an integration test that exercises the un-stubbed path end-to-end: each of the three real producers is invoked through `publish_generated` against a real filesystem fixture and the resulting written file is verified. This validates the late-import wiring in `lib/publish.py:146-148` and the registry registration done across Tasks 2-4.

- [ ] **Step 1: Write the failing test**

File `.claude/features/contract/test/test-producers-publish-generated-integration.py`:

```python
#!/usr/bin/env python3
"""test-producers-publish-generated-integration.py — end-to-end test that
publish_generated (lib.publish) invokes each of the three real producers
in lib.producers without a sys.modules stub, and writes the expected
output to the target file. Validates the late-import wiring in
publish_generated against the actual registry.
"""

import json
import os
import sys
import tempfile

FEATURE_DIR = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, FEATURE_DIR)

# Deliberately do NOT stub lib.producers — exercise the real module.
from lib.publish import publish_generated  # noqa: E402

FAIL = 0


def fail(msg):
    global FAIL
    print(f"FAIL: {msg}", file=sys.stderr)
    FAIL = 1


def ok(msg):
    print(f"PASS: {msg}")


def _write(path, content):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write(content)


# t1: publish_generated with read-file writes the source contents to target
with tempfile.TemporaryDirectory() as td:
    feat = os.path.join(td, "feature")
    root = os.path.join(td, "repo")
    os.makedirs(feat)
    os.makedirs(root)
    _write(os.path.join(feat, "src.txt"), "raw\n")
    r = publish_generated(
        "out.txt", "read-file", {"path": "src.txt"},
        feature_dir=feat, repo_root=root,
    )
    if not r.passed:
        fail(f"t1: publish_generated read-file failed: {r.messages}")
    elif open(os.path.join(root, "out.txt")).read() != "raw\n":
        fail("t1: read-file output did not match source")
    else:
        ok("t1: publish_generated routes through real read-file producer")

# t2: publish_generated with expand-at-imports expands one-level imports
with tempfile.TemporaryDirectory() as td:
    feat = os.path.join(td, "feature")
    root = os.path.join(td, "repo")
    os.makedirs(feat)
    os.makedirs(root)
    _write(os.path.join(feat, "leaf.md"), "LEAF\n")
    _write(os.path.join(feat, "top.md"), "preface\n@leaf.md\n")
    r = publish_generated(
        "OUT.md", "expand-at-imports", {"file": "top.md"},
        feature_dir=feat, repo_root=root,
    )
    expected = "preface\nLEAF\n"
    if not r.passed:
        fail(f"t2: publish_generated expand-at-imports failed: {r.messages}")
    elif open(os.path.join(root, "OUT.md")).read() != expected:
        fail(f"t2: expansion output mismatch: {open(os.path.join(root, 'OUT.md')).read()!r}")
    else:
        ok("t2: publish_generated routes through real expand-at-imports producer")

# t3: publish_generated with generate-claude-md composes header + @-imports
with tempfile.TemporaryDirectory() as td:
    feat = os.path.join(td, "feature")
    root = os.path.join(td, "repo")
    os.makedirs(feat)
    os.makedirs(root)
    _write(os.path.join(feat, "policy-header.json"),
           json.dumps({"header": "# H"}))
    policy_dir = os.path.join(root, ".claude/features/policy")
    _write(os.path.join(policy_dir, "a.md"), "")
    _write(os.path.join(policy_dir, "b.md"), "")
    r = publish_generated(
        "CLAUDE.md", "generate-claude-md",
        {"policy_source": ".claude/features/policy/",
         "header_source": "policy-header.json"},
        feature_dir=feat, repo_root=root,
    )
    expected = "# H\n\n@.claude/features/policy/a.md\n@.claude/features/policy/b.md\n"
    if not r.passed:
        fail(f"t3: publish_generated generate-claude-md failed: {r.messages}")
    elif open(os.path.join(root, "CLAUDE.md")).read() != expected:
        fail(f"t3: composed CLAUDE.md mismatch: {open(os.path.join(root, 'CLAUDE.md')).read()!r}")
    else:
        ok("t3: publish_generated routes through real generate-claude-md producer")

# t4: idempotency holds end-to-end — second call is a no-op
with tempfile.TemporaryDirectory() as td:
    feat = os.path.join(td, "feature")
    root = os.path.join(td, "repo")
    os.makedirs(feat)
    os.makedirs(root)
    _write(os.path.join(feat, "src.txt"), "x\n")
    publish_generated("o.txt", "read-file", {"path": "src.txt"},
                      feature_dir=feat, repo_root=root)
    r2 = publish_generated("o.txt", "read-file", {"path": "src.txt"},
                           feature_dir=feat, repo_root=root)
    if not r2.passed:
        fail(f"t4: second call failed: {r2.messages}")
    elif not any("no-op" in m.lower() for m in r2.messages):
        fail(f"t4: second call should report no-op: {r2.messages}")
    else:
        ok("t4: end-to-end idempotency through real producers")

if FAIL:
    print("test-producers-publish-generated-integration: FAIL", file=sys.stderr)
    sys.exit(1)
print("test-producers-publish-generated-integration: all checks passed.")
```

- [ ] **Step 2: Run test to verify it passes immediately**

Run: `python3 .claude/features/contract/test/test-producers-publish-generated-integration.py`
Expected: PASS (t1-t4). This test should pass right away because the producer module is now real (Tasks 1-4) and the late-import in publish_generated resolves it correctly. If it fails, the previous tasks left a bug — diagnose before proceeding.

- [ ] **Step 3: Wire the new test into run.py**

Append to `.claude/features/contract/test/run.py` immediately before `print("ALL TESTS PASSED")`:

```python
run_test("test-producers-publish-generated-integration.py")
```

- [ ] **Step 4: Run the full suite to verify nothing regressed**

Run: `python3 .claude/features/contract/test/run.py`
Expected: PASS — every test including the new integration test.

- [ ] **Step 5: Commit**

```bash
git add .claude/features/contract/test/test-producers-publish-generated-integration.py \
        .claude/features/contract/test/run.py
git commit -m "test(contract): integration — publish_generated × real producers

End-to-end coverage: publish_generated invokes each of the three real
producers (read-file, expand-at-imports, generate-claude-md) without a
sys.modules stub. Validates the late-import wiring in lib.publish and
end-to-end idempotency through the real registry.

NOTE — pending follow-on work after parallel B.x branches merge:
  * contract/feature.json version bump (1.23.0 -> 1.24.0)
  * contract spec.md: new invariant declaring the lib.producers API
    (the three producers + call_producer dispatcher + path-arg convention)
The version bump and invariant addition are deferred to the integration
commit per merge-conflict avoidance with parallel branches (B.2 runtime
APIs in ws43, B.3 mutation APIs in ws44).

Part of CONTRACT-BACKLOG-36 Plan B.4."
```

---

## Final acceptance

After Task 5:

- [ ] Run: `python3 .claude/features/contract/test/run.py`
  Expected: ALL TESTS PASSED.
- [ ] Run: `git log --oneline -6`
  Expected: 5 new commits on top of `11e8938e` — one per task.
- [ ] Push: `git push -u origin feature/meta-contract-producers-api`

---

## Self-Review

**Spec coverage:** All three required producers (`generate-claude-md`, `expand-at-imports`, `read-file`) are implemented and tested. `compose-template` is deferred and documented as such in the module docstring and registry comment. The `publish_generated` late-import contract is satisfied (Task 5 verifies un-stubbed integration). No `feature.json` or `spec.md` edits per R3.

**Placeholder scan:** All code blocks contain complete content. No TBD/TODO markers. Every test step has executable assertion code. Every implementation step has executable function bodies.

**Type consistency:** `call_producer(name, args, *, feature_dir, repo_root) -> str` — used identically in publish.py:146-148, the test stub in test-publish-generated.py:20-21, the new dispatch test, and every per-producer test. Producer signatures all follow `(producer-args, *, feature_dir, repo_root) -> str`. The `_resolve(path, feature_dir, repo_root) -> str` helper has the same shape everywhere it's referenced.
