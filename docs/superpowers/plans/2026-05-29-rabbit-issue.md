# rabbit-issue Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace `rabbit-file` (custom B/B branch-backed system) with `rabbit-issue` (thin wrapper over `gh` CLI against GitHub Issues), migrate existing items, and retire the old feature + branch.

**Architecture:** New feature `.claude/features/rabbit-issue/` provides scripts that wrap `gh issue create/view/close/reopen/list`. Type taxonomy maps to GH-default labels (`bug`, `enhancement`); rabbit governance labels (`rabbit-managed`, `feature:<name>`, `priority:<level>`) layer on top. A one-shot `migrate.py` copies open items to GH Issues and closed items to `archive/bug-backlog/<feature>/`, then the dedicated branch is deleted and the old feature directory removed.

**Tech Stack:** Python 3, `gh` CLI v2.x (already at v2.69), pytest, git.

**Spec:** `docs/superpowers/specs/2026-05-29-rabbit-issue-design.md`

---

## File Structure

**New feature:**
```
.claude/features/rabbit-issue/
├── feature.json                              # metadata + manifest
├── docs/spec/
│   ├── spec.md                               # full spec, frontmatter
│   └── contract.md                           # JSON contract, frontmatter
├── skills/rabbit-issue/
│   └── SKILL.md                              # Work Protocol
├── scripts/
│   ├── file-item.py                          # ~40 lines
│   ├── item-status.py                        # ~50 lines
│   ├── list-items.py                         # ~30 lines
│   ├── _gh.py                                # shared: ensure_labels, repo_slug, require_managed
│   └── migrate.py                            # ~100 lines (one-shot, deleted post-cutover)
└── test/
    ├── run.py                                # test runner
    ├── conftest.py                           # gh shim fixture
    ├── gh_shim.sh                            # mock gh binary
    ├── test-file-item.py
    ├── test-item-status.py
    ├── test-list-items.py
    ├── test-ensure-labels.py
    ├── test-rabbit-managed-guard.py
    ├── test-migrate-dry-run.py
    ├── test-migrate-real.py
    ├── test-migrate-idempotent.py
    ├── test-spec-presence.py
    ├── test-prompts-declared.py
    └── test-manifest-shape.py
```

**Cross-feature touches:**
- `.claude/features/rabbit-feature/skills/rabbit-feature-touch/SKILL.md` — rename "B/B mode" → "issue mode", update fetch protocol (gh issue view instead of git show)
- `.claude/features/rabbit-feature/docs/spec/spec.md` — same renames
- `.claude/features/rabbit-feature/test/test-touch-skill.py` — update assertions
- `.claude/agents/tdd-subagent/scripts/dispatch-tdd-subagent.py` — if it references rabbit-file paths

**Migration artifacts:**
```
archive/
├── bug-backlog/<feature>/<RABBIT-...-N>.json    # closed items
└── migration-manifest.json                       # old↔new ID mapping
```

**Deleted post-cutover:**
- `.claude/features/rabbit-file/` (entire directory)
- `origin/bug-backlog-files` (remote branch)
- `.claude/features/rabbit-issue/scripts/migrate.py` (one-shot)

---

## Phase 1 — Scaffold rabbit-issue feature

### Task 1: Create feature dir + minimal feature.json

**Files:**
- Create: `.claude/features/rabbit-issue/feature.json`

**Note on scope guard:** Writes to `.claude/features/` require a `rabbit-feature-touch` cycle OR a `.rabbit-scope-override` marker. For this plan's execution, recommend using **session override** at the start (`echo "session" > .rabbit-scope-override`) and removing it at the very end. Each task below assumes the override is in place.

- [ ] **Step 1: Create feature.json**

```bash
mkdir -p .claude/features/rabbit-issue/{docs/spec,skills/rabbit-issue,scripts,test}
```

```json
{
  "name": "rabbit-issue",
  "version": "0.1.0",
  "owner": "cyxu",
  "tdd_state": "spec-pending",
  "summary": "GitHub Issues wrapper for filing/tracking/closing bugs and enhancements. Replaces rabbit-file (which used a custom origin/bug-backlog-files branch).",
  "surface": {
    "hooks": [],
    "commands": [],
    "agents": [],
    "skills": ["rabbit-issue"],
    "scripts": [
      "scripts/file-item.py",
      "scripts/item-status.py",
      "scripts/list-items.py",
      "scripts/_gh.py",
      "scripts/migrate.py"
    ]
  },
  "deprecation_criterion": "when GH Issues is replaced or the workflow moves to a different tracker; revisit when claude-plugins-official ships a GH Issues skill",
  "updated": "2026-05-29",
  "manifest": [
    {
      "api": "publish_skill",
      "args": {"source": "skills/rabbit-issue/SKILL.md"}
    }
  ],
  "runtime": {},
  "configuration": [],
  "prompts": [
    {
      "id": "rabbit-issue",
      "kind": "skill",
      "inject": [
        ".claude/features/policy/philosophy.md",
        ".claude/features/policy/coding-rules.md"
      ],
      "slots": ["args"]
    }
  ]
}
```

- [ ] **Step 2: Commit**

```bash
git add .claude/features/rabbit-issue/feature.json
git commit -m "feat(rabbit-issue): scaffold feature.json"
```

---

### Task 2: Write spec.md

**Files:**
- Create: `.claude/features/rabbit-issue/docs/spec/spec.md`

- [ ] **Step 1: Write spec.md** (source the design doc; condense to spec form)

```markdown
---
feature: rabbit-issue
version: 1.0.0
owner: cyxu
deprecation_criterion: when GH Issues is replaced or the workflow moves to a different tracker
---

# rabbit-issue — Spec

## Purpose

Wrap `gh` CLI to provide rabbit's file/work/list/show operations against
GitHub Issues. Replaces rabbit-file's branch-backed B/B system.

## Surface

Three runtime scripts at `.claude/features/rabbit-issue/scripts/`:

- `file-item.py` — file a new issue
- `item-status.py` — show / close / reopen an issue
- `list-items.py` — list issues with filters

Plus a one-shot `migrate.py` (retired after cutover) and shared helper
`_gh.py`.

## Label schema

| Label | Purpose | Required? |
|---|---|---|
| `bug` *(GH default)* | Type — exclusive with `enhancement` | exactly one of bug/enhancement |
| `enhancement` *(GH default)* | Type — exclusive with `bug` | exactly one of bug/enhancement |
| `rabbit-managed` | Distinguishes rabbit-filed from human-filed | yes |
| `feature:<name>` | Feature scope | yes |
| `priority:<low\|medium\|high\|critical>` | Priority | yes |

Labels are auto-created on first `file-item.py` call via idempotent
`gh label create … || true`.

## Safety invariant

`item-status.py close` and `item-status.py reopen` refuse to act on
issues that lack the `rabbit-managed` label. Human-filed issues stay
out of rabbit's reach unless explicitly opted in.

## Lifecycle

- `state` is GH's binary `open` / `closed`
- `state_reason` ∈ {`completed`, `not_planned`, null}
  - `completed` — closed after TDD fix (default close reason)
  - `not_planned` — closed without work (stale/invalid)
- Reopen restores `state = open`, `state_reason = reopened`

## SHA / event history

Delegated entirely to GitHub Timeline API. No local `history` array.
Closing-reference (`Fixes #N` in commit messages) auto-links commits to
issue closure.

## Repository discovery

Repo slug derived at runtime from `git remote get-url origin`. All
scripts fail loudly with actionable error if `gh auth status` is not
green or the remote is not a GitHub URL.

## Out of scope

- GH Projects v2 boards (sub-statuses)
- User-install plugin-mode backend (deferred)
- Cross-tracker abstractions (Linear/Jira)
```

- [ ] **Step 2: Commit**

```bash
git add .claude/features/rabbit-issue/docs/spec/spec.md
git commit -m "feat(rabbit-issue): write spec.md"
```

---

### Task 3: Write contract.md

**Files:**
- Create: `.claude/features/rabbit-issue/docs/spec/contract.md`

- [ ] **Step 1: Write contract.md**

````markdown
---
feature: rabbit-issue
version: 1.0.0
owner: cyxu
deprecation_criterion: when GH Issues is replaced or the workflow moves to a different tracker
---

# rabbit-issue — Contract

```json
{
  "provides": {
    "skill": "rabbit-issue",
    "scripts": [
      "scripts/file-item.py",
      "scripts/item-status.py",
      "scripts/list-items.py"
    ],
    "issue_labels": [
      "bug",
      "enhancement",
      "rabbit-managed",
      "feature:<name>",
      "priority:<low|medium|high|critical>"
    ]
  },
  "reads": {
    "feature.json": "via rabbit-feature-scope (for --feature validation)",
    "github_issues": "via gh CLI, repo slug from `git remote get-url origin`"
  },
  "invokes": {
    "rabbit-feature-scope": "skill — resolve feature for ambiguous filings",
    "gh": "CLI tool — issue create/view/close/reopen/list, label create"
  },
  "never": [
    "writes to origin/bug-backlog-files (deleted by migration)",
    "maintains counter.json (GH allocates issue numbers)",
    "maintains item.json history array (GH Timeline is source of truth)",
    "closes/reopens issues lacking the `rabbit-managed` label"
  ]
}
```
````

- [ ] **Step 2: Commit**

```bash
git add .claude/features/rabbit-issue/docs/spec/contract.md
git commit -m "feat(rabbit-issue): write contract.md"
```

---

### Task 4: Test infrastructure — gh shim + conftest + run.py

**Files:**
- Create: `.claude/features/rabbit-issue/test/gh_shim.sh`
- Create: `.claude/features/rabbit-issue/test/conftest.py`
- Create: `.claude/features/rabbit-issue/test/run.py`

- [ ] **Step 1: Write gh shim**

```bash
#!/usr/bin/env bash
# .claude/features/rabbit-issue/test/gh_shim.sh
# Mock `gh` CLI for tests. Records args to $GH_SHIM_LOG.
# Returns canned responses from $GH_SHIM_RESPONSE_<SUBCOMMAND>_<VERB> or default.

set -e
LOG="${GH_SHIM_LOG:-/tmp/gh_shim.log}"
echo "$@" >> "$LOG"

case "$1 $2" in
  "issue create")
    # canned issue number = 9001 unless overridden
    NUM="${GH_SHIM_ISSUE_NUMBER:-9001}"
    echo "https://github.com/test/repo/issues/$NUM"
    ;;
  "issue view")
    NUM="$3"
    if [ -n "$GH_SHIM_ISSUE_BODY" ]; then
      cat "$GH_SHIM_ISSUE_BODY"
    else
      echo "{\"number\":$NUM,\"title\":\"test\",\"state\":\"open\",\"labels\":[{\"name\":\"rabbit-managed\"},{\"name\":\"bug\"},{\"name\":\"feature:test\"},{\"name\":\"priority:high\"}],\"body\":\"...\"}"
    fi
    ;;
  "issue close"|"issue reopen")
    echo "OK"
    ;;
  "issue list")
    if [ -n "$GH_SHIM_LIST_RESPONSE" ]; then
      cat "$GH_SHIM_LIST_RESPONSE"
    else
      echo "[]"
    fi
    ;;
  "label create")
    # may exit 1 on duplicate; let env control it
    exit "${GH_SHIM_LABEL_CREATE_EXIT:-0}"
    ;;
  "auth status")
    exit "${GH_SHIM_AUTH_EXIT:-0}"
    ;;
  *)
    echo "gh_shim: unknown subcommand: $@" >&2
    exit 99
    ;;
esac
```

```bash
chmod +x .claude/features/rabbit-issue/test/gh_shim.sh
```

- [ ] **Step 2: Write conftest.py**

```python
# .claude/features/rabbit-issue/test/conftest.py
import os, tempfile, shutil
from pathlib import Path
import pytest

TEST_DIR = Path(__file__).parent
SHIM = TEST_DIR / "gh_shim.sh"

@pytest.fixture
def gh_shim(monkeypatch, tmp_path):
    """Put gh_shim.sh on PATH as `gh`. Returns the log path."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    (bin_dir / "gh").symlink_to(SHIM)
    log = tmp_path / "gh.log"
    log.write_text("")
    monkeypatch.setenv("PATH", f"{bin_dir}:{os.environ['PATH']}")
    monkeypatch.setenv("GH_SHIM_LOG", str(log))
    return log

@pytest.fixture
def fake_repo(monkeypatch, tmp_path):
    """A throwaway git repo with origin set to a fake GH URL."""
    import subprocess
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "-C", str(repo), "init", "-q"], check=True)
    subprocess.run(["git", "-C", str(repo), "remote", "add", "origin",
                    "https://github.com/test/repo.git"], check=True)
    monkeypatch.chdir(repo)
    return repo
```

- [ ] **Step 3: Write run.py**

```python
#!/usr/bin/env python3
"""rabbit-issue test runner"""
import subprocess, sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent

def run_pytest_suite(script):
    print(f"=== {script} ===")
    result = subprocess.run([sys.executable, "-m", "pytest",
                             str(SCRIPT_DIR / script), "-v"])
    print()
    return result.returncode == 0

def run_suite(script):
    print(f"=== {script} ===")
    result = subprocess.run([sys.executable, str(SCRIPT_DIR / script)])
    print()
    return result.returncode == 0

SUITES = [
    ("pytest", "test-file-item.py"),
    ("pytest", "test-item-status.py"),
    ("pytest", "test-list-items.py"),
    ("pytest", "test-ensure-labels.py"),
    ("pytest", "test-rabbit-managed-guard.py"),
    ("pytest", "test-migrate-dry-run.py"),
    ("pytest", "test-migrate-real.py"),
    ("pytest", "test-migrate-idempotent.py"),
    ("py",     "test-spec-presence.py"),
    ("py",     "test-prompts-declared.py"),
    ("py",     "test-manifest-shape.py"),
]

print("rabbit-issue test runner\n")
fail = 0
for kind, script in SUITES:
    fn = run_pytest_suite if kind == "pytest" else run_suite
    if not fn(script):
        fail += 1
print(f"\n{'PASS' if fail == 0 else f'FAIL ({fail} suites)'}")
sys.exit(0 if fail == 0 else 1)
```

- [ ] **Step 4: Commit**

```bash
git add .claude/features/rabbit-issue/test/
git commit -m "feat(rabbit-issue): test infrastructure (gh shim, conftest, run.py)"
```

---

## Phase 2 — TDD build runtime scripts

### Task 5: TDD — `_gh.py` shared helpers

**Files:**
- Create: `.claude/features/rabbit-issue/scripts/_gh.py`
- Test: `.claude/features/rabbit-issue/test/test-ensure-labels.py`

- [ ] **Step 1: Write the failing test**

```python
# test-ensure-labels.py
import sys, subprocess, json
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

def test_repo_slug_from_https_remote(fake_repo, gh_shim):
    from _gh import repo_slug
    assert repo_slug() == "test/repo"

def test_repo_slug_from_ssh_remote(monkeypatch, fake_repo, gh_shim):
    subprocess.run(["git", "remote", "set-url", "origin",
                    "git@github.com:org/repo.git"], check=True)
    from _gh import repo_slug
    # may need fresh import; remove from sys.modules if cached
    import importlib, _gh; importlib.reload(_gh)
    assert _gh.repo_slug() == "org/repo"

def test_ensure_labels_calls_gh_label_create(gh_shim, fake_repo):
    import importlib
    sys.modules.pop("_gh", None)
    import _gh
    _gh.ensure_labels(["bug", "rabbit-managed", "feature:foo", "priority:high"])
    log = gh_shim.read_text().strip().split("\n")
    # Should have 4 label create calls
    creates = [l for l in log if l.startswith("label create")]
    assert len(creates) == 4

def test_ensure_labels_idempotent_on_duplicate(gh_shim, fake_repo, monkeypatch):
    monkeypatch.setenv("GH_SHIM_LABEL_CREATE_EXIT", "1")
    import importlib, _gh; importlib.reload(_gh)
    # Should NOT raise even though gh exits 1
    _gh.ensure_labels(["bug"])

def test_require_managed_raises_on_unmanaged(gh_shim, fake_repo, tmp_path, monkeypatch):
    body = tmp_path / "issue.json"
    body.write_text(json.dumps({"number": 1, "labels": [{"name": "bug"}]}))
    monkeypatch.setenv("GH_SHIM_ISSUE_BODY", str(body))
    import importlib, _gh; importlib.reload(_gh)
    import pytest
    with pytest.raises(SystemExit):
        _gh.require_managed(1)

def test_require_managed_passes_when_label_present(gh_shim, fake_repo, tmp_path, monkeypatch):
    body = tmp_path / "issue.json"
    body.write_text(json.dumps({"number": 1, "labels": [
        {"name": "bug"}, {"name": "rabbit-managed"}]}))
    monkeypatch.setenv("GH_SHIM_ISSUE_BODY", str(body))
    import importlib, _gh; importlib.reload(_gh)
    _gh.require_managed(1)  # no exception
```

- [ ] **Step 2: Run test to verify it fails**

```bash
python3 -m pytest .claude/features/rabbit-issue/test/test-ensure-labels.py -v
```
Expected: FAIL with `ModuleNotFoundError: No module named '_gh'`

- [ ] **Step 3: Implement `_gh.py`**

```python
# .claude/features/rabbit-issue/scripts/_gh.py
"""
Shared helpers for rabbit-issue scripts.

Version: 1.0.0
Owner: cyxu
Deprecation criterion: when rabbit-issue is retired
"""
import json, re, subprocess, sys

def repo_slug() -> str:
    """Return 'owner/repo' from `git remote get-url origin`."""
    url = subprocess.check_output(
        ["git", "remote", "get-url", "origin"], text=True).strip()
    m = re.match(r"^(?:https://github\.com/|git@github\.com:)([^/]+)/(.+?)(?:\.git)?$", url)
    if not m:
        sys.exit(f"rabbit-issue: origin is not a GitHub URL: {url}")
    return f"{m.group(1)}/{m.group(2)}"

def ensure_labels(labels: list[str]) -> None:
    """Create labels on the repo; idempotent (ignores 'already exists')."""
    slug = repo_slug()
    for label in labels:
        subprocess.run(
            ["gh", "label", "create", label, "-R", slug],
            capture_output=True, text=True)
        # ignore non-zero exit — gh returns 1 on duplicate

def gh_issue_view(number: int, fields: str = "number,title,state,labels,body") -> dict:
    """Return parsed issue JSON for issue #number."""
    out = subprocess.check_output(
        ["gh", "issue", "view", str(number), "-R", repo_slug(),
         "--json", fields], text=True)
    return json.loads(out)

def require_managed(number: int) -> None:
    """Exit with error if the issue lacks the rabbit-managed label."""
    issue = gh_issue_view(number, "number,labels")
    labels = {l["name"] for l in issue.get("labels", [])}
    if "rabbit-managed" not in labels:
        sys.exit(f"rabbit-issue: #{number} lacks `rabbit-managed` label; refusing to act")

def require_auth() -> None:
    """Exit if `gh auth status` fails."""
    r = subprocess.run(["gh", "auth", "status"], capture_output=True)
    if r.returncode != 0:
        sys.exit("rabbit-issue: `gh auth status` failed — run `gh auth login`")
```

- [ ] **Step 4: Run test to verify it passes**

```bash
python3 -m pytest .claude/features/rabbit-issue/test/test-ensure-labels.py -v
```
Expected: 6 passed

- [ ] **Step 5: Commit**

```bash
git add .claude/features/rabbit-issue/scripts/_gh.py \
        .claude/features/rabbit-issue/test/test-ensure-labels.py
git commit -m "feat(rabbit-issue): _gh.py helpers + label-bootstrap tests"
```

---

### Task 6: TDD — `file-item.py`

**Files:**
- Create: `.claude/features/rabbit-issue/scripts/file-item.py`
- Test: `.claude/features/rabbit-issue/test/test-file-item.py`

- [ ] **Step 1: Write the failing test**

```python
# test-file-item.py
import sys, subprocess, json
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
FILE_ITEM = SCRIPTS / "file-item.py"

def run_file_item(*args, env=None):
    r = subprocess.run(
        [sys.executable, str(FILE_ITEM), *args],
        capture_output=True, text=True, env=env)
    return r

def test_file_bug_creates_gh_issue(gh_shim, fake_repo, monkeypatch):
    env = {**__import__("os").environ}
    r = run_file_item(
        "--type", "bug",
        "--feature", "rabbit-cage",
        "--title", "login button broken on Safari",
        "--priority", "high",
        "--description", "steps: …",
        env=env)
    assert r.returncode == 0, r.stderr
    out = json.loads(r.stdout)
    assert out["number"] == 9001
    assert out["type"] == "bug"
    # gh shim log should include the create call with correct labels
    log = gh_shim.read_text()
    assert "issue create" in log
    assert "--label bug,rabbit-managed,feature:rabbit-cage,priority:high" in log \
        or all(lbl in log for lbl in ["bug", "rabbit-managed",
                                       "feature:rabbit-cage", "priority:high"])

def test_file_enhancement_uses_enhancement_label(gh_shim, fake_repo):
    r = run_file_item("--type", "enhancement", "--feature", "x",
                      "--title", "t", "--priority", "low", "--description", "d")
    assert r.returncode == 0
    assert "enhancement" in gh_shim.read_text()

def test_rejects_invalid_type(gh_shim, fake_repo):
    r = run_file_item("--type", "feature", "--feature", "x",
                      "--title", "t", "--priority", "low", "--description", "d")
    assert r.returncode != 0
    assert "type" in r.stderr.lower()

def test_rejects_invalid_priority(gh_shim, fake_repo):
    r = run_file_item("--type", "bug", "--feature", "x",
                      "--title", "t", "--priority", "urgent", "--description", "d")
    assert r.returncode != 0

def test_ensure_labels_called_before_create(gh_shim, fake_repo):
    run_file_item("--type", "bug", "--feature", "x",
                  "--title", "t", "--priority", "low", "--description", "d")
    log = gh_shim.read_text().split("\n")
    # `label create` should appear before `issue create`
    label_idx = next(i for i, l in enumerate(log) if l.startswith("label create"))
    issue_idx = next(i for i, l in enumerate(log) if l.startswith("issue create"))
    assert label_idx < issue_idx
```

- [ ] **Step 2: Run test to verify it fails**

```bash
python3 -m pytest .claude/features/rabbit-issue/test/test-file-item.py -v
```
Expected: FAIL (file-item.py doesn't exist)

- [ ] **Step 3: Implement file-item.py**

```python
#!/usr/bin/env python3
"""
rabbit-issue: file a new bug or enhancement on GitHub Issues.

Version: 1.0.0
Owner: cyxu
Deprecation criterion: when rabbit-issue is retired
"""
import argparse, json, subprocess, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _gh import ensure_labels, repo_slug, require_auth

VALID_TYPES = ("bug", "enhancement")
VALID_PRIORITIES = ("low", "medium", "high", "critical")

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--type", required=True, choices=VALID_TYPES)
    p.add_argument("--feature", required=True)
    p.add_argument("--title", required=True)
    p.add_argument("--priority", required=True, choices=VALID_PRIORITIES)
    p.add_argument("--description", required=True)
    args = p.parse_args()

    require_auth()
    labels = [args.type, "rabbit-managed",
              f"feature:{args.feature}", f"priority:{args.priority}"]
    ensure_labels(labels)

    slug = repo_slug()
    out = subprocess.check_output([
        "gh", "issue", "create", "-R", slug,
        "--title", args.title,
        "--body", args.description,
        "--label", ",".join(labels),
    ], text=True).strip()
    # gh prints URL: https://github.com/owner/repo/issues/N
    number = int(out.rsplit("/", 1)[-1])
    print(json.dumps({"number": number, "url": out, "type": args.type}))

if __name__ == "__main__":
    main()
```

```bash
chmod +x .claude/features/rabbit-issue/scripts/file-item.py
```

- [ ] **Step 4: Run test to verify it passes**

```bash
python3 -m pytest .claude/features/rabbit-issue/test/test-file-item.py -v
```
Expected: 5 passed

- [ ] **Step 5: Commit**

```bash
git add .claude/features/rabbit-issue/scripts/file-item.py \
        .claude/features/rabbit-issue/test/test-file-item.py
git commit -m "feat(rabbit-issue): file-item.py + tests"
```

---

### Task 7: TDD — `item-status.py`

**Files:**
- Create: `.claude/features/rabbit-issue/scripts/item-status.py`
- Test: `.claude/features/rabbit-issue/test/test-item-status.py`

- [ ] **Step 1: Write the failing test**

```python
# test-item-status.py
import sys, subprocess, json
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
ITEM_STATUS = SCRIPTS / "item-status.py"

def run_cmd(*args):
    return subprocess.run([sys.executable, str(ITEM_STATUS), *args],
                          capture_output=True, text=True)

def test_show_prints_issue_json(gh_shim, fake_repo):
    r = run_cmd("show", "42")
    assert r.returncode == 0
    out = json.loads(r.stdout)
    assert out["number"] == 42

def test_close_with_completed_reason(gh_shim, fake_repo):
    r = run_cmd("close", "42", "--reason", "completed",
                "--comment", "fixed in #99")
    assert r.returncode == 0
    log = gh_shim.read_text()
    assert "issue close" in log
    assert "--reason completed" in log

def test_close_with_not_planned_reason(gh_shim, fake_repo):
    r = run_cmd("close", "42", "--reason", "not-planned")
    assert r.returncode == 0
    assert "not-planned" in gh_shim.read_text()

def test_close_rejects_unknown_reason(gh_shim, fake_repo):
    r = run_cmd("close", "42", "--reason", "wontfix")
    assert r.returncode != 0

def test_reopen(gh_shim, fake_repo):
    r = run_cmd("reopen", "42")
    assert r.returncode == 0
    assert "issue reopen" in gh_shim.read_text()
```

- [ ] **Step 2: Run test to verify it fails**

```bash
python3 -m pytest .claude/features/rabbit-issue/test/test-item-status.py -v
```
Expected: FAIL

- [ ] **Step 3: Implement item-status.py**

```python
#!/usr/bin/env python3
"""
rabbit-issue: show/close/reopen an issue.

Version: 1.0.0
Owner: cyxu
Deprecation criterion: when rabbit-issue is retired
"""
import argparse, json, subprocess, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _gh import gh_issue_view, repo_slug, require_auth, require_managed

VALID_REASONS = ("completed", "not-planned")

def cmd_show(args):
    issue = gh_issue_view(args.number,
        "number,title,state,stateReason,labels,body,createdAt,closedAt")
    print(json.dumps(issue, indent=2))

def cmd_close(args):
    require_managed(args.number)
    cmd = ["gh", "issue", "close", str(args.number),
           "-R", repo_slug(), "--reason", args.reason]
    if args.comment:
        cmd += ["--comment", args.comment]
    subprocess.run(cmd, check=True)

def cmd_reopen(args):
    require_managed(args.number)
    cmd = ["gh", "issue", "reopen", str(args.number), "-R", repo_slug()]
    if args.comment:
        cmd += ["--comment", args.comment]
    subprocess.run(cmd, check=True)

def main():
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("show"); s.add_argument("number", type=int)
    c = sub.add_parser("close")
    c.add_argument("number", type=int)
    c.add_argument("--reason", required=True, choices=VALID_REASONS)
    c.add_argument("--comment", default="")
    r = sub.add_parser("reopen")
    r.add_argument("number", type=int)
    r.add_argument("--comment", default="")
    args = p.parse_args()
    require_auth()
    {"show": cmd_show, "close": cmd_close, "reopen": cmd_reopen}[args.cmd](args)

if __name__ == "__main__":
    main()
```

```bash
chmod +x .claude/features/rabbit-issue/scripts/item-status.py
```

- [ ] **Step 4: Run test to verify it passes**

```bash
python3 -m pytest .claude/features/rabbit-issue/test/test-item-status.py -v
```
Expected: 5 passed

- [ ] **Step 5: Commit**

```bash
git add .claude/features/rabbit-issue/scripts/item-status.py \
        .claude/features/rabbit-issue/test/test-item-status.py
git commit -m "feat(rabbit-issue): item-status.py + tests"
```

---

### Task 8: TDD — `list-items.py`

**Files:**
- Create: `.claude/features/rabbit-issue/scripts/list-items.py`
- Test: `.claude/features/rabbit-issue/test/test-list-items.py`

- [ ] **Step 1: Write the failing test**

```python
# test-list-items.py
import sys, subprocess, json
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
LIST = SCRIPTS / "list-items.py"

def run_cmd(*args, env=None):
    return subprocess.run([sys.executable, str(LIST), *args],
                          capture_output=True, text=True, env=env)

def test_list_open_bugs_calls_gh_with_correct_labels(gh_shim, fake_repo):
    r = run_cmd("--type", "bug")
    assert r.returncode == 0
    log = gh_shim.read_text()
    assert "issue list" in log
    assert "--label rabbit-managed" in log
    assert "--label bug" in log
    assert "--state open" in log

def test_list_all_types_omits_type_label(gh_shim, fake_repo):
    r = run_cmd("--type", "all")
    assert r.returncode == 0
    log = gh_shim.read_text()
    # rabbit-managed is always included; bug/enhancement only when type filter
    assert "--label rabbit-managed" in log
    assert "--label bug" not in log.split("issue list", 1)[1]
    assert "--label enhancement" not in log.split("issue list", 1)[1]

def test_list_filters_by_feature(gh_shim, fake_repo):
    r = run_cmd("--type", "bug", "--feature", "rabbit-cage")
    assert r.returncode == 0
    assert "feature:rabbit-cage" in gh_shim.read_text()

def test_deterministic_sort_by_number_asc(gh_shim, fake_repo, tmp_path, monkeypatch):
    fixture = tmp_path / "list.json"
    fixture.write_text(json.dumps([
        {"number": 17, "title": "t17", "state": "open",
         "labels": [{"name": "bug"}, {"name": "priority:high"},
                    {"name": "feature:rabbit-cage"}]},
        {"number": 3, "title": "t3", "state": "open",
         "labels": [{"name": "bug"}, {"name": "priority:low"},
                    {"name": "feature:rabbit-cage"}]},
    ]))
    monkeypatch.setenv("GH_SHIM_LIST_RESPONSE", str(fixture))
    r = run_cmd("--type", "bug")
    lines = [l for l in r.stdout.strip().split("\n") if l.startswith("#")]
    assert lines[0].startswith("#3 ")
    assert lines[1].startswith("#17 ")
```

- [ ] **Step 2: Run test to verify it fails**

```bash
python3 -m pytest .claude/features/rabbit-issue/test/test-list-items.py -v
```
Expected: FAIL

- [ ] **Step 3: Implement list-items.py**

```python
#!/usr/bin/env python3
"""
rabbit-issue: list issues with filters.

Version: 1.0.0
Owner: cyxu
Deprecation criterion: when rabbit-issue is retired
"""
import argparse, json, subprocess, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _gh import repo_slug, require_auth

VALID_TYPES = ("bug", "enhancement", "all")
VALID_STATES = ("open", "closed", "all")

def get_label(issue, prefix):
    for l in issue.get("labels", []):
        if l["name"].startswith(prefix):
            return l["name"][len(prefix):]
    return ""

def get_type(issue):
    names = {l["name"] for l in issue.get("labels", [])}
    if "bug" in names: return "bug"
    if "enhancement" in names: return "enhancement"
    return "?"

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--type", default="all", choices=VALID_TYPES)
    p.add_argument("--feature", default="")
    p.add_argument("--status", default="open", choices=VALID_STATES)
    args = p.parse_args()
    require_auth()

    cmd = ["gh", "issue", "list", "-R", repo_slug(),
           "--label", "rabbit-managed",
           "--state", args.status,
           "--limit", "500",
           "--json", "number,title,state,labels"]
    if args.type != "all":
        cmd += ["--label", args.type]
    if args.feature:
        cmd += ["--label", f"feature:{args.feature}"]

    out = subprocess.check_output(cmd, text=True)
    issues = json.loads(out)
    issues.sort(key=lambda i: i["number"])
    for i in issues:
        feature = get_label(i, "feature:")
        priority = get_label(i, "priority:")
        print(f"#{i['number']}  [{get_type(i)}]  [{i['state']}]  "
              f"[{priority}]  feature:{feature}  {i['title']}")

if __name__ == "__main__":
    main()
```

```bash
chmod +x .claude/features/rabbit-issue/scripts/list-items.py
```

- [ ] **Step 4: Run test to verify it passes**

```bash
python3 -m pytest .claude/features/rabbit-issue/test/test-list-items.py -v
```
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add .claude/features/rabbit-issue/scripts/list-items.py \
        .claude/features/rabbit-issue/test/test-list-items.py
git commit -m "feat(rabbit-issue): list-items.py + tests"
```

---

### Task 9: TDD — rabbit-managed safety guard regression

**Files:**
- Test: `.claude/features/rabbit-issue/test/test-rabbit-managed-guard.py`

- [ ] **Step 1: Write the failing test**

```python
# test-rabbit-managed-guard.py
import sys, subprocess, json
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
ITEM_STATUS = SCRIPTS / "item-status.py"

def test_close_refused_when_no_rabbit_managed_label(gh_shim, fake_repo, tmp_path, monkeypatch):
    body = tmp_path / "issue.json"
    body.write_text(json.dumps({"number": 5, "labels": [{"name": "bug"}]}))
    monkeypatch.setenv("GH_SHIM_ISSUE_BODY", str(body))
    r = subprocess.run([sys.executable, str(ITEM_STATUS),
                        "close", "5", "--reason", "completed"],
                       capture_output=True, text=True,
                       env={**__import__("os").environ})
    assert r.returncode != 0
    assert "rabbit-managed" in r.stderr or "rabbit-managed" in r.stdout
    # verify no `issue close` happened
    assert "issue close" not in gh_shim.read_text()

def test_reopen_refused_when_no_rabbit_managed_label(gh_shim, fake_repo, tmp_path, monkeypatch):
    body = tmp_path / "issue.json"
    body.write_text(json.dumps({"number": 5, "labels": [{"name": "bug"}]}))
    monkeypatch.setenv("GH_SHIM_ISSUE_BODY", str(body))
    r = subprocess.run([sys.executable, str(ITEM_STATUS), "reopen", "5"],
                       capture_output=True, text=True)
    assert r.returncode != 0
    assert "issue reopen" not in gh_shim.read_text()
```

- [ ] **Step 2: Run test to verify it passes immediately**

```bash
python3 -m pytest .claude/features/rabbit-issue/test/test-rabbit-managed-guard.py -v
```
Expected: 2 passed (logic implemented in Task 7 via `require_managed`)

- [ ] **Step 3: Commit**

```bash
git add .claude/features/rabbit-issue/test/test-rabbit-managed-guard.py
git commit -m "test(rabbit-issue): rabbit-managed safety guard regression"
```

---

### Task 10: TDD — spec/contract presence and manifest shape

**Files:**
- Test: `.claude/features/rabbit-issue/test/test-spec-presence.py`
- Test: `.claude/features/rabbit-issue/test/test-prompts-declared.py`
- Test: `.claude/features/rabbit-issue/test/test-manifest-shape.py`

- [ ] **Step 1: Write test-spec-presence.py**

```python
# test-spec-presence.py
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]

def main():
    spec = ROOT / "docs" / "spec" / "spec.md"
    contract = ROOT / "docs" / "spec" / "contract.md"
    assert spec.is_file(), f"missing {spec}"
    assert contract.is_file(), f"missing {contract}"
    for f in (spec, contract):
        text = f.read_text()
        assert text.startswith("---\n"), f"{f} missing YAML frontmatter"
        for key in ("feature:", "version:", "owner:", "deprecation_criterion:"):
            assert key in text.split("---\n", 2)[1], f"{f} frontmatter missing {key}"
    print("OK")

if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Write test-prompts-declared.py**

```python
# test-prompts-declared.py
import json, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def main():
    feature = json.loads((ROOT / "feature.json").read_text())
    prompts = feature.get("prompts", [])
    assert any(p["id"] == "rabbit-issue" and p["kind"] == "skill" for p in prompts), \
        "feature.json prompts must declare a 'rabbit-issue' skill entry"
    # Inject policy files
    entry = next(p for p in prompts if p["id"] == "rabbit-issue")
    inject = entry.get("inject", [])
    assert ".claude/features/policy/philosophy.md" in inject
    assert ".claude/features/policy/coding-rules.md" in inject
    print("OK")

if __name__ == "__main__":
    main()
```

- [ ] **Step 3: Write test-manifest-shape.py**

```python
# test-manifest-shape.py
import json, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def main():
    feature = json.loads((ROOT / "feature.json").read_text())
    for key in ("name", "version", "owner", "summary",
                "deprecation_criterion", "surface", "manifest"):
        assert key in feature, f"feature.json missing {key}"
    assert feature["name"] == "rabbit-issue"
    surface = feature["surface"]
    assert "rabbit-issue" in surface["skills"]
    for script in ("scripts/file-item.py", "scripts/item-status.py",
                   "scripts/list-items.py", "scripts/_gh.py"):
        assert script in surface["scripts"], f"missing {script} in surface.scripts"
    assert any(m["api"] == "publish_skill" for m in feature["manifest"])
    print("OK")

if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run tests**

```bash
python3 .claude/features/rabbit-issue/test/test-spec-presence.py
python3 .claude/features/rabbit-issue/test/test-prompts-declared.py
python3 .claude/features/rabbit-issue/test/test-manifest-shape.py
```
Expected: all print "OK"

- [ ] **Step 5: Commit**

```bash
git add .claude/features/rabbit-issue/test/test-spec-presence.py \
        .claude/features/rabbit-issue/test/test-prompts-declared.py \
        .claude/features/rabbit-issue/test/test-manifest-shape.py
git commit -m "test(rabbit-issue): spec/contract/manifest static checks"
```

---

## Phase 3 — Skill + smoke test against live GH

### Task 11: Write SKILL.md

**Files:**
- Create: `.claude/features/rabbit-issue/skills/rabbit-issue/SKILL.md`

- [ ] **Step 1: Write SKILL.md**

````markdown
---
name: rabbit-issue
description: Use when Claude detects intent to file a bug or enhancement, check issue status, list issues, close/reopen an issue, or perform any GH-Issues lifecycle operation in this repository. Replaces the retired rabbit-file skill — do NOT attempt to invoke rabbit-file. Trigger on phrases like "file a bug", "log an enhancement", "work this bug", "close the issue", "what bugs are open", "mark that done", "reopen that bug", or any lifecycle phrasing for bugs or enhancements.
version: 1.0.0
owner: cyxu
deprecation_criterion: when GH Issues is replaced or the workflow moves to a different tracker
---

## Overview

`rabbit-issue` wraps `gh issue` for the rabbit workflow. Three runtime
scripts: `file-item.py`, `item-status.py`, `list-items.py`. All issues
live on GitHub Issues against the repo whose `origin` is the current
remote.

| Mode | Script | Purpose |
|---|---|---|
| File  | `file-item.py`     | File a new bug or enhancement |
| Work  | `item-status.py`   | Show, close, or reopen an issue |
| List  | `list-items.py`    | List issues with filters |

## Label schema

Issues filed via `rabbit-issue` always carry these labels:

- Type: `bug` OR `enhancement` (mutually exclusive)
- `rabbit-managed` (distinguisher; safety guard refuses to act on issues without it)
- `feature:<name>` (feature scope)
- `priority:<low|medium|high|critical>`

Labels are auto-created on first use.

## File Protocol

1. Invoke `rabbit-feature-scope` to identify the related feature.
2. Ask for missing title / description / priority.
3. Call file-item.py:

```bash
python3 .claude/features/rabbit-issue/scripts/file-item.py \
  --type bug|enhancement \
  --feature <feature-name> \
  --title "..." \
  --priority <low|medium|high|critical> \
  --description "..."
```

4. Report the assigned GH issue number + URL.

## List Protocol

```bash
python3 .claude/features/rabbit-issue/scripts/list-items.py \
  --type bug|enhancement|all \
  [--feature <feature-name>] \
  [--status open|closed|all]
```

## Work Protocol

1. **Fetch** — `python3 item-status.py show <N>` returns issue JSON.
2. **Eval subagent** — dispatch read-only default-model subagent:
   - Reads issue body + spec
   - Returns verdict (`valid` / `stale-invalid`) with test gap analysis
3. **User-decision gate** — brief, ask "close or proceed?"
4. **If close without work:**

```bash
python3 .claude/features/rabbit-issue/scripts/item-status.py \
  close <N> --reason not-planned --comment "<why>"
```

5. **If proceed:**
   - Invoke `rabbit-feature-touch` in **issue mode** with the issue number.
   - The impl commit message MUST include `Fixes #<N>` so GH auto-closes
     on PR merge. The skill verifies closure post-merge; if not closed
     (e.g., merge to non-default branch), fall back to:

```bash
python3 .claude/features/rabbit-issue/scripts/item-status.py \
  close <N> --reason completed --comment "TDD cycle complete in <SHA>"
```

## Safety invariants

- `item-status.py close`/`reopen` refuse issues missing `rabbit-managed`
- All scripts fail loudly if `gh auth status` is not green
- Repo slug derived from `git remote get-url origin`; non-GitHub remotes fail

## Lifecycle

```
open ↔ closed    (state_reason: completed | not_planned | reopened | null)
```
````

- [ ] **Step 2: Commit**

```bash
git add .claude/features/rabbit-issue/skills/rabbit-issue/SKILL.md
git commit -m "feat(rabbit-issue): SKILL.md with Work Protocol"
```

---

### Task 12: Live smoke test against changyu87/rabbit-workflow

**Files:** none (operational verification)

- [ ] **Step 1: File a test issue**

```bash
python3 .claude/features/rabbit-issue/scripts/file-item.py \
  --type enhancement \
  --feature rabbit-issue \
  --title "rabbit-issue smoke test — please ignore" \
  --priority low \
  --description "Created by Task 12 of rabbit-issue impl plan. Will be closed immediately."
```
Expected: JSON output with `number` and `url`. Record the number as `$N`.

- [ ] **Step 2: Show the issue**

```bash
python3 .claude/features/rabbit-issue/scripts/item-status.py show $N
```
Expected: JSON with all five labels present.

- [ ] **Step 3: List shows the issue**

```bash
python3 .claude/features/rabbit-issue/scripts/list-items.py \
  --type enhancement --feature rabbit-issue
```
Expected: one line matching `#$N  [enhancement]  [open]  [low]  feature:rabbit-issue  ...`

- [ ] **Step 4: Close it**

```bash
python3 .claude/features/rabbit-issue/scripts/item-status.py \
  close $N --reason completed --comment "smoke test passed"
```

- [ ] **Step 5: Verify closure**

```bash
gh issue view $N -R changyu87/rabbit-workflow --json state,stateReason
```
Expected: `{"state":"CLOSED","stateReason":"COMPLETED"}`

**No commit** (this task is operational verification only). Advance feature.json `tdd_state` to `test-green`:

```bash
# edit .claude/features/rabbit-issue/feature.json: tdd_state → "test-green"
git add .claude/features/rabbit-issue/feature.json
git commit -m "chore(rabbit-issue): smoke test passed — tdd_state test-green"
```

---

## Phase 4 — Update rabbit-feature-touch ("B/B mode" → "issue mode")

### Task 13: Audit rabbit-feature-touch references

**Files:**
- Read: `.claude/features/rabbit-feature/skills/rabbit-feature-touch/SKILL.md`
- Read: `.claude/features/rabbit-feature/docs/spec/spec.md`
- Read: `.claude/agents/tdd-subagent/scripts/dispatch-tdd-subagent.py`

- [ ] **Step 1: List all references**

```bash
grep -rln "B/B mode\|rabbit-file\|bug-backlog-files\|backlog\|item.json" \
  .claude/features/rabbit-feature/ \
  .claude/agents/tdd-subagent/ \
  2>/dev/null
```

Record the file list as the surface to update.

---

### Task 14: Update rabbit-feature-touch SKILL.md

**Files:**
- Modify: `.claude/features/rabbit-feature/skills/rabbit-feature-touch/SKILL.md`

- [ ] **Step 1: Apply renames**

Sed-style transforms (verify each manually before committing):

| From | To |
|---|---|
| `B/B mode` | `issue mode` |
| `bug or backlog skill` | `rabbit-issue skill` |
| `rabbit-file` | `rabbit-issue` |
| `--linked-item <bug-or-item-dir> --item-type <bug\|backlog>` | `--linked-issue <N>` |
| `related_feature` from item.json | `feature:<name>` label on issue |
| `bug\|backlog` (mode value) | `bug\|enhancement` |

**Update the B/B item materialization section** (lines ~47-71) entirely. Replace with:

```markdown
#### Issue materialization

The canonical issue lives on GitHub Issues. The TDD subagent receives
the issue number (`N`) and fetches the issue payload via:

```bash
gh issue view <N> --repo $(git remote get-url origin | …) \
  --json number,title,body,labels,state,stateReason,comments,timelineItems \
  > .rabbit/issue-<N>.json
```

The fetched JSON is the subagent's read-only input — no local mirror in
the rabbit/features/... layout.
```

**Update the handoff section** (lines ~213-216):

```markdown
**issue mode:** Commit code to branch. Hand off to calling skill:

```json
{
  "mode": "issue",
  "issue_number": 42,
  "branch": "fix/42-login-broken",
  "impl_commit": "abc123...",
  "tdd_report_path": "..."
}
```

The calling skill (`rabbit-issue`) verifies the auto-close via `Fixes #N`
in the impl commit message and falls back to explicit
`item-status.py close` if the auto-close did not fire.
```

**Update branch naming** (lines ~87-88):

| Bug fix (issue) | `fix/<N>-<keywords>` |
| Enhancement task (issue) | `task/<N>-<keywords>` |

- [ ] **Step 2: Verify with grep**

```bash
grep -c "B/B\|backlog\|rabbit-file" \
  .claude/features/rabbit-feature/skills/rabbit-feature-touch/SKILL.md
```
Expected: 0

- [ ] **Step 3: Commit**

```bash
git add .claude/features/rabbit-feature/skills/rabbit-feature-touch/SKILL.md
git commit -m "feat(rabbit-feature-touch): rename B/B mode → issue mode"
```

---

### Task 15: Update rabbit-feature spec.md

**Files:**
- Modify: `.claude/features/rabbit-feature/docs/spec/spec.md`

- [ ] **Step 1: Apply same renames as Task 14** to the spec.

- [ ] **Step 2: Verify**

```bash
grep -c "B/B\|backlog\|rabbit-file" .claude/features/rabbit-feature/docs/spec/spec.md
```
Expected: 0

- [ ] **Step 3: Bump version in spec frontmatter** (e.g., 0.x → 0.x+1).

- [ ] **Step 4: Commit**

```bash
git add .claude/features/rabbit-feature/docs/spec/spec.md
git commit -m "feat(rabbit-feature): spec — B/B mode → issue mode"
```

---

### Task 16: Update dispatch-tdd-subagent.py

**Files:**
- Modify: `.claude/agents/tdd-subagent/scripts/dispatch-tdd-subagent.py`

- [ ] **Step 1: Read file**

```bash
cat .claude/agents/tdd-subagent/scripts/dispatch-tdd-subagent.py
```

- [ ] **Step 2: Apply renames** (locate every `rabbit-file`, `B/B`, `bug-backlog-files`, `item.json`, `--linked-item`, `--item-type`, `bug\|backlog` and replace per Task 14 mapping).

- [ ] **Step 3: Run rabbit-feature tests**

```bash
python3 .claude/features/rabbit-feature/test/run.py
```
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add .claude/agents/tdd-subagent/scripts/dispatch-tdd-subagent.py
git commit -m "feat(tdd-subagent): adopt rabbit-issue (issue mode)"
```

---

### Task 17: Update rabbit-feature tests for new mode names

**Files:**
- Modify: `.claude/features/rabbit-feature/test/test-touch-skill.py`

- [ ] **Step 1: Update assertions**

Replace any string assertions on `B/B mode`, `rabbit-file`, `--linked-item`, etc. with the new equivalents (`issue mode`, `rabbit-issue`, `--linked-issue`).

- [ ] **Step 2: Run tests**

```bash
python3 .claude/features/rabbit-feature/test/run.py
```
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add .claude/features/rabbit-feature/test/test-touch-skill.py
git commit -m "test(rabbit-feature): update assertions for issue mode"
```

---

## Phase 5 — TDD migrate.py

### Task 18: TDD — migrate.py dry-run

**Files:**
- Create: `.claude/features/rabbit-issue/scripts/migrate.py`
- Test: `.claude/features/rabbit-issue/test/test-migrate-dry-run.py`

- [ ] **Step 1: Write the failing test**

```python
# test-migrate-dry-run.py
import sys, subprocess, json, os
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
MIGRATE = SCRIPTS / "migrate.py"

def setup_synthetic_branch(fake_repo):
    """Create a synthetic origin/bug-backlog-files with 2 open + 1 closed item."""
    import subprocess as sp
    repo = fake_repo
    # Create orphan branch with content
    sp.run(["git", "-C", str(repo), "checkout", "--orphan", "bug-backlog-files"], check=True)
    sp.run(["git", "-C", str(repo), "rm", "-rf", "--ignore-unmatched", "."], check=True)
    base = repo / "rabbit/features/rabbit-cage/bugs/RABBIT-CAGE-BUG-1"
    base.mkdir(parents=True)
    (base / "item.json").write_text(json.dumps({
        "name": "RABBIT-CAGE-BUG-1", "type": "bug", "status": "open",
        "title": "t1", "priority": "high", "description": "d1",
        "related_feature": "rabbit-cage"}))
    base2 = repo / "rabbit/features/rabbit-cage/backlogs/RABBIT-CAGE-BACKLOG-1"
    base2.mkdir(parents=True)
    (base2 / "item.json").write_text(json.dumps({
        "name": "RABBIT-CAGE-BACKLOG-1", "type": "backlog", "status": "open",
        "title": "t2", "priority": "low", "description": "d2",
        "related_feature": "rabbit-cage"}))
    base3 = repo / "rabbit/features/rabbit-cage/bugs/RABBIT-CAGE-BUG-2"
    base3.mkdir(parents=True)
    (base3 / "item.json").write_text(json.dumps({
        "name": "RABBIT-CAGE-BUG-2", "type": "bug", "status": "close",
        "title": "t3", "priority": "medium", "description": "d3",
        "related_feature": "rabbit-cage"}))
    sp.run(["git", "-C", str(repo), "add", "."], check=True)
    sp.run(["git", "-C", str(repo), "-c", "user.email=t@t",
            "-c", "user.name=t", "commit", "-q", "-m", "synthetic"], check=True)
    # Simulate origin: clone refs into a "remote"
    sp.run(["git", "-C", str(repo), "update-ref",
            "refs/remotes/origin/bug-backlog-files", "HEAD"], check=True)
    sp.run(["git", "-C", str(repo), "checkout", "-q", "-b", "main"], check=True)

def test_dry_run_reports_counts_without_writes(gh_shim, fake_repo):
    setup_synthetic_branch(fake_repo)
    r = subprocess.run([sys.executable, str(MIGRATE), "--dry-run"],
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    out = r.stdout
    assert "open items: 2" in out.lower()
    assert "closed items: 1" in out.lower()
    # No GH writes
    log = gh_shim.read_text()
    assert "issue create" not in log
    # No archive writes
    assert not (fake_repo / "archive").exists()
```

- [ ] **Step 2: Run test to verify it fails**

```bash
python3 -m pytest .claude/features/rabbit-issue/test/test-migrate-dry-run.py -v
```
Expected: FAIL (migrate.py doesn't exist)

- [ ] **Step 3: Implement migrate.py (dry-run path)**

```python
#!/usr/bin/env python3
"""
rabbit-issue: ONE-SHOT migration from origin/bug-backlog-files to GH Issues + archive/.

Version: 1.0.0
Owner: cyxu
Deprecation criterion: deleted immediately after cutover commit lands on main
"""
import argparse, json, subprocess, sys, shutil, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _gh import ensure_labels, repo_slug, require_auth

BRANCH = "origin/bug-backlog-files"
ARCHIVE_DIR = Path("archive/bug-backlog")
MANIFEST = Path("archive/migration-manifest.json")

def walk_items():
    """Yield (feature, type_old, id, item_dict) from the branch via `git ls-tree` / `git show`."""
    out = subprocess.check_output(
        ["git", "ls-tree", "-r", "--name-only", BRANCH], text=True)
    for path in out.strip().split("\n"):
        if not path.endswith("/item.json"):
            continue
        # path: rabbit/features/<feature>/<types>/<ID>/item.json
        parts = path.split("/")
        if len(parts) != 6 or parts[0] != "rabbit" or parts[1] != "features":
            continue
        feature, types_dir, item_id = parts[2], parts[3], parts[4]
        type_old = "bug" if types_dir == "bugs" else "backlog" if types_dir == "backlogs" else None
        if type_old is None:
            continue
        body = subprocess.check_output(["git", "show", f"{BRANCH}:{path}"], text=True)
        yield feature, type_old, item_id, json.loads(body)

def map_type(t_old):
    return "bug" if t_old == "bug" else "enhancement"

def load_manifest():
    if MANIFEST.exists():
        return json.loads(MANIFEST.read_text())
    return {"open_items": [], "closed_items": []}

def already_migrated_open(manifest, old_id):
    return any(i["old_id"] == old_id for i in manifest["open_items"])

def already_migrated_closed(manifest, old_id):
    return any(i["old_id"] == old_id for i in manifest["closed_items"])

def dry_run():
    open_n = closed_n = 0
    for feature, t_old, item_id, body in walk_items():
        if body.get("status") == "open":
            open_n += 1
        elif body.get("status") == "close":
            closed_n += 1
    print(f"DRY RUN")
    print(f"  open items:   {open_n}")
    print(f"  closed items: {closed_n}")
    print(f"  archive root: {ARCHIVE_DIR}")
    print(f"  branch:       {BRANCH}")

def real_migrate():
    require_auth()
    manifest = load_manifest()
    open_log, closed_log = list(manifest["open_items"]), list(manifest["closed_items"])
    for feature, t_old, item_id, body in walk_items():
        if body.get("status") == "open":
            if already_migrated_open(manifest, item_id):
                continue
            t_new = map_type(t_old)
            prio = body.get("priority", "medium")
            labels = [t_new, "rabbit-managed",
                      f"feature:{feature}", f"priority:{prio}"]
            ensure_labels(labels)
            url = subprocess.check_output(
                ["gh", "issue", "create", "-R", repo_slug(),
                 "--title", body["title"],
                 "--body", body.get("description", ""),
                 "--label", ",".join(labels)], text=True).strip()
            number = int(url.rsplit("/", 1)[-1])
            open_log.append({"old_id": item_id, "new_number": number, "url": url})
            print(f"  open  {item_id} → #{number}")
        elif body.get("status") == "close":
            if already_migrated_closed(manifest, item_id):
                continue
            dest = ARCHIVE_DIR / feature / f"{item_id}.json"
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(json.dumps(body, indent=2))
            closed_log.append({"old_id": item_id, "archive_path": str(dest)})
            print(f"  close {item_id} → {dest}")
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST.write_text(json.dumps({
        "migrated_at": datetime.datetime.utcnow().isoformat() + "Z",
        "rabbit_workflow_repo": repo_slug(),
        "old_branch": "bug-backlog-files",
        "open_items": open_log,
        "closed_items": closed_log,
    }, indent=2))
    print(f"\nManifest: {MANIFEST}")
    print(f"\n*** READY TO DELETE BRANCH (gated on user approval):")
    print(f"    git push origin --delete bug-backlog-files")

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()
    (dry_run if args.dry_run else real_migrate)()

if __name__ == "__main__":
    main()
```

```bash
chmod +x .claude/features/rabbit-issue/scripts/migrate.py
```

- [ ] **Step 4: Run dry-run test to verify it passes**

```bash
python3 -m pytest .claude/features/rabbit-issue/test/test-migrate-dry-run.py -v
```
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add .claude/features/rabbit-issue/scripts/migrate.py \
        .claude/features/rabbit-issue/test/test-migrate-dry-run.py
git commit -m "feat(rabbit-issue): migrate.py + dry-run test"
```

---

### Task 19: TDD — migrate.py real migration

**Files:**
- Test: `.claude/features/rabbit-issue/test/test-migrate-real.py`

- [ ] **Step 1: Write the failing test**

```python
# test-migrate-real.py
import sys, subprocess, json
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
MIGRATE = SCRIPTS / "migrate.py"

# Reuse setup_synthetic_branch from test-migrate-dry-run.py via local copy
def setup(fake_repo):
    from importlib.util import spec_from_file_location, module_from_spec
    spec = spec_from_file_location("dry_test",
        Path(__file__).parent / "test-migrate-dry-run.py")
    m = module_from_spec(spec); spec.loader.exec_module(m)
    m.setup_synthetic_branch(fake_repo)

def test_real_migration_creates_issues_and_archives(gh_shim, fake_repo):
    setup(fake_repo)
    r = subprocess.run([sys.executable, str(MIGRATE)],
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    log = gh_shim.read_text()
    # 2 open items → 2 issue create calls
    assert log.count("issue create") == 2
    # 1 closed item → archive file present
    archive = fake_repo / "archive/bug-backlog/rabbit-cage/RABBIT-CAGE-BUG-2.json"
    assert archive.is_file()
    # Manifest exists and tracks all items
    manifest = json.loads((fake_repo / "archive/migration-manifest.json").read_text())
    assert len(manifest["open_items"]) == 2
    assert len(manifest["closed_items"]) == 1

def test_backlog_type_mapped_to_enhancement(gh_shim, fake_repo):
    setup(fake_repo)
    subprocess.run([sys.executable, str(MIGRATE)],
                   capture_output=True, text=True, check=True)
    log = gh_shim.read_text()
    # The backlog item must be created with `enhancement` label
    create_lines = [l for l in log.split("\n") if "issue create" in l]
    enhancement_lines = [l for l in create_lines if "enhancement" in l]
    assert len(enhancement_lines) == 1
```

- [ ] **Step 2: Run test**

```bash
python3 -m pytest .claude/features/rabbit-issue/test/test-migrate-real.py -v
```
Expected: PASS (logic from Task 18)

- [ ] **Step 3: Commit**

```bash
git add .claude/features/rabbit-issue/test/test-migrate-real.py
git commit -m "test(rabbit-issue): migrate.py real migration + backlog→enhancement"
```

---

### Task 20: TDD — migrate.py idempotency

**Files:**
- Test: `.claude/features/rabbit-issue/test/test-migrate-idempotent.py`

- [ ] **Step 1: Write the test**

```python
# test-migrate-idempotent.py
import sys, subprocess
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
MIGRATE = SCRIPTS / "migrate.py"

def setup(fake_repo):
    from importlib.util import spec_from_file_location, module_from_spec
    spec = spec_from_file_location("dry_test",
        Path(__file__).parent / "test-migrate-dry-run.py")
    m = module_from_spec(spec); spec.loader.exec_module(m)
    m.setup_synthetic_branch(fake_repo)

def test_second_run_is_noop(gh_shim, fake_repo):
    setup(fake_repo)
    # First run
    subprocess.run([sys.executable, str(MIGRATE)],
                   capture_output=True, text=True, check=True)
    log_after_first = gh_shim.read_text()
    create_count_1 = log_after_first.count("issue create")
    # Second run
    subprocess.run([sys.executable, str(MIGRATE)],
                   capture_output=True, text=True, check=True)
    log_after_second = gh_shim.read_text()
    create_count_2 = log_after_second.count("issue create")
    # No new issues created
    assert create_count_2 == create_count_1
```

- [ ] **Step 2: Run test**

```bash
python3 -m pytest .claude/features/rabbit-issue/test/test-migrate-idempotent.py -v
```
Expected: PASS (manifest skip logic from Task 18)

- [ ] **Step 3: Run full test suite**

```bash
python3 .claude/features/rabbit-issue/test/run.py
```
Expected: ALL PASS

- [ ] **Step 4: Commit**

```bash
git add .claude/features/rabbit-issue/test/test-migrate-idempotent.py
git commit -m "test(rabbit-issue): migrate.py idempotency"
```

---

## Phase 6 — Execute migration

### Task 21: Dry-run against the live branch

**Files:** none (operational)

- [ ] **Step 1: Fetch the branch**

```bash
git fetch origin bug-backlog-files
```

- [ ] **Step 2: Run dry-run**

```bash
python3 .claude/features/rabbit-issue/scripts/migrate.py --dry-run
```

- [ ] **Step 3: Record counts** — note the reported open / closed counts. These are the target verification numbers for Task 22.

---

### Task 22: USER-GATED — Real migration

**Files:** runtime side-effects only

- [ ] **Step 1: Get explicit user approval**

Brief the user with the dry-run counts. Ask: "Proceed with real migration? This will create $OPEN GH issues and write $CLOSED archive files."

Wait for explicit "proceed" before next step.

- [ ] **Step 2: Run migration**

```bash
python3 .claude/features/rabbit-issue/scripts/migrate.py
```
Expected: per-item log lines, manifest written at `archive/migration-manifest.json`, "READY TO DELETE BRANCH" footer.

- [ ] **Step 3: Verify counts**

```bash
# Count new GH issues
gh issue list -R changyu87/rabbit-workflow --label rabbit-managed \
  --state all --limit 500 --json number | jq length
# Count archive files
find archive/bug-backlog -name "*.json" | wc -l
# Compare to dry-run counts from Task 21
```

- [ ] **Step 4: Spot-check 2-3 items**

```bash
# Pick 2 items from manifest; verify labels via gh issue view
python3 -c "
import json
m = json.load(open('archive/migration-manifest.json'))
for i in m['open_items'][:2]:
    print(i['new_number'], i['old_id'])
"
gh issue view <number> -R changyu87/rabbit-workflow --json labels,title,body
```
Expected: 4 labels (type, rabbit-managed, feature:X, priority:Y), title + body preserved.

---

### Task 23: Commit archive + manifest

**Files:** `archive/` (new), `archive/migration-manifest.json`

- [ ] **Step 1: Stage and commit**

```bash
git add archive/
git commit -m "chore(rabbit-issue): archive closed B/B items + migration manifest

Migrated $OPEN open items to GH Issues and $CLOSED closed items to
archive/bug-backlog/. Manifest at archive/migration-manifest.json.

Closes RABBIT-FILE-BACKLOG-16."
```

(Use real counts from Task 22 verification.)

---

## Phase 7 — Cleanup (user-gated)

### Task 24: USER-GATED — Delete dedicated branch

**Files:** remote-only

- [ ] **Step 1: Get explicit user approval**

Confirm with user: "Migration verified. Delete the `bug-backlog-files` branch on origin? This is hard to undo cleanly."

Wait for explicit "delete" before next step.

- [ ] **Step 2: Capture reflog SHA for rollback**

```bash
git rev-parse origin/bug-backlog-files
# Record this SHA — recovery uses it if branch needs to be restored
```

- [ ] **Step 3: Delete remote branch**

```bash
git push origin --delete bug-backlog-files
```

- [ ] **Step 4: Delete local tracking refs**

```bash
git update-ref -d refs/remotes/origin/bug-backlog-files
git remote prune origin
```

---

### Task 25: Delete .claude/features/rabbit-file/

**Files:**
- Delete: `.claude/features/rabbit-file/` (entire directory)

- [ ] **Step 1: Verify nothing references it**

```bash
grep -rln "rabbit-file" .claude/ docs/ CLAUDE.md 2>/dev/null | grep -v archive
```
Expected: only matches inside `.claude/features/rabbit-file/` itself (which is about to be deleted)

If any other file references `rabbit-file`, update it first. Common suspects:
- `.claude/workspace-structure.json` (remove the rabbit-file entry)
- `.claude/features/rabbit-cage/install.py` (if it deploys rabbit-file, remove)
- `.claude/features/rabbit-cage/docs/spec/spec.md` (mention list)
- `.claude/features/contract/test/test-workspace-declares-all-features.py` (test fixture)

- [ ] **Step 2: Delete the directory**

```bash
git rm -r .claude/features/rabbit-file/
```

- [ ] **Step 3: Update workspace-structure.json**

Remove the `rabbit-file` entry from features list.

- [ ] **Step 4: Run cross-feature tests**

```bash
python3 .claude/features/contract/test/run.py
python3 .claude/features/rabbit-cage/test/run.py
python3 .claude/features/rabbit-feature/test/run.py
```
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "chore: remove retired rabbit-file feature

Replaced by rabbit-issue (GH Issues backend). All open items migrated;
closed items archived. The bug-backlog-files branch was deleted in the
prior step."
```

---

### Task 26: Delete migrate.py

**Files:**
- Delete: `.claude/features/rabbit-issue/scripts/migrate.py`
- Modify: `.claude/features/rabbit-issue/feature.json` (remove migrate.py from surface.scripts)
- Modify: `.claude/features/rabbit-issue/test/run.py` (remove migrate test suites)
- Delete: `.claude/features/rabbit-issue/test/test-migrate-*.py`

- [ ] **Step 1: Delete migrate.py and its tests**

```bash
git rm .claude/features/rabbit-issue/scripts/migrate.py
git rm .claude/features/rabbit-issue/test/test-migrate-dry-run.py
git rm .claude/features/rabbit-issue/test/test-migrate-real.py
git rm .claude/features/rabbit-issue/test/test-migrate-idempotent.py
```

- [ ] **Step 2: Update feature.json**

Remove `"scripts/migrate.py"` from `surface.scripts`.

- [ ] **Step 3: Update run.py**

Remove the three `("pytest", "test-migrate-*.py")` entries from the `SUITES` list.

- [ ] **Step 4: Run tests to confirm green**

```bash
python3 .claude/features/rabbit-issue/test/run.py
```
Expected: ALL PASS (8 suites now instead of 11)

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "chore(rabbit-issue): retire one-shot migrate.py post-cutover"
```

---

### Task 27: Final verification + CLAUDE.md update

**Files:**
- Check: `CLAUDE.md` (root) — does it mention rabbit-file?
- Modify: any leftover references found

- [ ] **Step 1: Find leftover references**

```bash
grep -rln "rabbit-file\|bug-backlog-files\|B/B mode\|backlog" \
  CLAUDE.md .claude/features/ docs/ 2>/dev/null \
  | grep -v archive \
  | grep -v "docs/superpowers/specs/2026-05-29-rabbit-issue-design.md" \
  | grep -v "docs/superpowers/plans/2026-05-29-rabbit-issue.md"
```
Expected: each match either inside an archive entry or a historic spec/plan — none requiring update.

- [ ] **Step 2: Update CLAUDE.md if needed**

If `CLAUDE.md` references `rabbit-file` or B/B, replace with `rabbit-issue` or "issue mode."

- [ ] **Step 3: Run full rabbit-issue suite**

```bash
python3 .claude/features/rabbit-issue/test/run.py
```
Expected: ALL PASS

- [ ] **Step 4: Smoke test via SKILL**

In a fresh Claude session, invoke `Skill("rabbit-issue", args: "list open bugs")` and verify the skill runs end-to-end against the real repo.

- [ ] **Step 5: Final commit**

```bash
git add -A
git commit -m "chore: final cleanup — rabbit-file → rabbit-issue cutover complete

- All open B/B items live in GH Issues with rabbit-managed labels
- Closed items archived under archive/bug-backlog/
- origin/bug-backlog-files branch deleted
- .claude/features/rabbit-file/ removed
- migrate.py retired
- rabbit-feature-touch updated for issue mode
- All tests green

Closes RABBIT-FILE-BACKLOG-16."
```

---

## Self-Review Checklist (for the engineer executing this plan)

After each phase:
- All new files match the paths in **File Structure**
- All tests pass via `run.py`
- Commits follow the pattern in each task
- No `rabbit-file` references remain outside `archive/` and historical spec/plan docs

After Task 27:
- `gh issue list --label rabbit-managed -R changyu87/rabbit-workflow` returns the migrated open items
- `archive/migration-manifest.json` cross-references every migrated item
- `git ls-remote --heads origin bug-backlog-files` returns empty
- `.claude/features/rabbit-file/` does not exist
- `python3 .claude/features/rabbit-issue/test/run.py` reports all green
