# Meta-Contract Plan B.1: contract.lib.publish

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement `contract.lib.publish` — the seven publish API functions that deploy feature artifacts idempotently into the workspace.

**Architecture:** All functions live in `.claude/features/contract/lib/publish.py`. Each takes API args as positional/keyword params plus keyword-only context params (`feature_dir`, `repo_root`). Returns `CheckResult` (from `lib.checks`). Idempotency via SHA-256 for file operations; content-equality for generated content. `publish_hook` also registers the hook command in `.claude/settings.json` via read-modify-write. `publish_generated` late-imports `lib.producers` (written in B.4) so B.1 tests stub the producers module via `sys.modules` injection before import.

**Tech Stack:** Python 3 stdlib only (`os`, `shutil`, `hashlib`, `json`, `pathlib`).

**Branch:** create `feature/meta-contract-api-libraries` off current HEAD (`feature/meta-contract-foundation`).

---

## Files

**Create:**
- `.claude/features/contract/lib/publish.py`
- `.claude/features/contract/test/test-publish-file.py`
- `.claude/features/contract/test/test-publish-skill-command-agent.py`
- `.claude/features/contract/test/test-publish-hook.py`
- `.claude/features/contract/test/test-publish-settings.py`
- `.claude/features/contract/test/test-publish-generated.py`

**Modify:**
- `.claude/features/contract/test/test-files-exist.py` — add `check_file("lib/publish.py")` in Task 1
- `.claude/features/contract/test/run.py` — wire each test in its Task commit (Revision R1 from Plan A)
- `.claude/features/contract/docs/spec/spec.md` — add invariant 44 in Task 6
- `.claude/features/contract/feature.json` — bump `1.22.0 → 1.23.0` in Task 6
- `.claude/features/contract/docs/spec/contract.md` — add `lib/publish.py` to `provides.lib` in Task 6

---

## Task 1: Branch setup + lib/publish.py skeleton + `publish_file`

**Files:**
- Create: `.claude/features/contract/lib/publish.py`
- Create: `.claude/features/contract/test/test-publish-file.py`
- Modify: `.claude/features/contract/test/run.py`
- Modify: `.claude/features/contract/test/test-files-exist.py`

- [ ] **Step 1: Create the feature branch**

```bash
git checkout -b feature/meta-contract-api-libraries
```

Expected: switched to new branch `feature/meta-contract-api-libraries`.

- [ ] **Step 2: Write the failing test**

Create `.claude/features/contract/test/test-publish-file.py`:

```python
#!/usr/bin/env python3
"""test-publish-file.py — exercises publish_file: idempotent file copy from
feature-dir-relative source to repo-root-relative destination.
"""

import os
import sys
import tempfile

FEATURE_DIR = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, FEATURE_DIR)

from lib.publish import publish_file  # noqa: E402

FAIL = 0


def fail(msg):
    global FAIL
    print(f"FAIL: {msg}", file=sys.stderr)
    FAIL = 1


def ok(msg):
    print(f"PASS: {msg}")


# t1: basic copy — destination created, content matches source
with tempfile.TemporaryDirectory() as td:
    feat = os.path.join(td, "feature")
    root = os.path.join(td, "repo")
    os.makedirs(os.path.join(feat, "scripts"))
    os.makedirs(root)
    src = os.path.join(feat, "scripts", "myscript.py")
    with open(src, "w") as f:
        f.write("# hello\n")
    r = publish_file("scripts/myscript.py", ".claude/hooks/myscript.py",
                     feature_dir=feat, repo_root=root)
    dest = os.path.join(root, ".claude", "hooks", "myscript.py")
    if not r.passed:
        fail(f"t1: publish_file failed: {r.messages}")
    elif not os.path.isfile(dest):
        fail("t1: destination file not created")
    elif open(dest).read() != "# hello\n":
        fail("t1: destination content mismatch")
    else:
        ok("t1: basic copy creates destination with correct content")

# t2: idempotent — same content returns 'no-op' in messages
with tempfile.TemporaryDirectory() as td:
    feat = os.path.join(td, "feature")
    root = os.path.join(td, "repo")
    os.makedirs(os.path.join(feat, "src"))
    os.makedirs(os.path.join(root, ".claude"))
    src = os.path.join(feat, "src", "a.txt")
    dest = os.path.join(root, ".claude", "a.txt")
    with open(src, "w") as f:
        f.write("abc")
    with open(dest, "w") as f:
        f.write("abc")
    r = publish_file("src/a.txt", ".claude/a.txt", feature_dir=feat, repo_root=root)
    if not r.passed:
        fail(f"t2: idempotent call failed: {r.messages}")
    elif not any("no-op" in m.lower() for m in r.messages):
        fail(f"t2: idempotent call should report 'no-op' in messages, got: {r.messages}")
    else:
        ok("t2: idempotent: same content returns no-op result")

# t3: drift — changed source overwrites destination
with tempfile.TemporaryDirectory() as td:
    feat = os.path.join(td, "feature")
    root = os.path.join(td, "repo")
    os.makedirs(os.path.join(feat, "src"))
    os.makedirs(os.path.join(root, ".claude"))
    src = os.path.join(feat, "src", "a.txt")
    dest = os.path.join(root, ".claude", "a.txt")
    with open(src, "w") as f:
        f.write("new-content")
    with open(dest, "w") as f:
        f.write("old-content")
    r = publish_file("src/a.txt", ".claude/a.txt", feature_dir=feat, repo_root=root)
    if not r.passed:
        fail(f"t3: drift copy failed: {r.messages}")
    elif open(dest).read() != "new-content":
        fail("t3: drift copy did not update destination")
    else:
        ok("t3: drift: changed source overwrites destination")

# t4: missing source → CheckResult(passed=False) with descriptive message
with tempfile.TemporaryDirectory() as td:
    feat = os.path.join(td, "feature")
    root = os.path.join(td, "repo")
    os.makedirs(feat)
    os.makedirs(root)
    r = publish_file("nonexistent.txt", "out.txt", feature_dir=feat, repo_root=root)
    if r.passed:
        fail("t4: missing source should return passed=False")
    elif not any(
        word in " ".join(r.messages).lower()
        for word in ("source", "not found", "missing")
    ):
        fail(f"t4: error message doesn't mention source: {r.messages}")
    else:
        ok("t4: missing source returns passed=False with descriptive message")

# t5: destination parent directories created automatically
with tempfile.TemporaryDirectory() as td:
    feat = os.path.join(td, "feature")
    root = os.path.join(td, "repo")
    os.makedirs(os.path.join(feat, "f"))
    os.makedirs(root)
    with open(os.path.join(feat, "f", "x.md"), "w") as f:
        f.write("hi")
    r = publish_file("f/x.md", "a/b/c/x.md", feature_dir=feat, repo_root=root)
    if not r.passed:
        fail(f"t5: deep destination failed: {r.messages}")
    elif not os.path.isfile(os.path.join(root, "a", "b", "c", "x.md")):
        fail("t5: deep destination not created")
    else:
        ok("t5: destination parent directories created automatically")

if FAIL:
    print("test-publish-file: FAIL", file=sys.stderr)
    sys.exit(1)
print("test-publish-file: all checks passed.")
```

- [ ] **Step 3: Run test to verify it fails**

```bash
python3 .claude/features/contract/test/test-publish-file.py
```

Expected: `ModuleNotFoundError` or `ImportError` — `lib.publish` does not exist yet.

- [ ] **Step 4: Create `lib/publish.py`**

Create `.claude/features/contract/lib/publish.py`:

```python
"""contract.lib.publish — API library for deploying feature artifacts to the workspace.

Each function implements one publish API call as declared in a feature's MANIFEST
section. All functions accept API args as explicit params plus keyword-only context
params (feature_dir, repo_root) and return CheckResult.

All publish operations are idempotent: if the destination already matches the source
(by SHA-256 for files, by content equality for generated), the call is a no-op.

Version: 1.0.0
Owner: rabbit-workflow team (contract)
Deprecation criterion: when the rabbit CLI exposes native artifact publishing.
"""

import hashlib
import json
import os
import shutil
from pathlib import Path

from lib.checks import CheckResult


def _sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def publish_file(source: str, dest: str, *, feature_dir: str, repo_root: str) -> CheckResult:
    """Deploy source (feature-dir-relative) to dest (repo-root-relative), idempotent.

    Returns CheckResult(passed=False) if source does not exist.
    Returns CheckResult(passed=True) on success (copy) or no-op (unchanged).
    """
    src_path = os.path.join(feature_dir, source)
    dst_path = os.path.join(repo_root, dest)
    if not os.path.isfile(src_path):
        return CheckResult(False, [f"ERROR: source not found: {src_path}"])
    if os.path.isfile(dst_path) and _sha256_file(src_path) == _sha256_file(dst_path):
        return CheckResult(True, [f"OK: {dest} unchanged (no-op)"])
    dst_dir = os.path.dirname(dst_path)
    if dst_dir:
        os.makedirs(dst_dir, exist_ok=True)
    shutil.copy2(src_path, dst_path)
    return CheckResult(True, [f"OK: {dest} published"])
```

- [ ] **Step 5: Run test to verify it passes**

```bash
python3 .claude/features/contract/test/test-publish-file.py
```

Expected: all PASS lines, exit 0.

- [ ] **Step 6: Add `lib/publish.py` to `test-files-exist.py`**

Open `.claude/features/contract/test/test-files-exist.py`. Find the line `check_file("scripts/rabbit_print.py")`. Add immediately after it:

```python
check_file("lib/publish.py")
```

- [ ] **Step 7: Wire test into `run.py` and commit**

Open `.claude/features/contract/test/run.py`. After `run_test("test-validate-meta-contract-cli.py")`, add:

```python
run_test("test-publish-file.py")
```

Run the full suite to verify:

```bash
python3 .claude/features/contract/test/run.py
```

Expected: ALL TESTS PASSED.

```bash
git add .claude/features/contract/lib/publish.py \
        .claude/features/contract/test/test-publish-file.py \
        .claude/features/contract/test/test-files-exist.py \
        .claude/features/contract/test/run.py
git commit -m "feat(contract): lib/publish.py — publish_file (idempotent SHA-256 copy)

Core primitive for all publish APIs. SHA-256 comparison makes every
publish call a no-op when source already matches destination."
```

---

## Task 2: `publish_skill`, `publish_command`, `publish_agent`

**Files:**
- Modify: `.claude/features/contract/lib/publish.py` (append 3 functions)
- Create: `.claude/features/contract/test/test-publish-skill-command-agent.py`
- Modify: `.claude/features/contract/test/run.py`

- [ ] **Step 1: Write the failing test**

Create `.claude/features/contract/test/test-publish-skill-command-agent.py`:

```python
#!/usr/bin/env python3
"""test-publish-skill-command-agent.py — exercises publish_skill, publish_command,
publish_agent: path-convention variants of publish_file.
"""

import os
import sys
import tempfile

FEATURE_DIR = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, FEATURE_DIR)

from lib.publish import publish_skill, publish_command, publish_agent  # noqa: E402

FAIL = 0


def fail(msg):
    global FAIL
    print(f"FAIL: {msg}", file=sys.stderr)
    FAIL = 1


def ok(msg):
    print(f"PASS: {msg}")


# --- publish_skill ---

# t1: skill deployed to .claude/skills/<name>/SKILL.md; name from parent dir
with tempfile.TemporaryDirectory() as td:
    feat = os.path.join(td, "feature")
    root = os.path.join(td, "repo")
    skill_src = os.path.join(feat, "skills", "rabbit-foo")
    os.makedirs(skill_src)
    with open(os.path.join(skill_src, "SKILL.md"), "w") as f:
        f.write("# rabbit-foo skill\n")
    r = publish_skill("skills/rabbit-foo/SKILL.md", feature_dir=feat, repo_root=root)
    dest = os.path.join(root, ".claude", "skills", "rabbit-foo", "SKILL.md")
    if not r.passed:
        fail(f"t1: publish_skill failed: {r.messages}")
    elif not os.path.isfile(dest):
        fail(f"t1: skill not at {dest}")
    elif open(dest).read() != "# rabbit-foo skill\n":
        fail("t1: skill content mismatch")
    else:
        ok("t1: publish_skill deploys to .claude/skills/<name>/SKILL.md")

# t2: skill name derived from source parent directory name
with tempfile.TemporaryDirectory() as td:
    feat = os.path.join(td, "feature")
    root = os.path.join(td, "repo")
    skill_src = os.path.join(feat, "skills", "rabbit-bar")
    os.makedirs(skill_src)
    with open(os.path.join(skill_src, "SKILL.md"), "w") as f:
        f.write("bar")
    publish_skill("skills/rabbit-bar/SKILL.md", feature_dir=feat, repo_root=root)
    dest = os.path.join(root, ".claude", "skills", "rabbit-bar", "SKILL.md")
    if os.path.isfile(dest):
        ok("t2: skill name derived from source parent directory name")
    else:
        fail(f"t2: expected {dest}")

# t3: missing source → passed=False
with tempfile.TemporaryDirectory() as td:
    feat = os.path.join(td, "feature")
    root = os.path.join(td, "repo")
    os.makedirs(feat)
    os.makedirs(root)
    r = publish_skill("skills/rabbit-missing/SKILL.md", feature_dir=feat, repo_root=root)
    if r.passed:
        fail("t3: missing source should fail")
    else:
        ok("t3: publish_skill missing source → passed=False")

# t4: idempotent — same content reports no-op
with tempfile.TemporaryDirectory() as td:
    feat = os.path.join(td, "feature")
    root = os.path.join(td, "repo")
    skill_src = os.path.join(feat, "skills", "rabbit-baz")
    skill_dst = os.path.join(root, ".claude", "skills", "rabbit-baz")
    os.makedirs(skill_src)
    os.makedirs(skill_dst)
    content = "# rabbit-baz\n"
    with open(os.path.join(skill_src, "SKILL.md"), "w") as f:
        f.write(content)
    with open(os.path.join(skill_dst, "SKILL.md"), "w") as f:
        f.write(content)
    r = publish_skill("skills/rabbit-baz/SKILL.md", feature_dir=feat, repo_root=root)
    if not r.passed:
        fail(f"t4: idempotent call failed: {r.messages}")
    elif not any("no-op" in m.lower() for m in r.messages):
        fail(f"t4: idempotent should report no-op, got: {r.messages}")
    else:
        ok("t4: publish_skill idempotent when content unchanged")

# --- publish_command ---

# t5: command deployed to .claude/commands/<basename>
with tempfile.TemporaryDirectory() as td:
    feat = os.path.join(td, "feature")
    root = os.path.join(td, "repo")
    cmd_dir = os.path.join(feat, "commands")
    os.makedirs(cmd_dir)
    with open(os.path.join(cmd_dir, "rabbit-do.md"), "w") as f:
        f.write("# rabbit-do\n")
    r = publish_command("commands/rabbit-do.md", feature_dir=feat, repo_root=root)
    dest = os.path.join(root, ".claude", "commands", "rabbit-do.md")
    if not r.passed:
        fail(f"t5: publish_command failed: {r.messages}")
    elif not os.path.isfile(dest):
        fail(f"t5: command not at {dest}")
    else:
        ok("t5: publish_command deploys to .claude/commands/<basename>")

# t6: command idempotent
with tempfile.TemporaryDirectory() as td:
    feat = os.path.join(td, "feature")
    root = os.path.join(td, "repo")
    cmd_dir = os.path.join(feat, "commands")
    dest_dir = os.path.join(root, ".claude", "commands")
    os.makedirs(cmd_dir)
    os.makedirs(dest_dir)
    with open(os.path.join(cmd_dir, "rabbit-x.md"), "w") as f:
        f.write("same")
    with open(os.path.join(dest_dir, "rabbit-x.md"), "w") as f:
        f.write("same")
    r = publish_command("commands/rabbit-x.md", feature_dir=feat, repo_root=root)
    if not r.passed:
        fail(f"t6: idempotent command failed: {r.messages}")
    elif not any("no-op" in m.lower() for m in r.messages):
        fail(f"t6: idempotent should report no-op, got: {r.messages}")
    else:
        ok("t6: publish_command idempotent when content unchanged")

# --- publish_agent ---

# t7: agent deployed to .claude/agents/<basename>
with tempfile.TemporaryDirectory() as td:
    feat = os.path.join(td, "feature")
    root = os.path.join(td, "repo")
    agent_dir = os.path.join(feat, "agents")
    os.makedirs(agent_dir)
    with open(os.path.join(agent_dir, "rabbit-helper.md"), "w") as f:
        f.write("# rabbit-helper agent\n")
    r = publish_agent("agents/rabbit-helper.md", feature_dir=feat, repo_root=root)
    dest = os.path.join(root, ".claude", "agents", "rabbit-helper.md")
    if not r.passed:
        fail(f"t7: publish_agent failed: {r.messages}")
    elif not os.path.isfile(dest):
        fail(f"t7: agent not at {dest}")
    else:
        ok("t7: publish_agent deploys to .claude/agents/<basename>")

# t8: agent missing source → passed=False
with tempfile.TemporaryDirectory() as td:
    feat = os.path.join(td, "feature")
    root = os.path.join(td, "repo")
    os.makedirs(feat)
    os.makedirs(root)
    r = publish_agent("agents/rabbit-missing.md", feature_dir=feat, repo_root=root)
    if r.passed:
        fail("t8: missing agent source should fail")
    else:
        ok("t8: publish_agent missing source → passed=False")

if FAIL:
    print("test-publish-skill-command-agent: FAIL", file=sys.stderr)
    sys.exit(1)
print("test-publish-skill-command-agent: all checks passed.")
```

- [ ] **Step 2: Run test to verify it fails**

```bash
python3 .claude/features/contract/test/test-publish-skill-command-agent.py
```

Expected: `ImportError` — `publish_skill`, `publish_command`, `publish_agent` not yet defined.

- [ ] **Step 3: Append the three functions to `lib/publish.py`**

Open `.claude/features/contract/lib/publish.py`. Append at the end of the file:

```python


def publish_skill(source: str, *, feature_dir: str, repo_root: str) -> CheckResult:
    """Deploy a skill's SKILL.md to .claude/skills/<skill-name>/SKILL.md.

    source — feature-dir-relative path, e.g. "skills/rabbit-foo/SKILL.md".
    Skill name is the name of the source file's parent directory.
    """
    skill_name = Path(source).parent.name
    dest = f".claude/skills/{skill_name}/{Path(source).name}"
    return publish_file(source, dest, feature_dir=feature_dir, repo_root=repo_root)


def publish_command(source: str, *, feature_dir: str, repo_root: str) -> CheckResult:
    """Deploy a command file to .claude/commands/<basename>.

    source — feature-dir-relative path, e.g. "commands/rabbit-do.md".
    """
    dest = f".claude/commands/{Path(source).name}"
    return publish_file(source, dest, feature_dir=feature_dir, repo_root=repo_root)


def publish_agent(source: str, *, feature_dir: str, repo_root: str) -> CheckResult:
    """Deploy an agent file to .claude/agents/<basename>.

    source — feature-dir-relative path, e.g. "agents/rabbit-helper.md".
    """
    dest = f".claude/agents/{Path(source).name}"
    return publish_file(source, dest, feature_dir=feature_dir, repo_root=repo_root)
```

- [ ] **Step 4: Run test to verify it passes**

```bash
python3 .claude/features/contract/test/test-publish-skill-command-agent.py
```

Expected: all PASS, exit 0.

- [ ] **Step 5: Wire into `run.py` and commit**

Add to `run.py` after `run_test("test-publish-file.py")`:

```python
run_test("test-publish-skill-command-agent.py")
```

```bash
git add .claude/features/contract/lib/publish.py \
        .claude/features/contract/test/test-publish-skill-command-agent.py \
        .claude/features/contract/test/run.py
git commit -m "feat(contract): publish_skill, publish_command, publish_agent

Path-convention wrappers around publish_file. Skill name derived from
source parent directory; command and agent use source basename."
```

---

## Task 3: `publish_hook`

**Files:**
- Modify: `.claude/features/contract/lib/publish.py` (append `publish_hook`)
- Create: `.claude/features/contract/test/test-publish-hook.py`
- Modify: `.claude/features/contract/test/run.py`

- [ ] **Step 1: Write the failing test**

Create `.claude/features/contract/test/test-publish-hook.py`:

```python
#!/usr/bin/env python3
"""test-publish-hook.py — exercises publish_hook: deploys a hook script to
.claude/hooks/ and registers it in .claude/settings.json via read-modify-write.
"""

import json
import os
import sys
import tempfile

FEATURE_DIR = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, FEATURE_DIR)

from lib.publish import publish_hook  # noqa: E402

FAIL = 0


def fail(msg):
    global FAIL
    print(f"FAIL: {msg}", file=sys.stderr)
    FAIL = 1


def ok(msg):
    print(f"PASS: {msg}")


def make_env(td, hook_content="# hook\n"):
    feat = os.path.join(td, "feature")
    root = os.path.join(td, "repo")
    hooks_src = os.path.join(feat, "hooks")
    os.makedirs(hooks_src)
    os.makedirs(os.path.join(root, ".claude"))
    with open(os.path.join(hooks_src, "stop-check.py"), "w") as f:
        f.write(hook_content)
    return feat, root


# t1: hook file deployed to .claude/hooks/<filename>
with tempfile.TemporaryDirectory() as td:
    feat, root = make_env(td)
    r = publish_hook("Stop", "hooks/stop-check.py", feature_dir=feat, repo_root=root)
    dest = os.path.join(root, ".claude", "hooks", "stop-check.py")
    if not r.passed:
        fail(f"t1: publish_hook failed: {r.messages}")
    elif not os.path.isfile(dest):
        fail("t1: hook file not deployed to .claude/hooks/")
    else:
        ok("t1: hook file deployed to .claude/hooks/")

# t2: hook registered in settings.json under correct event
with tempfile.TemporaryDirectory() as td:
    feat, root = make_env(td)
    publish_hook("Stop", "hooks/stop-check.py", feature_dir=feat, repo_root=root)
    settings_path = os.path.join(root, ".claude", "settings.json")
    if not os.path.isfile(settings_path):
        fail("t2: settings.json not created")
    else:
        data = json.loads(open(settings_path).read())
        stop_entries = data.get("hooks", {}).get("Stop", [])
        commands = [h["command"] for entry in stop_entries for h in entry.get("hooks", [])]
        if ".claude/hooks/stop-check.py" in commands:
            ok("t2: hook command registered in settings.json under Stop")
        else:
            fail(f"t2: hook command not found in Stop hooks; found: {commands}")

# t3: idempotent — second call does not duplicate the settings.json entry
with tempfile.TemporaryDirectory() as td:
    feat, root = make_env(td)
    publish_hook("Stop", "hooks/stop-check.py", feature_dir=feat, repo_root=root)
    publish_hook("Stop", "hooks/stop-check.py", feature_dir=feat, repo_root=root)
    settings_path = os.path.join(root, ".claude", "settings.json")
    data = json.loads(open(settings_path).read())
    stop_entries = data.get("hooks", {}).get("Stop", [])
    commands = [h["command"] for entry in stop_entries for h in entry.get("hooks", [])]
    count = commands.count(".claude/hooks/stop-check.py")
    if count == 1:
        ok("t3: idempotent: duplicate call does not add duplicate settings entry")
    else:
        fail(f"t3: expected 1 registration, got {count}; commands={commands}")

# t4: existing settings.json fields are preserved (read-modify-write)
with tempfile.TemporaryDirectory() as td:
    feat, root = make_env(td)
    settings_path = os.path.join(root, ".claude", "settings.json")
    existing = {
        "env": {"MY_VAR": "hello"},
        "permissions": {"allow": ["Bash(*)"]},
        "hooks": {
            "Stop": [{"matcher": "*", "hooks": [{"type": "command",
                                                  "command": ".claude/hooks/other.py"}]}]
        }
    }
    with open(settings_path, "w") as f:
        json.dump(existing, f)
    publish_hook("Stop", "hooks/stop-check.py", feature_dir=feat, repo_root=root)
    data = json.loads(open(settings_path).read())
    if data.get("env", {}).get("MY_VAR") != "hello":
        fail("t4: existing env field lost after publish_hook")
    elif data.get("permissions", {}).get("allow") != ["Bash(*)"]:
        fail("t4: existing permissions field lost after publish_hook")
    else:
        ok("t4: existing settings fields preserved via read-modify-write")

# t5: pre-existing hook entries under same event are kept alongside new one
with tempfile.TemporaryDirectory() as td:
    feat, root = make_env(td)
    settings_path = os.path.join(root, ".claude", "settings.json")
    existing = {
        "hooks": {
            "Stop": [{"matcher": "*", "hooks": [{"type": "command",
                                                  "command": ".claude/hooks/other.py"}]}]
        }
    }
    with open(settings_path, "w") as f:
        json.dump(existing, f)
    publish_hook("Stop", "hooks/stop-check.py", feature_dir=feat, repo_root=root)
    data = json.loads(open(settings_path).read())
    stop_entries = data.get("hooks", {}).get("Stop", [])
    commands = [h["command"] for entry in stop_entries for h in entry.get("hooks", [])]
    if ".claude/hooks/other.py" not in commands:
        fail(f"t5: pre-existing hook entry was removed: {commands}")
    elif ".claude/hooks/stop-check.py" not in commands:
        fail(f"t5: new hook entry not added: {commands}")
    else:
        ok("t5: pre-existing hooks preserved; new hook added alongside")

# t6: hook registered under SessionStart event
with tempfile.TemporaryDirectory() as td:
    feat, root = make_env(td)
    publish_hook("SessionStart", "hooks/stop-check.py", feature_dir=feat, repo_root=root)
    settings_path = os.path.join(root, ".claude", "settings.json")
    data = json.loads(open(settings_path).read())
    ss_entries = data.get("hooks", {}).get("SessionStart", [])
    commands = [h["command"] for entry in ss_entries for h in entry.get("hooks", [])]
    if ".claude/hooks/stop-check.py" in commands:
        ok("t6: hook registered under SessionStart event")
    else:
        fail(f"t6: hook not registered under SessionStart: {commands}")

if FAIL:
    print("test-publish-hook: FAIL", file=sys.stderr)
    sys.exit(1)
print("test-publish-hook: all checks passed.")
```

- [ ] **Step 2: Run test to verify it fails**

```bash
python3 .claude/features/contract/test/test-publish-hook.py
```

Expected: `ImportError` for `publish_hook`.

- [ ] **Step 3: Append `publish_hook` to `lib/publish.py`**

Open `.claude/features/contract/lib/publish.py`. Append at the end:

```python


def publish_hook(event: str, source: str, matcher: str = "*", *,
                 feature_dir: str, repo_root: str) -> CheckResult:
    """Deploy a hook script to .claude/hooks/ and register it in .claude/settings.json.

    event   — Claude Code event: Stop | SessionStart | UserPromptSubmit | PreToolUse.
    source  — feature-dir-relative path, e.g. "hooks/stop-dispatcher.py".
    matcher — hook matcher pattern (default "*").

    Idempotent: re-running with unchanged hook file and already-registered command
    is a no-op. Existing settings.json fields are preserved (read-modify-write).
    """
    hook_name = Path(source).name
    hook_dest = f".claude/hooks/{hook_name}"
    result = publish_file(source, hook_dest, feature_dir=feature_dir, repo_root=repo_root)
    if not result.passed:
        return result

    settings_path = os.path.join(repo_root, ".claude", "settings.json")
    if os.path.isfile(settings_path):
        try:
            with open(settings_path) as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError):
            data = {}
    else:
        data = {}
    if not isinstance(data, dict):
        data = {}

    command = f".claude/hooks/{hook_name}"
    hooks_section = data.setdefault("hooks", {})
    event_entries = hooks_section.setdefault(event, [])
    for entry in event_entries:
        if any(h.get("command") == command for h in entry.get("hooks", [])):
            return CheckResult(True, [f"OK: {hook_dest} already registered under {event} (no-op)"])

    event_entries.append({"matcher": matcher,
                           "hooks": [{"type": "command", "command": command}]})
    os.makedirs(os.path.dirname(settings_path), exist_ok=True)
    with open(settings_path, "w") as f:
        json.dump(data, f, indent=2)
    return CheckResult(True, [f"OK: {hook_dest} deployed and registered under {event}"])
```

- [ ] **Step 4: Run test to verify it passes**

```bash
python3 .claude/features/contract/test/test-publish-hook.py
```

Expected: all PASS, exit 0.

- [ ] **Step 5: Wire into `run.py` and commit**

Add to `run.py` after `run_test("test-publish-skill-command-agent.py")`:

```python
run_test("test-publish-hook.py")
```

```bash
git add .claude/features/contract/lib/publish.py \
        .claude/features/contract/test/test-publish-hook.py \
        .claude/features/contract/test/run.py
git commit -m "feat(contract): publish_hook — deploy + settings.json registration

Idempotent: duplicate calls neither re-copy unchanged files nor
duplicate hook entries in settings.json. Pre-existing settings
fields and hook entries preserved via read-modify-write."
```

---

## Task 4: `publish_settings`

**Files:**
- Modify: `.claude/features/contract/lib/publish.py` (append `publish_settings`)
- Create: `.claude/features/contract/test/test-publish-settings.py`
- Modify: `.claude/features/contract/test/run.py`

- [ ] **Step 1: Write the failing test**

Create `.claude/features/contract/test/test-publish-settings.py`:

```python
#!/usr/bin/env python3
"""test-publish-settings.py — exercises publish_settings: idempotent copy of a
feature's settings.json source to .claude/settings.json.
"""

import json
import os
import sys
import tempfile

FEATURE_DIR = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, FEATURE_DIR)

from lib.publish import publish_settings  # noqa: E402

FAIL = 0


def fail(msg):
    global FAIL
    print(f"FAIL: {msg}", file=sys.stderr)
    FAIL = 1


def ok(msg):
    print(f"PASS: {msg}")


SAMPLE = {
    "env": {"RABBIT_REFRESH_EVERY": "20"},
    "permissions": {"allow": ["Bash(*)"]},
    "hooks": {"Stop": [{"matcher": "*",
                         "hooks": [{"type": "command", "command": ".claude/hooks/x.py"}]}]}
}

# t1: settings deployed to .claude/settings.json with correct content
with tempfile.TemporaryDirectory() as td:
    feat = os.path.join(td, "feature")
    root = os.path.join(td, "repo")
    os.makedirs(feat)
    os.makedirs(root)
    with open(os.path.join(feat, "settings.json"), "w") as f:
        json.dump(SAMPLE, f)
    r = publish_settings("settings.json", feature_dir=feat, repo_root=root)
    dest = os.path.join(root, ".claude", "settings.json")
    if not r.passed:
        fail(f"t1: publish_settings failed: {r.messages}")
    elif not os.path.isfile(dest):
        fail("t1: .claude/settings.json not created")
    else:
        data = json.load(open(dest))
        if data.get("env", {}).get("RABBIT_REFRESH_EVERY") == "20":
            ok("t1: settings.json deployed with correct content")
        else:
            fail(f"t1: content mismatch: {data}")

# t2: idempotent — same content reports no-op
with tempfile.TemporaryDirectory() as td:
    feat = os.path.join(td, "feature")
    root = os.path.join(td, "repo")
    os.makedirs(feat)
    os.makedirs(os.path.join(root, ".claude"))
    with open(os.path.join(feat, "settings.json"), "w") as f:
        json.dump(SAMPLE, f)
    dest = os.path.join(root, ".claude", "settings.json")
    with open(dest, "w") as f:
        json.dump(SAMPLE, f)
    r = publish_settings("settings.json", feature_dir=feat, repo_root=root)
    if not r.passed:
        fail(f"t2: idempotent call failed: {r.messages}")
    elif not any("no-op" in m.lower() for m in r.messages):
        fail(f"t2: idempotent should report no-op, got: {r.messages}")
    else:
        ok("t2: idempotent: same content returns no-op result")

# t3: missing source → passed=False
with tempfile.TemporaryDirectory() as td:
    feat = os.path.join(td, "feature")
    root = os.path.join(td, "repo")
    os.makedirs(feat)
    os.makedirs(root)
    r = publish_settings("settings.json", feature_dir=feat, repo_root=root)
    if r.passed:
        fail("t3: missing source should fail")
    else:
        ok("t3: missing source → passed=False")

# t4: drift — different content overwrites destination
with tempfile.TemporaryDirectory() as td:
    feat = os.path.join(td, "feature")
    root = os.path.join(td, "repo")
    os.makedirs(feat)
    os.makedirs(os.path.join(root, ".claude"))
    new_settings = dict(SAMPLE, env={"RABBIT_REFRESH_EVERY": "10"})
    with open(os.path.join(feat, "settings.json"), "w") as f:
        json.dump(new_settings, f)
    dest = os.path.join(root, ".claude", "settings.json")
    with open(dest, "w") as f:
        json.dump(SAMPLE, f)
    r = publish_settings("settings.json", feature_dir=feat, repo_root=root)
    if not r.passed:
        fail(f"t4: drift copy failed: {r.messages}")
    else:
        data = json.load(open(dest))
        if data.get("env", {}).get("RABBIT_REFRESH_EVERY") == "10":
            ok("t4: drift: updated source overwrites destination")
        else:
            fail(f"t4: destination not updated: {data}")

if FAIL:
    print("test-publish-settings: FAIL", file=sys.stderr)
    sys.exit(1)
print("test-publish-settings: all checks passed.")
```

- [ ] **Step 2: Run test to verify it fails**

```bash
python3 .claude/features/contract/test/test-publish-settings.py
```

Expected: `ImportError` for `publish_settings`.

- [ ] **Step 3: Append `publish_settings` to `lib/publish.py`**

Open `.claude/features/contract/lib/publish.py`. Append at the end:

```python


def publish_settings(source: str, *, feature_dir: str, repo_root: str) -> CheckResult:
    """Deploy the feature's settings.json to .claude/settings.json (idempotent).

    source — feature-dir-relative path to the settings JSON source file.
    Rabbit-cage-exclusive by design: only one feature should declare
    publish_settings in its MANIFEST. The library does not enforce exclusivity;
    the dispatcher enforces it.
    """
    return publish_file(source, ".claude/settings.json",
                        feature_dir=feature_dir, repo_root=repo_root)
```

- [ ] **Step 4: Run test to verify it passes**

```bash
python3 .claude/features/contract/test/test-publish-settings.py
```

Expected: all PASS, exit 0.

- [ ] **Step 5: Wire into `run.py` and commit**

Add to `run.py` after `run_test("test-publish-hook.py")`:

```python
run_test("test-publish-settings.py")
```

```bash
git add .claude/features/contract/lib/publish.py \
        .claude/features/contract/test/test-publish-settings.py \
        .claude/features/contract/test/run.py
git commit -m "feat(contract): publish_settings — idempotent settings.json deploy

Thin wrapper around publish_file. Rabbit-cage-exclusive by design;
exclusivity enforced by the dispatcher, not this library."
```

---

## Task 5: `publish_generated`

**Files:**
- Modify: `.claude/features/contract/lib/publish.py` (append `publish_generated`)
- Create: `.claude/features/contract/test/test-publish-generated.py`
- Modify: `.claude/features/contract/test/run.py`

- [ ] **Step 1: Write the failing test**

Create `.claude/features/contract/test/test-publish-generated.py`:

```python
#!/usr/bin/env python3
"""test-publish-generated.py — exercises publish_generated: invokes a named
content producer and writes its output to target (idempotent on content).

lib.producers is not yet written (Plan B.4). This test stubs it via
sys.modules injection BEFORE importing lib.publish so the lazy import inside
publish_generated resolves to the stub.
"""

import os
import sys
import tempfile
import types

FEATURE_DIR = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, FEATURE_DIR)

# Stub lib.producers BEFORE importing lib.publish.
_producers_stub = types.ModuleType("lib.producers")
_producers_stub.call_producer = lambda name, args, feature_dir, repo_root: f"# generated by {name}\n"
if "lib" not in sys.modules:
    sys.modules["lib"] = types.ModuleType("lib")
sys.modules["lib.producers"] = _producers_stub

from lib.publish import publish_generated  # noqa: E402

FAIL = 0


def fail(msg):
    global FAIL
    print(f"FAIL: {msg}", file=sys.stderr)
    FAIL = 1


def ok(msg):
    print(f"PASS: {msg}")


# t1: producer invoked and output written to target
with tempfile.TemporaryDirectory() as td:
    feat = os.path.join(td, "feature")
    root = os.path.join(td, "repo")
    os.makedirs(feat)
    os.makedirs(root)
    r = publish_generated(
        "CLAUDE.md",
        "generate-claude-md",
        {"policy_source": ".claude/features/policy/"},
        feature_dir=feat,
        repo_root=root,
    )
    target = os.path.join(root, "CLAUDE.md")
    if not r.passed:
        fail(f"t1: publish_generated failed: {r.messages}")
    elif not os.path.isfile(target):
        fail("t1: target file not created")
    elif open(target).read() != "# generated by generate-claude-md\n":
        fail(f"t1: target content mismatch: {open(target).read()!r}")
    else:
        ok("t1: producer invoked and output written to target")

# t2: idempotent — same content reports no-op
with tempfile.TemporaryDirectory() as td:
    feat = os.path.join(td, "feature")
    root = os.path.join(td, "repo")
    os.makedirs(feat)
    os.makedirs(root)
    target = os.path.join(root, "CLAUDE.md")
    with open(target, "w") as f:
        f.write("# generated by generate-claude-md\n")
    r = publish_generated("CLAUDE.md", "generate-claude-md", {}, feature_dir=feat, repo_root=root)
    if not r.passed:
        fail(f"t2: idempotent call failed: {r.messages}")
    elif not any("no-op" in m.lower() for m in r.messages):
        fail(f"t2: idempotent should report no-op, got: {r.messages}")
    else:
        ok("t2: idempotent: same content returns no-op result")

# t3: drift — different existing content is overwritten
with tempfile.TemporaryDirectory() as td:
    feat = os.path.join(td, "feature")
    root = os.path.join(td, "repo")
    os.makedirs(feat)
    os.makedirs(root)
    target = os.path.join(root, "CLAUDE.md")
    with open(target, "w") as f:
        f.write("old content\n")
    r = publish_generated("CLAUDE.md", "generate-claude-md", {}, feature_dir=feat, repo_root=root)
    if not r.passed:
        fail(f"t3: drift update failed: {r.messages}")
    elif open(target).read() != "# generated by generate-claude-md\n":
        fail("t3: drift update did not replace content")
    else:
        ok("t3: drift: different existing content is overwritten")

# t4: producer name and args passed through correctly
call_log = []


def _logging_producer(name, args, feature_dir, repo_root):
    call_log.append({"name": name, "args": args})
    return "x"


_producers_stub.call_producer = _logging_producer
with tempfile.TemporaryDirectory() as td:
    feat = os.path.join(td, "feature")
    root = os.path.join(td, "repo")
    os.makedirs(feat)
    os.makedirs(root)
    publish_generated("CLAUDE.md", "my-producer", {"k": "v"}, feature_dir=feat, repo_root=root)
    if call_log and call_log[0]["name"] == "my-producer" and call_log[0]["args"] == {"k": "v"}:
        ok("t4: producer name and args passed through correctly")
    else:
        fail(f"t4: unexpected call log: {call_log}")

# t5: target parent directories created automatically
_producers_stub.call_producer = lambda name, args, feature_dir, repo_root: "content"
with tempfile.TemporaryDirectory() as td:
    feat = os.path.join(td, "feature")
    root = os.path.join(td, "repo")
    os.makedirs(feat)
    os.makedirs(root)
    r = publish_generated("a/b/c/output.md", "read-file", {}, feature_dir=feat, repo_root=root)
    if not r.passed:
        fail(f"t5: deep target failed: {r.messages}")
    elif not os.path.isfile(os.path.join(root, "a", "b", "c", "output.md")):
        fail("t5: deep target not created")
    else:
        ok("t5: target parent directories created automatically")

if FAIL:
    print("test-publish-generated: FAIL", file=sys.stderr)
    sys.exit(1)
print("test-publish-generated: all checks passed.")
```

- [ ] **Step 2: Run test to verify it fails**

```bash
python3 .claude/features/contract/test/test-publish-generated.py
```

Expected: `ImportError` for `publish_generated`.

- [ ] **Step 3: Append `publish_generated` to `lib/publish.py`**

Open `.claude/features/contract/lib/publish.py`. Append at the end:

```python


def publish_generated(target: str, producer: str, args: dict, *,
                      feature_dir: str, repo_root: str) -> CheckResult:
    """Invoke a named content producer and write its output to target (idempotent).

    target   — repo-root-relative path to write, e.g. "CLAUDE.md".
    producer — producer name resolved via lib.producers.call_producer (Plan B.4).
    args     — arguments forwarded to the producer function.

    Late-imports lib.producers so this module is importable before B.4 lands.
    Returns CheckResult(passed=False) if lib.producers is unavailable.
    """
    try:
        from lib import producers  # noqa: PLC0415
        content = producers.call_producer(producer, args,
                                          feature_dir=feature_dir, repo_root=repo_root)
    except (ImportError, AttributeError) as e:
        return CheckResult(False, [f"ERROR: lib.producers unavailable: {e}"])

    target_path = os.path.join(repo_root, target)
    current = ""
    if os.path.isfile(target_path):
        with open(target_path) as f:
            current = f.read()
    if content == current:
        return CheckResult(True, [f"OK: {target} unchanged (no-op)"])
    target_dir = os.path.dirname(target_path)
    if target_dir:
        os.makedirs(target_dir, exist_ok=True)
    with open(target_path, "w") as f:
        f.write(content)
    return CheckResult(True, [f"OK: {target} generated via {producer}"])
```

- [ ] **Step 4: Run test to verify it passes**

```bash
python3 .claude/features/contract/test/test-publish-generated.py
```

Expected: all PASS, exit 0.

- [ ] **Step 5: Wire into `run.py`, run full suite, and commit**

Add to `run.py` after `run_test("test-publish-settings.py")`:

```python
run_test("test-publish-generated.py")
```

Run the full suite:

```bash
python3 .claude/features/contract/test/run.py
```

Expected: ALL TESTS PASSED.

```bash
git add .claude/features/contract/lib/publish.py \
        .claude/features/contract/test/test-publish-generated.py \
        .claude/features/contract/test/run.py
git commit -m "feat(contract): publish_generated — invoke producer + write target

Late-imports lib.producers (Plan B.4) so this module is importable
before producers.py exists. Idempotent on content equality."
```

---

## Task 6: Spec invariant 44 + version bump + contract.md update

**Files:**
- Modify: `.claude/features/contract/docs/spec/spec.md`
- Modify: `.claude/features/contract/feature.json`
- Modify: `.claude/features/contract/docs/spec/contract.md`

- [ ] **Step 1: Check the current version and last invariant number**

```bash
head -10 .claude/features/contract/docs/spec/spec.md
grep -c "^[0-9]\+\." .claude/features/contract/docs/spec/spec.md
```

Expected: frontmatter shows `version: 1.22.0`; last numbered invariant is 43. Verify before editing.

- [ ] **Step 2: Add invariant 44 to `spec.md`**

Open `.claude/features/contract/docs/spec/spec.md`. After invariant 43 (the final `validate_meta_contract` invariant), append:

```markdown

44. **`contract.lib.publish` API library (Plan B.1).** `.claude/features/contract/lib/publish.py` MUST export seven publish API functions: `publish_file`, `publish_skill`, `publish_command`, `publish_agent`, `publish_hook`, `publish_settings`, `publish_generated`. Each accepts API args as explicit params plus keyword-only context params `feature_dir` and `repo_root`, and returns `CheckResult` from `lib.checks`. All functions are idempotent: re-running with unchanged source is a no-op (SHA-256 comparison for file-copy operations; content-equality check for generated content). `publish_hook` additionally reads/writes `.claude/settings.json` via read-modify-write, preserving all existing fields, and is idempotent on the hook command registration. `publish_generated` late-imports `lib.producers` (Plan B.4) so the module is importable before `lib/producers.py` exists, returning `CheckResult(passed=False)` if producers is unavailable. Coverage enforced by `test/test-publish-{file,skill-command-agent,hook,settings,generated}.py`.
```

- [ ] **Step 3: Bump version in `spec.md` frontmatter**

In the YAML frontmatter at the top of `spec.md`, change `version: 1.22.0` to `version: 1.23.0`.

- [ ] **Step 4: Bump version in `feature.json`**

Open `.claude/features/contract/feature.json`. Change `"version": "1.22.0"` to `"version": "1.23.0"`.

- [ ] **Step 5: Add `lib/publish.py` to `contract.md` provides section**

Open `.claude/features/contract/docs/spec/contract.md`. In the JSON block's `provides.lib` array, add after `".claude/features/contract/lib/checks.py"`:

```json
".claude/features/contract/lib/publish.py"
```

- [ ] **Step 6: Run full test suite**

```bash
python3 .claude/features/contract/test/run.py
```

Expected: ALL TESTS PASSED. The `test-check-invariant-monotonic-order` test validates 44 follows 43.

- [ ] **Step 7: Commit**

```bash
git add .claude/features/contract/docs/spec/spec.md \
        .claude/features/contract/feature.json \
        .claude/features/contract/docs/spec/contract.md
git commit -m "docs(contract): invariant 44 + version 1.23.0 for lib/publish.py

Documents the seven publish API functions, their idempotency guarantee,
and publish_hook's read-modify-write settings.json behavior.
Adds lib/publish.py to contract.md provides section."
```

---

## Plan complete — verification checklist

- [ ] `python3 .claude/features/contract/test/run.py` exits 0
- [ ] `git log --oneline -6` shows 6 B.1 commits on `feature/meta-contract-api-libraries`
- [ ] `python3 .claude/features/contract/scripts/validate-meta-contract.py .claude/features/contract` exits 0
- [ ] Spot-check `publish_file` idempotency end-to-end:

```bash
python3 - <<'EOF'
import sys, tempfile, os, shutil
sys.path.insert(0, ".claude/features/contract")
from lib.publish import publish_file

with tempfile.TemporaryDirectory() as td:
    shutil.copy(".claude/features/contract/feature.json", os.path.join(td, "feature.json"))
    r1 = publish_file("feature.json", "out/feature.json", feature_dir=td, repo_root=td)
    r2 = publish_file("feature.json", "out/feature.json", feature_dir=td, repo_root=td)
    print("first:", r1.passed, r1.messages)
    print("second:", r2.passed, r2.messages)
    assert "no-op" in r2.messages[0].lower(), "second call must be no-op"
    print("OK: idempotency verified")
EOF
```

Expected: first call prints `True ['OK: out/feature.json published']`, second prints `True ['OK: out/feature.json unchanged (no-op)']`.

---

## What this plan does NOT cover

Deferred to other B.x sub-plans:
- **B.2** — `contract.lib.runtime` (8 runtime API functions + `RuntimeReturn` type)
- **B.3** — `contract.lib.mutation` (7 mutation API functions + JSON-path helpers)
- **B.4** — `contract.lib.producers` (3 content producer functions + `call_producer` dispatcher)

After all four B.x sub-plans land, Plan C rewrites the rabbit-cage dispatcher to consume the four API libraries.
