# Federate Build Manifests Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Retire the monolithic `contract/build-contract.json` in favor of per-feature `publish.json` files, with `contract` owning the JSON schema, `build.py` discovering and executing from all feature manifests, and `sync-check.py` detecting drift from per-feature manifests.

**Architecture:** Each active feature declares its own `publish.json` (source paths relative to feature root). `build.py` globs `feature.json` files, skips retired features, and inlines the copy-file logic (build-targets.py is deleted). `sync-check.py` discovers the same manifests for drift detection. The contract feature owns `schemas/publish-manifest.schema.json`; per-feature manifests validate against it.

**Tech Stack:** Python 3, stdlib only (json, hashlib, shutil, re, pathlib, subprocess). No new dependencies.

---

## Affected Files (36 total)

**CREATE (9):**
- `contract/schemas/publish-manifest.schema.json`
- `contract/test/test-publish-manifest-schema.py`
- `contract/test/test-publish-manifests.py`
- `rabbit-cage/publish.json`
- `rabbit-feature/publish.json`
- `rabbit-file/publish.json`
- `tdd-subagent/publish.json`
- `tdd-state-machine/publish.json`

**MODIFY (22):**
- `rabbit-cage/hooks/sync-check.py`
- `rabbit-cage/scripts/build.py`
- `rabbit-cage/test/test_helpers.py`
- `rabbit-cage/test/test-RABBIT-CAGE-BACKLOG-21-surface-drift-files.py`
- `rabbit-cage/test/test-RABBIT-CAGE-BUG4.py`
- `rabbit-cage/test/test-RABBIT-CAGE-22-stale-marker.py`
- `rabbit-cage/test/test-build-non-git-dir.py`
- `rabbit-cage/test/test-team-wide-permissions.py`
- `rabbit-cage/test/test-RABBIT-CAGE-WAVE4-bug-cleanup.py`
- `rabbit-cage/test/test-RABBIT-CAGE-BACKLOG2-python-only.py`
- `rabbit-cage/test/test-no-embedded-python3.py`
- `rabbit-cage/test/test-generated-surface.py`
- `rabbit-cage/test/test-BACKLOG-11-rabbit-config-skill.py`
- `rabbit-cage/test/test-RABBIT-CAGE-BACKLOG9-green-messages.py`
- `rabbit-cage/test/test-RABBIT-CAGE-BACKLOG7-visual-messages.py`
- `contract/test/run.py`
- `contract/test/test-files-exist.py`
- `contract/test/test-retirement-semantics.py`
- `contract/test/test-retired-artifacts.py`
- `contract/test/test-bug-fixes-cycle.py`
- `contract/test/test-no-dead-contract-scripts.py`
- `contract/test/test-rabbit-feature-skills-deployment.py`

**DELETE (5):**
- `contract/build-contract.json`
- `contract/schemas/build-contract.schema.json`
- `contract/test/test-build-contract.py`
- `contract/test/test-build-contract-post-consolidation.py`
- `rabbit-cage/scripts/build-targets.py`

All paths are relative to `.claude/features/`.

---

## Task 1: Schema + test-publish-manifest-schema.py

**Files:**
- Create: `.claude/features/contract/test/test-publish-manifest-schema.py`
- Create: `.claude/features/contract/schemas/publish-manifest.schema.json`

- [ ] **Step 1: Write test-publish-manifest-schema.py**

```python
#!/usr/bin/env python3
"""test-publish-manifest-schema.py — validates publish-manifest.schema.json.

t1: schema file exists
t2: schema is valid JSON
t3: ownership fields present (schema_version, owner, deprecation_criterion)
t4: title == 'publish-manifest'
"""
import json
import os
import sys

FEATURE_DIR = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
SCHEMA_PATH = os.path.join(FEATURE_DIR, "schemas", "publish-manifest.schema.json")

passed = 0
failed = 0


def ok(n, msg):
    global passed
    print(f"  PASS t{n}: {msg}")
    passed += 1


def fail_t(n, msg):
    global failed
    print(f"  FAIL t{n}: {msg}", file=sys.stderr)
    failed += 1


print("test-publish-manifest-schema.py")

if os.path.isfile(SCHEMA_PATH):
    ok(1, "publish-manifest.schema.json exists")
else:
    fail_t(1, f"publish-manifest.schema.json missing at {SCHEMA_PATH}")

schema = None
if os.path.isfile(SCHEMA_PATH):
    try:
        schema = json.load(open(SCHEMA_PATH))
        ok(2, "schema is valid JSON")
    except json.JSONDecodeError as e:
        fail_t(2, f"schema is not valid JSON: {e}")
else:
    fail_t(2, "schema is not valid JSON (file missing)")

if schema is not None:
    for field in ("schema_version", "owner", "deprecation_criterion"):
        if field in schema:
            ok(3, f"ownership field '{field}' present")
        else:
            fail_t(3, f"ownership field '{field}' missing")
else:
    fail_t(3, "ownership fields not checked (schema missing/invalid)")

if schema is not None:
    if schema.get("title") == "publish-manifest":
        ok(4, "title == 'publish-manifest'")
    else:
        fail_t(4, f"title is {schema.get('title')!r}, expected 'publish-manifest'")
else:
    fail_t(4, "title not checked (schema missing/invalid)")

print()
print(f"Results: {passed} passed, {failed} failed")
sys.exit(0 if failed == 0 else 1)
```

- [ ] **Step 2: Run test to verify it fails**

```bash
python3 .claude/features/contract/test/test-publish-manifest-schema.py
```
Expected: FAIL t1 (schema missing)

- [ ] **Step 3: Create publish-manifest.schema.json**

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "publish-manifest",
  "description": "Per-feature publish manifest declaring copy-file targets to the deployed .claude/ surface",
  "schema_version": "1.0.0",
  "owner": "rabbit-workflow team",
  "deprecation_criterion": "when Claude Code natively manages workspace artifact generation",
  "type": "object",
  "required": ["schema_version", "feature", "owner", "deprecation_criterion", "targets"],
  "properties": {
    "schema_version": {"type": "string"},
    "feature": {"type": "string"},
    "owner": {"type": "string"},
    "deprecation_criterion": {"type": "string"},
    "targets": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["name", "type", "source", "destination"],
        "properties": {
          "name": {"type": "string"},
          "type": {"type": "string", "enum": ["copy-file"]},
          "source": {"type": "string"},
          "destination": {"type": "string"},
          "check_on_stop": {"type": "boolean"}
        },
        "additionalProperties": false
      }
    }
  },
  "additionalProperties": false
}
```

- [ ] **Step 4: Run test to verify it passes**

```bash
python3 .claude/features/contract/test/test-publish-manifest-schema.py
```
Expected: 5 PASS, 0 failed

- [ ] **Step 5: Commit**

```bash
git add .claude/features/contract/schemas/publish-manifest.schema.json \
        .claude/features/contract/test/test-publish-manifest-schema.py
git commit -m "feat(contract): add publish-manifest.schema.json + validation test (CONTRACT-BACKLOG-21)"
```

---

## Task 2: test-publish-manifests.py + per-feature publish.json files

**Files:**
- Create: `.claude/features/contract/test/test-publish-manifests.py`
- Create: `.claude/features/rabbit-cage/publish.json`
- Create: `.claude/features/rabbit-feature/publish.json`
- Create: `.claude/features/rabbit-file/publish.json`
- Create: `.claude/features/tdd-subagent/publish.json`
- Create: `.claude/features/tdd-state-machine/publish.json`

- [ ] **Step 1: Write test-publish-manifests.py**

```python
#!/usr/bin/env python3
"""test-publish-manifests.py — validates per-feature publish.json manifests.

For each active feature with a publish.json:
  - validates against publish-manifest.schema.json
  - checks all declared source paths exist on disk
  - checks feature field matches directory name
"""
import json
import os
import sys

FEATURE_DIR = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import subprocess
result = subprocess.run(
    ["git", "-C", FEATURE_DIR, "rev-parse", "--show-toplevel"],
    capture_output=True, text=True
)
REPO_ROOT = result.stdout.strip() if result.returncode == 0 else ""
FEATURES_DIR = os.path.join(REPO_ROOT, ".claude", "features")
SCHEMA_PATH = os.path.join(FEATURE_DIR, "schemas", "publish-manifest.schema.json")

passed = 0
failed = 0


def ok(label, msg):
    global passed
    print(f"  PASS {label}: {msg}")
    passed += 1


def fail_t(label, msg):
    global failed
    print(f"  FAIL {label}: {msg}", file=sys.stderr)
    failed += 1


print("test-publish-manifests.py")

try:
    schema = json.load(open(SCHEMA_PATH))
except (json.JSONDecodeError, OSError) as e:
    print(f"ABORT: cannot load schema: {e}", file=sys.stderr)
    sys.exit(1)

feature_dirs = sorted([
    d for d in os.listdir(FEATURES_DIR)
    if os.path.isdir(os.path.join(FEATURES_DIR, d))
])

found_manifests = 0
for feature_name in feature_dirs:
    feature_dir = os.path.join(FEATURES_DIR, feature_name)
    feature_json_path = os.path.join(feature_dir, "feature.json")
    publish_path = os.path.join(feature_dir, "publish.json")

    if not os.path.isfile(feature_json_path):
        continue
    try:
        feature_meta = json.load(open(feature_json_path))
    except (json.JSONDecodeError, OSError):
        continue
    if feature_meta.get("status") == "retired":
        continue
    if not os.path.isfile(publish_path):
        continue

    found_manifests += 1
    label = feature_name

    try:
        manifest = json.load(open(publish_path))
    except json.JSONDecodeError as e:
        fail_t(label, f"publish.json is not valid JSON: {e}")
        continue
    ok(f"{label}/json", "publish.json is valid JSON")

    if manifest.get("feature") != feature_name:
        fail_t(f"{label}/feature", f"feature field {manifest.get('feature')!r} != dir {feature_name!r}")
    else:
        ok(f"{label}/feature", "feature field matches dir name")

    for field in ("schema_version", "feature", "owner", "deprecation_criterion", "targets"):
        if field in manifest:
            ok(f"{label}/field/{field}", f"required field '{field}' present")
        else:
            fail_t(f"{label}/field/{field}", f"required field '{field}' missing")

    for target in manifest.get("targets", []):
        source_rel = target.get("source", "")
        source_abs = os.path.join(feature_dir, source_rel)
        t_name = target.get("name", source_rel)
        if not os.path.isfile(source_abs):
            fail_t(f"{label}/source/{t_name}", f"source does not exist: {source_abs}")
        else:
            ok(f"{label}/source/{t_name}", f"source exists: {source_rel}")

if found_manifests == 0:
    fail_t("coverage", "no active feature publish.json files found")
else:
    ok("coverage", f"{found_manifests} active feature manifests validated")

print()
print(f"Results: {passed} passed, {failed} failed")
sys.exit(0 if failed == 0 else 1)
```

- [ ] **Step 2: Run test to verify it fails**

```bash
python3 .claude/features/contract/test/test-publish-manifests.py
```
Expected: FAIL "no active feature publish.json files found"

- [ ] **Step 3: Create rabbit-cage/publish.json**

Note: 11 targets (10 original + 1 new: rabbit-config.py script). Source paths are relative to `.claude/features/rabbit-cage/`.

```json
{
  "schema_version": "1.0.0",
  "feature": "rabbit-cage",
  "owner": "rabbit-workflow team",
  "deprecation_criterion": "when Claude Code natively manages workspace artifact generation",
  "targets": [
    {"name": "hooks/refresh.py", "type": "copy-file", "source": "hooks/refresh.py", "destination": ".claude/hooks/refresh.py", "check_on_stop": true},
    {"name": "hooks/scope-guard.py", "type": "copy-file", "source": "hooks/scope-guard.py", "destination": ".claude/hooks/scope-guard.py", "check_on_stop": true},
    {"name": "hooks/session-init.py", "type": "copy-file", "source": "hooks/session-init.py", "destination": ".claude/hooks/session-init.py", "check_on_stop": true},
    {"name": "hooks/sync-check.py", "type": "copy-file", "source": "hooks/sync-check.py", "destination": ".claude/hooks/sync-check.py", "check_on_stop": true},
    {"name": "commands/rabbit-refresh.md", "type": "copy-file", "source": "commands/rabbit-refresh.md", "destination": ".claude/commands/rabbit-refresh.md", "check_on_stop": true},
    {"name": "commands/rabbit-project.md", "type": "copy-file", "source": "commands/rabbit-project.md", "destination": ".claude/commands/rabbit-project.md", "check_on_stop": true},
    {"name": "settings.json", "type": "copy-file", "source": "settings.json", "destination": ".claude/settings.json", "check_on_stop": true},
    {"name": "skills/rabbit-config/SKILL.md", "type": "copy-file", "source": "skills/rabbit-config/SKILL.md", "destination": ".claude/skills/rabbit-config/SKILL.md", "check_on_stop": true},
    {"name": "skills/rabbit-config/scripts/rabbit-config.py", "type": "copy-file", "source": "skills/rabbit-config/scripts/rabbit-config.py", "destination": ".claude/skills/rabbit-config/scripts/rabbit-config.py", "check_on_stop": true},
    {"name": "README.md", "type": "copy-file", "source": "README.md", "destination": "README.md", "check_on_stop": false},
    {"name": "install.py", "type": "copy-file", "source": "install.py", "destination": "install.py", "check_on_stop": false}
  ]
}
```

- [ ] **Step 4: Create rabbit-feature/publish.json**

```json
{
  "schema_version": "1.0.0",
  "feature": "rabbit-feature",
  "owner": "rabbit-workflow team",
  "deprecation_criterion": "when Claude Code natively supports feature lifecycle management",
  "targets": [
    {"name": "skills/rabbit-feature-touch/SKILL.md", "type": "copy-file", "source": "skills/rabbit-feature-touch/SKILL.md", "destination": ".claude/skills/rabbit-feature-touch/SKILL.md", "check_on_stop": true},
    {"name": "skills/rabbit-feature-scope/SKILL.md", "type": "copy-file", "source": "skills/rabbit-feature-scope/SKILL.md", "destination": ".claude/skills/rabbit-feature-scope/SKILL.md", "check_on_stop": true},
    {"name": "skills/rabbit-feature-new/SKILL.md", "type": "copy-file", "source": "skills/rabbit-feature-new/SKILL.md", "destination": ".claude/skills/rabbit-feature-new/SKILL.md", "check_on_stop": true},
    {"name": "skills/rabbit-feature-audit/SKILL.md", "type": "copy-file", "source": "skills/rabbit-feature-audit/SKILL.md", "destination": ".claude/skills/rabbit-feature-audit/SKILL.md", "check_on_stop": true},
    {"name": "skills/rabbit-feature-spec/SKILL.md", "type": "copy-file", "source": "skills/rabbit-feature-spec/SKILL.md", "destination": ".claude/skills/rabbit-feature-spec/SKILL.md", "check_on_stop": true}
  ]
}
```

- [ ] **Step 5: Create rabbit-file/publish.json**

```json
{
  "schema_version": "1.0.0",
  "feature": "rabbit-file",
  "owner": "rabbit-workflow team",
  "deprecation_criterion": "when Claude Code natively supports bug and backlog lifecycle management",
  "targets": [
    {"name": "skills/rabbit-file/SKILL.md", "type": "copy-file", "source": "skills/rabbit-file/SKILL.md", "destination": ".claude/skills/rabbit-file/SKILL.md", "check_on_stop": true}
  ]
}
```

- [ ] **Step 6: Create tdd-subagent/publish.json**

```json
{
  "schema_version": "1.0.0",
  "feature": "tdd-subagent",
  "owner": "rabbit-workflow team",
  "deprecation_criterion": "when Claude Code natively supports parallel TDD subagent dispatch",
  "targets": [
    {"name": "agents/tdd-subagent.md", "type": "copy-file", "source": "agents/tdd-subagent.md", "destination": ".claude/agents/tdd-subagent.md", "check_on_stop": true},
    {"name": "agents/tdd-subagent/scripts/dispatch-tdd-subagent.py", "type": "copy-file", "source": "scripts/dispatch-tdd-subagent.py", "destination": ".claude/agents/tdd-subagent/scripts/dispatch-tdd-subagent.py", "check_on_stop": true}
  ]
}
```

- [ ] **Step 7: Create tdd-state-machine/publish.json**

```json
{
  "schema_version": "1.0.0",
  "feature": "tdd-state-machine",
  "owner": "rabbit-workflow team",
  "deprecation_criterion": "when Claude Code natively supports TDD state machine lifecycle management",
  "targets": [
    {"name": "agents/tdd-subagent/scripts/tdd-step.py", "type": "copy-file", "source": "scripts/tdd-step.py", "destination": ".claude/agents/tdd-subagent/scripts/tdd-step.py", "check_on_stop": true}
  ]
}
```

- [ ] **Step 8: Run test-publish-manifests.py to verify it passes**

```bash
python3 .claude/features/contract/test/test-publish-manifests.py
```
Expected: coverage PASS (5 manifests), all source/field checks PASS, 0 failed

- [ ] **Step 9: Commit**

```bash
git add .claude/features/contract/test/test-publish-manifests.py \
        .claude/features/rabbit-cage/publish.json \
        .claude/features/rabbit-feature/publish.json \
        .claude/features/rabbit-file/publish.json \
        .claude/features/tdd-subagent/publish.json \
        .claude/features/tdd-state-machine/publish.json
git commit -m "feat: add per-feature publish.json manifests + validation test (CONTRACT-BACKLOG-21)"
```

---

## Task 3: Add write_feature_manifest() to test_helpers.py

**Files:**
- Modify: `.claude/features/rabbit-cage/test/test_helpers.py`

- [ ] **Step 1: Read test_helpers.py** (needed before edit)

Read `.claude/features/rabbit-cage/test/test_helpers.py`

- [ ] **Step 2: Append write_feature_manifest at end of file**

Add after the `run_sync` function:

```python
def write_feature_manifest(tmproot, feature_name, targets):
    """Create an active feature with publish.json in tmproot for test fixtures.

    Each target dict must have: name, source (relative to feature dir),
    destination (relative to repo root). Optional: check_on_stop (default True).
    Source files are NOT created — callers create them inside the returned
    feature_dir path.
    Returns the absolute path of the created feature dir.
    """
    feature_dir = os.path.join(tmproot, ".claude", "features", feature_name)
    os.makedirs(feature_dir, exist_ok=True)
    with open(os.path.join(feature_dir, "feature.json"), "w") as f:
        json.dump({
            "name": feature_name,
            "version": "1.0.0",
            "owner": "test",
            "status": "active",
            "deprecation_criterion": "n/a",
        }, f)
    manifest = {
        "schema_version": "1.0.0",
        "feature": feature_name,
        "owner": "test",
        "deprecation_criterion": "test fixture",
        "targets": [
            {
                "name": t["name"],
                "type": "copy-file",
                "source": t["source"],
                "destination": t["destination"],
                "check_on_stop": t.get("check_on_stop", True),
            }
            for t in targets
        ],
    }
    with open(os.path.join(feature_dir, "publish.json"), "w") as f:
        json.dump(manifest, f, indent=2)
    return feature_dir
```

- [ ] **Step 3: Commit**

```bash
git add .claude/features/rabbit-cage/test/test_helpers.py
git commit -m "feat(rabbit-cage): add write_feature_manifest() to test_helpers"
```

---

## Task 4: Refactor sync-check.py

**Files:**
- Modify: `.claude/features/rabbit-cage/hooks/sync-check.py` (function `_collect_drifted_targets`, lines 131-170)

- [ ] **Step 1: Read sync-check.py** (needed before edit)

Read `.claude/features/rabbit-cage/hooks/sync-check.py` lines 131-170

- [ ] **Step 2: Replace _collect_drifted_targets**

Replace the entire `_collect_drifted_targets` function (from `def _collect_drifted_targets` through its closing `return drifted`) with:

```python
def _collect_drifted_targets(root: Path) -> list:
    """Inv 88 (CONTRACT-BACKLOG-21). Discover all active feature publish.json
    manifests and compare each check_on_stop=true target's source and
    destination by sha256. Returns names of drifted targets.

    Missing source files are skipped. A missing destination counts as drift.
    Malformed publish.json files are soft-failed with a stderr warning.
    """
    drifted = []
    for feature_json_path in sorted(root.glob(".claude/features/*/feature.json")):
        try:
            meta = json.loads(feature_json_path.read_text())
        except Exception as e:
            log_exc(_TAG, f"failed to read {feature_json_path.name}", e)
            continue
        if meta.get("status") == "retired":
            continue
        publish = feature_json_path.parent / "publish.json"
        if not publish.exists():
            continue
        try:
            data = json.loads(publish.read_text())
        except Exception as e:
            log_exc(_TAG, f"failed to read publish.json for {feature_json_path.parent.name}", e)
            continue
        feature_dir = feature_json_path.parent
        for target in data.get("targets", []):
            if target.get("type") != "copy-file":
                continue
            if not target.get("check_on_stop"):
                continue
            src = feature_dir / target["source"]
            dst = root / target["destination"]
            if not src.is_file():
                continue
            try:
                src_sha = hashlib.sha256(src.read_bytes()).hexdigest()
            except Exception as e:
                log_exc(_TAG, f"failed to hash source for {target.get('name')}", e)
                continue
            if dst.is_file():
                try:
                    dst_sha = hashlib.sha256(dst.read_bytes()).hexdigest()
                except Exception as e:
                    log_exc(_TAG, f"failed to hash destination for {target.get('name')}", e)
                    continue
                if src_sha != dst_sha:
                    drifted.append(target["name"])
            else:
                drifted.append(target["name"])
    return drifted
```

- [ ] **Step 3: Also update the docstring of render_surface_drift to remove the build-contract.json reference**

In `render_surface_drift`, change the docstring from:
```
    Iterates build-contract.json copy-file targets, collects the names of
```
to:
```
    Iterates per-feature publish.json copy-file targets, collects the names of
```

- [ ] **Step 4: Run rabbit-cage test suite to verify no regressions**

```bash
python3 .claude/features/rabbit-cage/test/run.py 2>&1 | tail -20
```
Expected: ALL TESTS PASSED (some tests will skip drift scenarios since they still use old build-contract.json temp structures — those will be fixed in Task 6+)

- [ ] **Step 5: Commit**

```bash
git add .claude/features/rabbit-cage/hooks/sync-check.py
git commit -m "feat(rabbit-cage): sync-check discovers per-feature publish.json for drift detection"
```

---

## Task 5: Refactor build.py + delete build-targets.py

**Files:**
- Modify: `.claude/features/rabbit-cage/scripts/build.py` (full rewrite)
- Delete: `.claude/features/rabbit-cage/scripts/build-targets.py`

- [ ] **Step 1: Read build.py** (needed before edit)

Read `.claude/features/rabbit-cage/scripts/build.py`

- [ ] **Step 2: Rewrite build.py**

Full new content:

```python
#!/usr/bin/env python3
"""build.py — unified workspace artifact builder.

Discovers per-feature publish.json manifests and builds all declared
copy-file targets. Source paths in each manifest are relative to the
feature directory; destination paths are relative to the repo root.

Usage: build.py [REPO_ROOT]

Version: 2.0.0
Owner: rabbit-workflow team (rabbit-cage)
Deprecation criterion: when Claude Code natively manages workspace artifact generation
"""

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _discover_manifests(root: Path):
    """Yield (feature_dir, manifest) for each active feature with publish.json."""
    for feature_json_path in sorted(root.glob(".claude/features/*/feature.json")):
        try:
            meta = json.loads(feature_json_path.read_text())
        except Exception:
            continue
        if meta.get("status") == "retired":
            continue
        publish = feature_json_path.parent / "publish.json"
        if not publish.exists():
            continue
        try:
            manifest = json.loads(publish.read_text())
        except Exception:
            sys.stderr.write(f"build: skipping malformed publish.json: {publish}\n")
            continue
        yield feature_json_path.parent, manifest


def main() -> int:
    script_dir = Path(__file__).resolve().parent
    if len(sys.argv) > 1:
        root = Path(sys.argv[1])
    else:
        try:
            out = subprocess.check_output(
                ["git", "-C", str(script_dir), "rev-parse", "--show-toplevel"],
                stderr=subprocess.DEVNULL,
            )
            root = Path(out.decode().strip())
        except Exception:
            sys.stderr.write("build: cannot determine REPO_ROOT (not a git repo, no arg)\n")
            return 1

    errors = 0
    for feature_dir, manifest in _discover_manifests(root):
        for target in manifest.get("targets", []):
            name = target["name"]
            if target.get("type") != "copy-file":
                sys.stderr.write(f"  [error] unknown type for target '{name}'\n")
                errors += 1
                continue
            src = feature_dir / target["source"]
            dst = root / target["destination"]
            if not src.is_file():
                sys.stderr.write(f"  [error] source not found: {src}\n")
                errors += 1
                continue
            dst.parent.mkdir(parents=True, exist_ok=True)
            content_changed = (not dst.is_file()) or (_sha256(src) != _sha256(dst))
            if content_changed:
                shutil.copy2(src, dst)
                print(f"  [built] {name}")
            else:
                print(f"  [no-op] {name}")
            # BUG-81: widen marker write to any copy-file destination under
            # .claude/skills/<name>/ (scripts, resources, SKILL.md).
            skill_match = re.match(r'^\.claude/skills/([^/]+)/', target["destination"])
            if skill_match and content_changed:
                marker = root / ".rabbit-skills-updated"
                with open(marker, "a") as f:
                    f.write(skill_match.group(1) + "\n")

    if errors:
        sys.stderr.write(f"\nbuild: {errors} error(s)\n")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 3: Run build.py and verify 20 targets build**

```bash
python3 .claude/features/rabbit-cage/scripts/build.py
```
Expected output: 20 lines of `[built]` or `[no-op]` — one per target across all 5 features. Verify no `[error]` lines.

- [ ] **Step 4: Delete build-targets.py**

```bash
git rm .claude/features/rabbit-cage/scripts/build-targets.py
```

- [ ] **Step 5: Commit**

```bash
git add .claude/features/rabbit-cage/scripts/build.py
git commit -m "feat(rabbit-cage): federated build.py discovers publish.json; delete build-targets.py"
```

---

## Task 6: Update sync-check drift test

**Files:**
- Modify: `.claude/features/rabbit-cage/test/test-RABBIT-CAGE-BACKLOG-21-surface-drift-files.py`

- [ ] **Step 1: Read the drift test**

Read `.claude/features/rabbit-cage/test/test-RABBIT-CAGE-BACKLOG-21-surface-drift-files.py`

- [ ] **Step 2: Replace write_contract with write_feature_manifest**

Update the import line:
```python
from test_helpers import REPO_ROOT, make_git_repo, run_sync, write_feature_manifest
```

Replace the `write_contract` helper function and all four test scenarios:

```python
# Remove the write_contract function entirely.

# t1: single drifted target
print("=== t1: single drifted copy-file target — its name is named ===")
root = make_git_repo()
tmproots.append(root)

feature_dir = write_feature_manifest(root, "fake-drift-t1", [{
    "name": "hooks/sync-check.py",
    "source": "hooks/sync-check.py",
    "destination": "dst/hooks/sync-check.py",
    "check_on_stop": True,
}])
os.makedirs(os.path.join(feature_dir, "hooks"), exist_ok=True)
write_file(os.path.join(feature_dir, "hooks/sync-check.py"), "# real source content\n")
write_file(os.path.join(root, "dst/hooks/sync-check.py"), "# stale destination content\n")

# t2: multiple drifted targets
root = make_git_repo()
tmproots.append(root)

feature_dir = write_feature_manifest(root, "fake-drift-t2", [
    {"name": "hooks/a.py", "source": "a.py", "destination": "dst/a.py", "check_on_stop": True},
    {"name": "settings/b.json", "source": "b.json", "destination": "dst/b.json", "check_on_stop": True},
])
write_file(os.path.join(feature_dir, "a.py"), "A source\n")
write_file(os.path.join(root, "dst/a.py"), "A destination stale\n")
write_file(os.path.join(feature_dir, "b.json"), "B source\n")
write_file(os.path.join(root, "dst/b.json"), "B destination stale\n")

# t3: zero drift
root = make_git_repo()
tmproots.append(root)

feature_dir = write_feature_manifest(root, "fake-clean-t3", [{
    "name": "hooks/clean.py",
    "source": "clean.py",
    "destination": "dst/clean.py",
    "check_on_stop": True,
}])
write_file(os.path.join(feature_dir, "clean.py"), "identical content\n")
write_file(os.path.join(root, "dst/clean.py"), "identical content\n")

# t4: check_on_stop=false drift is ignored
root = make_git_repo()
tmproots.append(root)

feature_dir = write_feature_manifest(root, "fake-optional-t4", [{
    "name": "optional/optional.py",
    "source": "optional.py",
    "destination": "dst/optional.py",
    "check_on_stop": False,
}])
write_file(os.path.join(feature_dir, "optional.py"), "src\n")
write_file(os.path.join(root, "dst/optional.py"), "dst stale\n")
```

- [ ] **Step 3: Run drift test to verify it passes**

```bash
python3 .claude/features/rabbit-cage/test/test-RABBIT-CAGE-BACKLOG-21-surface-drift-files.py
```
Expected: ALL TESTS PASSED

- [ ] **Step 4: Commit**

```bash
git add .claude/features/rabbit-cage/test/test-RABBIT-CAGE-BACKLOG-21-surface-drift-files.py
git commit -m "test(rabbit-cage): update BACKLOG-21 drift test for per-feature publish.json"
```

---

## Task 7: Update build marker tests (BUG4, stale-marker)

**Files:**
- Modify: `.claude/features/rabbit-cage/test/test-RABBIT-CAGE-BUG4.py`
- Modify: `.claude/features/rabbit-cage/test/test-RABBIT-CAGE-22-stale-marker.py`

Both tests use `make_contract(d, targets_with_absolute_paths)`. Replace with `write_feature_manifest`.

- [ ] **Step 1: Read test-RABBIT-CAGE-BUG4.py**

Read `.claude/features/rabbit-cage/test/test-RABBIT-CAGE-BUG4.py`

- [ ] **Step 2: Update BUG4 test**

In test-RABBIT-CAGE-BUG4.py:
1. Delete the `make_contract` function entirely.
2. Replace `from test_helpers import ...` with one that includes `write_feature_manifest` if test_helpers is imported there, or just remove the `make_contract` helper.
3. Replace the test body that calls `make_contract`:

```python
# Before the tests, set up the feature manifest (replaces make_contract calls):
SKILL_FEATURE_DIR = write_feature_manifest(tmproot, "test-skill", [{
    "name": "skills/test-skill/SKILL.md",
    "source": "skills/test-skill/SKILL.md",
    "destination": ".claude/skills/test-skill/SKILL.md",
}])
os.makedirs(os.path.join(SKILL_FEATURE_DIR, "skills/test-skill"), exist_ok=True)
SRC = os.path.join(SKILL_FEATURE_DIR, "skills/test-skill/SKILL.md")
DEST = os.path.join(tmproot, ".claude/skills/test-skill/SKILL.md")
MARKER = os.path.join(tmproot, ".rabbit-skills-updated")
with open(SRC, "w") as f:
    f.write("# Test skill v1\nbody\n")
```

Remove the `make_contract(tmproot, [...])` calls before t1, t2, t3 (the manifest is written once and stays).

Add `write_feature_manifest` import from test_helpers (BUG4 has its own `make_build_repo`, so add import at top or copy the function inline). Easiest: add at the top of the file:

```python
import sys
import os
_THIS = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _THIS)
from test_helpers import write_feature_manifest
```

- [ ] **Step 3: Read test-RABBIT-CAGE-22-stale-marker.py**

Read `.claude/features/rabbit-cage/test/test-RABBIT-CAGE-22-stale-marker.py`

- [ ] **Step 4: Update stale-marker test**

Same pattern: delete `make_contract`, import `write_feature_manifest` from test_helpers (the file already imports from test_helpers if it uses make_build_repo — but this file has its own make_build_repo; add the import).

Replace each `make_contract(tmproot, [...])` call with the appropriate `write_feature_manifest` call. The key mapping:

**t1 (SKILL.md marker):** source goes inside the feature dir
```python
SKILL_FEATURE_DIR = write_feature_manifest(tmproot, "test-skill", [{
    "name": "skills/test-skill/SKILL.md",
    "source": "skills/test-skill/SKILL.md",
    "destination": ".claude/skills/test-skill/SKILL.md",
}])
os.makedirs(os.path.join(tmproot, ".claude/features/test-skill/skills/test-skill"), exist_ok=True)
with open(os.path.join(SKILL_FEATURE_DIR, "skills/test-skill/SKILL.md"), "w") as f:
    f.write("# Test skill\n")
```

**t3 (commands target):** source goes inside a fake feature dir
```python
CMD_FEATURE_DIR = write_feature_manifest(tmproot, "fake-cmd-feature", [{
    "name": "commands/test-cmd.md",
    "source": "commands/test-cmd.md",
    "destination": ".claude/commands/test-cmd.md",
}])
os.makedirs(os.path.join(CMD_FEATURE_DIR, "commands"), exist_ok=True)
with open(os.path.join(CMD_FEATURE_DIR, "commands/test-cmd.md"), "w") as f:
    f.write("# Test cmd\n")
```

**t4 (README.md non-skills target):**
```python
README_FEATURE_DIR = write_feature_manifest(tmproot, "fake-readme-feature", [{
    "name": "README.md",
    "source": "readme-source.md",
    "destination": "README.md",
}])
with open(os.path.join(README_FEATURE_DIR, "readme-source.md"), "w") as f:
    f.write("# README\n")
```

**t5 (two skill features):**
```python
feat_a_dir = write_feature_manifest(tmproot, "feat-a", [{
    "name": "skills/feat-a/SKILL.md",
    "source": "skills/feat-a/SKILL.md",
    "destination": ".claude/skills/feat-a/SKILL.md",
}])
feat_b_dir = write_feature_manifest(tmproot, "feat-b", [{
    "name": "skills/feat-b/SKILL.md",
    "source": "skills/feat-b/SKILL.md",
    "destination": ".claude/skills/feat-b/SKILL.md",
}])
os.makedirs(os.path.join(feat_a_dir, "skills/feat-a"), exist_ok=True)
os.makedirs(os.path.join(feat_b_dir, "skills/feat-b"), exist_ok=True)
with open(os.path.join(feat_a_dir, "skills/feat-a/SKILL.md"), "w") as f:
    f.write("# Feat A\n")
with open(os.path.join(feat_b_dir, "skills/feat-b/SKILL.md"), "w") as f:
    f.write("# Feat B\n")
# Remove old make_contract call for t5
```

- [ ] **Step 5: Run both tests**

```bash
python3 .claude/features/rabbit-cage/test/test-RABBIT-CAGE-BUG4.py
python3 .claude/features/rabbit-cage/test/test-RABBIT-CAGE-22-stale-marker.py
```
Expected: ALL TESTS PASSED for both

- [ ] **Step 6: Commit**

```bash
git add .claude/features/rabbit-cage/test/test-RABBIT-CAGE-BUG4.py \
        .claude/features/rabbit-cage/test/test-RABBIT-CAGE-22-stale-marker.py
git commit -m "test(rabbit-cage): update marker tests for publish.json fixture model"
```

---

## Task 8: Update remaining rabbit-cage tests

**Files:**
- Modify: `test-build-non-git-dir.py`
- Modify: `test-team-wide-permissions.py`
- Modify: `test-RABBIT-CAGE-WAVE4-bug-cleanup.py`
- Modify: `test-RABBIT-CAGE-BACKLOG2-python-only.py`
- Modify: `test-no-embedded-python3.py`
- Modify: `test-generated-surface.py`
- Modify: `test-BACKLOG-11-rabbit-config-skill.py`
- Modify: `test-RABBIT-CAGE-BACKLOG9-green-messages.py`
- Modify: `test-RABBIT-CAGE-BACKLOG7-visual-messages.py`

All paths relative to `.claude/features/rabbit-cage/test/`.

- [ ] **Step 1: Update test-build-non-git-dir.py**

Read the file. Make these changes:
- t2: replace `if "RABBIT_ROOT" in build_src` with `if "_discover_manifests" in build_src` (the new build.py uses this function, not RABBIT_ROOT).
- t3: Replace the generate-claude-md test with a publish.json test:

```python
# t3: build.py in a non-git dir processes publish.json targets when REPO_ROOT arg given
tmpdir_target = tempfile.mkdtemp()
try:
    # Create a minimal feature with publish.json
    feature_dir = os.path.join(tmpdir_target, ".claude/features/fake-feature")
    os.makedirs(feature_dir, exist_ok=True)
    with open(os.path.join(feature_dir, "feature.json"), "w") as f:
        json.dump({"name": "fake-feature", "version": "1.0.0", "owner": "test",
                   "status": "active", "deprecation_criterion": "n/a"}, f)
    os.makedirs(os.path.join(feature_dir, "src"), exist_ok=True)
    with open(os.path.join(feature_dir, "src/hello.txt"), "w") as f:
        f.write("hello\n")
    publish = {
        "schema_version": "1.0.0", "feature": "fake-feature",
        "owner": "test", "deprecation_criterion": "n/a",
        "targets": [{"name": "hello.txt", "type": "copy-file",
                     "source": "src/hello.txt", "destination": "dst/hello.txt",
                     "check_on_stop": False}],
    }
    with open(os.path.join(feature_dir, "publish.json"), "w") as f:
        json.dump(publish, f)

    result = subprocess.run(
        [sys.executable, BUILD_SH, tmpdir_target],
        capture_output=True, text=True,
    )
    if result.returncode == 0 and os.path.isfile(os.path.join(tmpdir_target, "dst/hello.txt")):
        ok(3, "build.py processes publish.json targets in non-git dir when REPO_ROOT arg given")
    else:
        fail_t(3, f"build.py failed in non-git dir: rc={result.returncode} stderr={result.stderr!r}")
finally:
    shutil.rmtree(tmpdir_target, ignore_errors=True)
```

- [ ] **Step 2: Update test-team-wide-permissions.py**

Read the file. Changes:
1. Find `BUILD_TARGETS_PY` constant and replace with `BUILD_PY`:
   ```python
   BUILD_PY = os.path.join(REPO_ROOT, ".claude", "features", "rabbit-cage", "scripts", "build.py")
   ```
2. Remove the `BUILD_TARGETS_PY` line (which points to build-targets.py).
3. In `test_build_py_propagates_permissions_e2e_sandboxed`, replace the entire sandbox setup:

```python
def test_build_py_propagates_permissions_e2e_sandboxed():
    sandbox = tempfile.mkdtemp(prefix="test-team-wide-permissions-")
    try:
        feature_dir = os.path.join(sandbox, ".claude/features/fake-settings")
        os.makedirs(feature_dir, exist_ok=True)
        sandbox_src = os.path.join(feature_dir, "settings.json")
        shutil.copy(SOURCE_SETTINGS, sandbox_src)

        data = json.loads(open(sandbox_src).read())
        probe = "Bash(test-probe-do-not-keep)"
        data["permissions"]["deny"].append(probe)
        with open(sandbox_src, "w") as f:
            json.dump(data, f, indent=2)

        with open(os.path.join(feature_dir, "feature.json"), "w") as f:
            json.dump({"name": "fake-settings", "version": "1.0.0", "owner": "test",
                       "status": "active", "deprecation_criterion": "n/a"}, f)
        dst_rel = ".claude/settings.json"
        publish = {
            "schema_version": "1.0.0", "feature": "fake-settings",
            "owner": "test", "deprecation_criterion": "test",
            "targets": [{"name": "settings.json", "type": "copy-file",
                         "source": "settings.json", "destination": dst_rel,
                         "check_on_stop": False}],
        }
        with open(os.path.join(feature_dir, "publish.json"), "w") as f:
            json.dump(publish, f, indent=2)

        sandbox_dst = os.path.join(sandbox, dst_rel)
        os.makedirs(os.path.dirname(sandbox_dst), exist_ok=True)

        result = subprocess.run(
            [sys.executable, BUILD_PY, sandbox],
            cwd=sandbox, capture_output=True, text=True,
        )
        assert result.returncode == 0, (
            f"build.py failed: rc={result.returncode}\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )
        new_dest = json.loads(open(sandbox_dst).read())
        assert probe in new_dest.get("permissions", {}).get("deny", []), (
            "build.py did not propagate the probe deny entry — copy-file broken"
        )
    finally:
        shutil.rmtree(sandbox, ignore_errors=True)
```

- [ ] **Step 3: Update test-RABBIT-CAGE-WAVE4-bug-cleanup.py**

Read the file. Changes:
1. Lines ~157-170 (BUG-44/BUG-81 checks): Change `bt_py = read(os.path.join(SCRIPTS, "build-targets.py"))` to `bt_py = read(os.path.join(SCRIPTS, "build.py"))`. The checks for `"[no-op]"` and `"content_changed"` and the `skill_match` regex remain valid — they're now in build.py.

2. Find the `for t, script in [(21, "scripts/build-targets.py"), ...]` loop. Remove the `(21, "scripts/build-targets.py")` entry. Renumber if needed.

- [ ] **Step 4: Update test-RABBIT-CAGE-BACKLOG2-python-only.py**

Read the file. Changes:
1. In `expected_scripts` list (line ~61), remove `"build-targets.py"`.
2. In section 7 (build-contract check), replace with:

```python
# [7] rabbit-cage/publish.json targets reference .py for rabbit-cage hooks
print("[7] rabbit-cage publish.json targets reference .py for rabbit-cage hooks")
publish_path = os.path.join(REPO_ROOT, ".claude/features/rabbit-cage/publish.json")
if os.path.isfile(publish_path):
    pub = json.load(open(publish_path))
    sh_targets = [
        t.get("source", "") for t in pub.get("targets", [])
        if t.get("type") == "copy-file" and t.get("source", "").endswith(".sh")
    ]
    if not sh_targets:
        passed("no rabbit-cage .sh paths in rabbit-cage/publish.json targets")
    else:
        failed(f"rabbit-cage/publish.json still references .sh files: {sh_targets}")
else:
    failed(f"rabbit-cage/publish.json not found at {publish_path}")
```

- [ ] **Step 5: Update test-no-embedded-python3.py**

Read the file. Find the line that includes `"build-targets.py"` in a list and remove it.

- [ ] **Step 6: Update test-generated-surface.py**

Read the file. Replace the `t2` check (which asserts build-contract.json exists) with a check that all active features have publish.json files:

```python
# t2: at least one active feature publish.json exists
features_dir = os.path.join(REPO_ROOT, ".claude/features")
publish_count = sum(
    1 for d in os.listdir(features_dir)
    if os.path.isfile(os.path.join(features_dir, d, "publish.json"))
    and json.load(open(os.path.join(features_dir, d, "feature.json"))).get("status") != "retired"
    if os.path.isfile(os.path.join(features_dir, d, "feature.json"))
)
if publish_count >= 5:
    ok(2, f"found {publish_count} active feature publish.json manifests")
else:
    fail_t(2, f"expected >= 5 active feature publish.json files, found {publish_count}")
```

Also remove the `CONTRACT = ...` constant and the `with open(CONTRACT)` call for t3+. Instead iterate per-feature publish.json for drift check:

```python
# t3+: all check_on_stop=true targets in all feature publish.json files are in sync
t = 3
for feature_dir_name in sorted(os.listdir(features_dir)):
    feature_dir = os.path.join(features_dir, feature_dir_name)
    fj = os.path.join(feature_dir, "feature.json")
    pj = os.path.join(feature_dir, "publish.json")
    if not os.path.isfile(fj) or not os.path.isfile(pj):
        continue
    if json.load(open(fj)).get("status") == "retired":
        continue
    manifest = json.load(open(pj))
    for target in manifest.get("targets", []):
        if not (target.get("check_on_stop") and target["type"] == "copy-file"):
            continue
        name = target["name"]
        src_abs = os.path.join(feature_dir, target["source"])
        dst_abs = os.path.join(REPO_ROOT, target["destination"])
        if not os.path.isfile(src_abs):
            fail_t(t, f"{name}: source missing: {src_abs}")
            t += 1
            continue
        if not os.path.isfile(dst_abs):
            fail_t(t, f"{name}: destination missing: {dst_abs}")
        elif not filecmp.cmp(src_abs, dst_abs, shallow=False):
            fail_t(t, f"{name}: source and destination differ")
        else:
            ok(t, f"{name}: source and destination in sync")
        t += 1
```

- [ ] **Step 7: Update test-BACKLOG-11-rabbit-config-skill.py**

Read the file. Change the t6 check (lines ~145-162) to read from `rabbit-cage/publish.json` instead of `build-contract.json`:

```python
# t6: rabbit-cage/publish.json registers the new SKILL.md and scripts as copy-file targets
publish_path = os.path.join(REPO_ROOT, ".claude/features/rabbit-cage/publish.json")
if os.path.isfile(publish_path):
    with open(publish_path) as f:
        publish = json.load(f)
    by_name = {t.get("name"): t for t in publish.get("targets", [])}
    skill_entry = by_name.get("skills/rabbit-config/SKILL.md")
    script_entry = by_name.get("skills/rabbit-config/scripts/rabbit-config.py")
    if skill_entry and skill_entry.get("destination") == ".claude/skills/rabbit-config/SKILL.md":
        ok(6, "rabbit-cage/publish.json registers skills/rabbit-config/SKILL.md")
    else:
        fail_t(6, "rabbit-cage/publish.json missing skills/rabbit-config/SKILL.md entry")
    if script_entry and script_entry.get("destination") == ".claude/skills/rabbit-config/scripts/rabbit-config.py":
        ok(7, "rabbit-cage/publish.json registers skills/rabbit-config/scripts/rabbit-config.py")
    else:
        fail_t(7, "rabbit-cage/publish.json missing rabbit-config.py script entry (root cause fix)")
else:
    fail_t(6, "rabbit-cage/publish.json missing")
    fail_t(7, "rabbit-cage/publish.json missing")
```

Note: this adds a t7 check for the new `rabbit-config.py` script entry. Renumber subsequent tests if needed.

- [ ] **Step 8: Update test-RABBIT-CAGE-BACKLOG9-green-messages.py**

Read the file. Find the section that creates `build-contract.json` (around line 135). Replace with:

```python
# Create feature manifest with drift for surface-drift test
write_feature_manifest(tmp2, "fake-drift", [{
    "name": "hooks/x.py",
    "source": "x.py",
    "destination": "dst/x.py",
    "check_on_stop": True,
}])
feature_dir_drift = os.path.join(tmp2, ".claude/features/fake-drift")
os.makedirs(os.path.join(tmp2, "dst"), exist_ok=True)
with open(os.path.join(feature_dir_drift, "x.py"), "w") as f:
    f.write("source\n")
with open(os.path.join(tmp2, "dst/x.py"), "w") as f:
    f.write("destination stale\n")
```

Add `write_feature_manifest` to import from test_helpers if not already imported.

- [ ] **Step 9: Update test-RABBIT-CAGE-BACKLOG7-visual-messages.py**

Read the file. Find the `build-contract.json` creation around line 139. Same pattern as BACKLOG9 — replace with:

```python
write_feature_manifest(tmproot2, "fake-drift", [{
    "name": "hooks/x.py",
    "source": "x.py",
    "destination": "dst/x.py",
    "check_on_stop": True,
}])
feature_dir_drift = os.path.join(tmproot2, ".claude/features/fake-drift")
os.makedirs(os.path.join(tmproot2, "dst"), exist_ok=True)
with open(os.path.join(feature_dir_drift, "x.py"), "w") as f:
    f.write("source\n")
with open(os.path.join(tmproot2, "dst/x.py"), "w") as f:
    f.write("destination stale\n")
```

Add `write_feature_manifest` to import from test_helpers.

- [ ] **Step 10: Run full rabbit-cage test suite**

```bash
python3 .claude/features/rabbit-cage/test/run.py 2>&1 | tail -5
```
Expected: ALL TESTS PASSED

- [ ] **Step 11: Commit**

```bash
git add .claude/features/rabbit-cage/test/
git commit -m "test(rabbit-cage): update all tests for federated publish.json model"
```

---

## Task 9: Update contract tests

**Files:**
- Modify: `.claude/features/contract/test/run.py`
- Modify: `.claude/features/contract/test/test-files-exist.py`
- Modify: `.claude/features/contract/test/test-retirement-semantics.py`
- Modify: `.claude/features/contract/test/test-retired-artifacts.py`
- Modify: `.claude/features/contract/test/test-bug-fixes-cycle.py`
- Modify: `.claude/features/contract/test/test-no-dead-contract-scripts.py`
- Modify: `.claude/features/contract/test/test-rabbit-feature-skills-deployment.py`

- [ ] **Step 1: Update run.py**

Read run.py. Make these changes:
1. Remove the two lines:
   ```python
   run_test("test-build-contract.py")
   run_test("test-build-contract-post-consolidation.py")
   ```
2. Add in their place (position them near the other schema/contract tests):
   ```python
   run_test("test-publish-manifest-schema.py")
   run_test("test-publish-manifests.py")
   ```

- [ ] **Step 2: Update test-files-exist.py**

Read the file. Change line 92:
```python
check_file("test/test-build-contract.py")
```
to:
```python
check_file("test/test-publish-manifests.py")
check_file("test/test-publish-manifest-schema.py")
```

- [ ] **Step 3: Update test-retirement-semantics.py**

Read the file. Change t6 (lines ~157-171) which checks build-contract.json for the tdd-step.py source:

```python
# t6: tdd-state-machine/publish.json tdd-step.py source points to tdd-state-machine
TDD_SM_PUBLISH = os.path.join(REPO_ROOT, ".claude/features/tdd-state-machine/publish.json")
if os.path.isfile(TDD_SM_PUBLISH):
    with open(TDD_SM_PUBLISH) as f:
        pub = json.load(f)
    tdd_step_entry = next(
        (t for t in pub.get("targets", [])
         if t.get("name") == "agents/tdd-subagent/scripts/tdd-step.py"),
        None,
    )
    if tdd_step_entry is None:
        ko(6, "tdd-state-machine/publish.json missing tdd-step.py target")
    elif tdd_step_entry.get("source") != "scripts/tdd-step.py":
        ko(6, f"tdd-step.py source = {tdd_step_entry.get('source')!r}, expected 'scripts/tdd-step.py'")
    else:
        ok(6, "tdd-state-machine/publish.json tdd-step.py source is 'scripts/tdd-step.py'")
else:
    ko(6, f"tdd-state-machine/publish.json not found at {TDD_SM_PUBLISH}")
```

Also remove `BUILD_CONTRACT = ...` constant if it's no longer used anywhere else in the file.

- [ ] **Step 4: Update test-retired-artifacts.py**

Read the file. Change b7 (lines ~124-137) which checks build-contract.json for rabbit-workspace-map:

```python
# b7: no feature publish.json declares rabbit-workspace-map skill
b7_fail = False
for feature_dir_name in os.listdir(os.path.join(REPO_ROOT, ".claude/features")):
    pub = os.path.join(REPO_ROOT, ".claude/features", feature_dir_name, "publish.json")
    if not os.path.isfile(pub):
        continue
    try:
        data = json.load(open(pub))
    except Exception:
        continue
    ws_entries = [
        t for t in data.get("targets", [])
        if "rabbit-workspace-map" in t.get("name", "")
        or "rabbit-workspace-map" in t.get("source", "")
        or "rabbit-workspace-map" in t.get("destination", "")
    ]
    if ws_entries:
        ko("b7", f"{feature_dir_name}/publish.json declares rabbit-workspace-map: {[e.get('name') for e in ws_entries]}")
        b7_fail = True
if not b7_fail:
    ok("b7", "no feature publish.json declares rabbit-workspace-map entry")
```

Also change section a3: remove `"test-build-contract.py"` from the `ALLOWED` set (the file will be deleted):
```python
ALLOWED = {SELF}
```

- [ ] **Step 5: Update test-bug-fixes-cycle.py**

Read the file. Change the BACKLOG-6 section (lines ~130-144) to read per-feature publish.json files instead of build-contract.json:

```python
# BACKLOG-6: publish.json copy-file destinations match sources by basename
features_dir = os.path.join(REPO_ROOT, ".claude/features")
mismatches = []
for feature_dir_name in os.listdir(features_dir):
    pub = os.path.join(features_dir, feature_dir_name, "publish.json")
    if not os.path.isfile(pub):
        continue
    try:
        data = json.load(open(pub))
    except Exception:
        continue
    for target in data.get("targets", []):
        if target.get("type") == "copy-file":
            src = target.get("source", "")
            dst = target.get("destination", "")
            if os.path.basename(src) != os.path.basename(dst):
                mismatches.append((f"{feature_dir_name}/{src}", dst))
if not mismatches:
    ok("BACKLOG-6: every publish.json copy-file target's source basename matches destination basename")
else:
    ko(f"BACKLOG-6: copy-file basename mismatches: {mismatches}")
```

Remove the `bc_path = ...` and `with open(bc_path)` lines.

- [ ] **Step 6: Update test-no-dead-contract-scripts.py**

Read the file. Remove the stale exclusion for build-contract.json (line ~131):
```python
if norm == os.path.join(FEATURE_DIR, "build-contract.json"):
    continue
```
Delete those two lines.

- [ ] **Step 7: Update test-rabbit-feature-skills-deployment.py**

Read the file. Replace entire file content:

```python
#!/usr/bin/env python3
"""test-rabbit-feature-skills-deployment.py — CONTRACT-BUG-41 (bundled deploy).

End-to-end assertions for the bundled deployment of all five
rabbit-feature skills via rabbit-feature/publish.json:

  - rabbit-feature-touch
  - rabbit-feature-scope
  - rabbit-feature-spec
  - rabbit-feature-new   (BUG-41)
  - rabbit-feature-audit (BUG-41)

Each skill MUST have:
  - an entry in rabbit-feature/publish.json with the correct source/destination
  - a SKILL.md source file on disk under .claude/features/rabbit-feature/skills/
  - a deployed copy at .claude/skills/<name>/SKILL.md

Non-interactive. Exits non-zero on failure.
"""

import json
import os
import sys

FEATURE_DIR = os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
)
REPO_ROOT = os.path.normpath(os.path.join(FEATURE_DIR, "..", "..", ".."))
RABBIT_FEATURE_DIR = os.path.join(REPO_ROOT, ".claude", "features", "rabbit-feature")
PUBLISH_PATH = os.path.join(RABBIT_FEATURE_DIR, "publish.json")

EXPECTED_SKILLS = [
    "rabbit-feature-touch",
    "rabbit-feature-scope",
    "rabbit-feature-spec",
    "rabbit-feature-new",
    "rabbit-feature-audit",
]

passed = 0
failed = 0


def ok(n, msg):
    global passed
    print(f"  PASS t{n}: {msg}")
    passed += 1


def ko(n, msg):
    global failed
    print(f"  FAIL t{n}: {msg}", file=sys.stderr)
    failed += 1


print("test-rabbit-feature-skills-deployment.py")

with open(PUBLISH_PATH) as f:
    data = json.load(f)

by_name = {t.get("name"): t for t in data.get("targets", [])}

for i, skill in enumerate(EXPECTED_SKILLS, start=1):
    name = f"skills/{skill}/SKILL.md"
    expected_source = f"skills/{skill}/SKILL.md"
    expected_dest = f".claude/skills/{skill}/SKILL.md"

    entry = by_name.get(name)
    if entry is None:
        ko(i, f"no entry named {name} in rabbit-feature/publish.json")
        continue
    if entry.get("source") != expected_source:
        ko(i, f"{name}: source {entry.get('source')!r} != {expected_source!r}")
        continue
    if entry.get("destination") != expected_dest:
        ko(i, f"{name}: destination {entry.get('destination')!r} != {expected_dest!r}")
        continue

    source_abs = os.path.join(RABBIT_FEATURE_DIR, expected_source)
    if not os.path.isfile(source_abs):
        ko(i, f"{name}: source file missing: {source_abs}")
        continue

    dest_abs = os.path.join(REPO_ROOT, expected_dest)
    if not os.path.isfile(dest_abs):
        ko(i, f"{name}: deployed SKILL.md missing at {dest_abs}")
        continue

    ok(i, f"{skill}: source + destination wired and deployed")

print()
print(f"Results: {passed} passed, {failed} failed")
sys.exit(0 if failed == 0 else 1)
```

- [ ] **Step 8: Run contract test suite (before file deletions)**

```bash
python3 .claude/features/contract/test/run.py 2>&1 | tail -5
```
Expected: ALL TESTS PASSED

- [ ] **Step 9: Commit**

```bash
git add .claude/features/contract/test/
git commit -m "test(contract): update tests for federated publish.json model"
```

---

## Task 10: Delete retired files

**Files:**
- Delete: `.claude/features/contract/build-contract.json`
- Delete: `.claude/features/contract/schemas/build-contract.schema.json`
- Delete: `.claude/features/contract/test/test-build-contract.py`
- Delete: `.claude/features/contract/test/test-build-contract-post-consolidation.py`

(build-targets.py was already deleted in Task 5)

- [ ] **Step 1: Delete all retired files**

```bash
git rm .claude/features/contract/build-contract.json \
       .claude/features/contract/schemas/build-contract.schema.json \
       .claude/features/contract/test/test-build-contract.py \
       .claude/features/contract/test/test-build-contract-post-consolidation.py
```

- [ ] **Step 2: Run full contract test suite**

```bash
python3 .claude/features/contract/test/run.py 2>&1 | tail -5
```
Expected: ALL TESTS PASSED (the deleted tests are no longer in run.py)

- [ ] **Step 3: Run full build to verify deployed surface**

```bash
python3 .claude/features/rabbit-cage/scripts/build.py
```
Expected: 20 lines of `[built]` or `[no-op]`, 0 errors. New `[built]` for `skills/rabbit-config/scripts/rabbit-config.py`.

- [ ] **Step 4: Verify deployed rabbit-config.py exists**

```bash
ls .claude/skills/rabbit-config/scripts/
```
Expected: `rabbit-config.py` present

- [ ] **Step 5: Commit**

```bash
git commit -m "refactor(contract): delete build-contract.json and related artifacts (CONTRACT-BACKLOG-21)"
```

---

## Task 11: Run all 7 test suites + close backlog

**Files:** No file changes — verification only.

- [ ] **Step 1: Run all 7 feature test suites**

```bash
for f in contract rabbit-cage rabbit-feature rabbit-file tdd-state-machine tdd-subagent policy; do
  echo "=== $f ===" && python3 .claude/features/$f/test/run.py 2>&1 | tail -3
done
```
Expected: ALL TESTS PASSED for all 7 suites.

- [ ] **Step 2: Verify sync-check finds no drift**

```bash
python3 .claude/features/rabbit-cage/scripts/build.py
```
Expected: all `[no-op]` (built in Task 10 Step 3)

- [ ] **Step 3: Final commit and push**

```bash
git add -A
git status  # verify nothing untracked
git log --oneline -8  # review commit history
```

Create PR:
```bash
gh pr create --title "feat: federate build manifests — per-feature publish.json (CONTRACT-BACKLOG-21)" \
  --body "$(cat <<'EOF'
## Summary
- Adds `contract/schemas/publish-manifest.schema.json` as the canonical schema for per-feature publish manifests
- Creates `publish.json` for all 5 active publishing features (rabbit-cage, rabbit-feature, rabbit-file, tdd-subagent, tdd-state-machine)
- Refactors `build.py` to discover + execute from per-feature manifests; deletes `build-targets.py`
- Refactors `sync-check.py` `_collect_drifted_targets` to iterate per-feature manifests
- Fixes root-cause gap: `rabbit-config/scripts/rabbit-config.py` now declared in rabbit-cage's `publish.json` and deployed to `.claude/skills/rabbit-config/scripts/`
- Deletes `build-contract.json`, `build-contract.schema.json`, `test-build-contract.py`, `test-build-contract-post-consolidation.py`

## Test plan
- [ ] All 7 feature test suites pass: contract, rabbit-cage, rabbit-feature, rabbit-file, tdd-state-machine, tdd-subagent, policy
- [ ] `build.py` produces 20 targets with no errors
- [ ] `.claude/skills/rabbit-config/scripts/rabbit-config.py` exists after build

🤖 Generated with [Claude Code](https://claude.ai/claude-code)
EOF
)"
```

- [ ] **Step 4: After PR merges, close CONTRACT-BACKLOG-21**

```bash
python3 .claude/features/rabbit-file/scripts/item-status.py close \
  --feature contract --type backlog --id CONTRACT-BACKLOG-21 \
  --note "Implemented: per-feature publish.json, build.py federated discovery, sync-check.py updated, build-contract.json retired"
```

**Only run this step AFTER the PR is merged to main.**

---

## Self-Review Notes

1. **Spec coverage:** All 7 design decisions are covered. The rabbit-config.py deployment gap is fixed in Task 2 (publish.json). The schema validation test covers Task 1 design. Drift detection covers Tasks 4+6. Source analysis tests (WAVE4, BACKLOG2) preserve BUG-44/BUG-81 regressions.

2. **Type consistency:** `write_feature_manifest(tmproot, feature_name, targets)` signature is consistent across all tasks that use it (Tasks 3, 6, 7, 8). The `targets` dict structure (name, source, destination, check_on_stop) is consistent.

3. **Placeholder scan:** No TBD. Task 8 includes concrete code for each test update. Task 9 includes complete new file content for test-rabbit-feature-skills-deployment.py.

4. **Ordering:** Tasks depend on each other in order: schema must exist before test-publish-manifests runs (Tasks 1→2), test_helpers must have write_feature_manifest before drift/marker tests use it (Tasks 3→6,7,8), sync-check must be refactored before drift test can verify it (Tasks 4→6), build.py must be refactored before build marker tests can work (Tasks 5→7), all tests must pass before file deletions (Tasks 8+9 before 10).
