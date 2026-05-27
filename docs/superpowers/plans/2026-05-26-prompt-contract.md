# Prompt-Contract Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> **Execution model in this repo:** every task that edits files under `.claude/features/<X>/` MUST be performed via `rabbit-feature-touch` on feature `<X>` (which itself runs the 7-step TDD cycle via the TDD subagent dispatcher). Do NOT direct-edit scope-protected files. Tasks are still written in standard TDD-step form so the impl-suggestion handed to the TDD subagent is fully concrete.

**Goal:** Implement the prompt-contract per the design at `docs/superpowers/specs/2026-05-26-prompt-contract-design.md`. Federate per-feature `prompts` declarations into each `feature.json`; contract owns the schema, templates, assembler script, PreToolUse hook, and Stop-event runtime APIs. Closes CONTRACT-BACKLOG-1.

**Architecture:** Schemas + templates + assembler + hook + runtime APIs all owned by `contract` feature. Each other feature declares a `prompts` section in its own `feature.json` listing each skill/subagent it surfaces with the policy files to inject + named slots. Storage of assembled prompts at `.rabbit/prompts/`. Existing meta-contract validator (Inv 43) extends to validate the new section.

**Tech Stack:** Python 3 stdlib only. JSON Schema draft-07 (as documentation; validator is hand-rolled — matches existing meta-contract pattern). PreToolUse hook via Claude Code hook contract.

---

## Universal rules (apply to every task)

These match the conventions surfaced during the meta-contract foundation plan and apply to every task in this plan.

**R1 — Every new test wired into `test/run.py` in the same commit.** Each feature's `test/run.py` is self-enforcing (a meta-test fails if any active `test-*.py` is not invoked). Add `run_test("<new-test-name>.py")` to `run.py` BEFORE the commit step.

**R2 — Every new schema file carries top-level `schema_version`, `owner`, `deprecation_criterion`.** Per spec-rules.md. Use:
```json
"schema_version": "1.0.0",
"owner": "rabbit-workflow team",
"deprecation_criterion": "<one-line condition for retirement>"
```
The corresponding shape test asserts these three fields are present and non-empty strings.

**R3 — Every new Python script under `.claude/features/<X>/scripts/` carries module-level docstring with Version, Owner, Deprecation criterion.** Per Inv 16 of contract spec.

**R4 — Every new entry under `.claude/features/contract/scripts/` (not `enforcement/`) needs at least one production caller outside the contract feature itself.** Per Inv 34. New scripts created here in Phase A (`build-prompt.py`) become production callers when Phase B / C / D land; the regression test `test-no-dead-contract-scripts.py` will be temporarily satisfied by callers inside Phase A's own test files, then by real callers from later phases.

**R5 — All implementation goes through `rabbit-feature-touch` per feature.** No direct edits to scope-protected files. The impl-suggestion handed to the TDD subagent should be the per-task code/test content from this plan.

---

## Files to be created/modified (full list)

**Phase A (contract feature):**

Create:
- `.claude/features/contract/schemas/prompts.schema.json`
- `.claude/features/contract/templates/prompts/` (directory; remains empty until Phase B)
- `.claude/features/contract/scripts/build-prompt.py`
- `.claude/features/contract/scripts/enforcement/check-prompts-section.py`
- `.claude/features/contract/hooks/prompt-injector.py`
- `.claude/features/contract/lib/policy_block.py`
- `.claude/features/contract/test/test-prompts-schema-shape.py`
- `.claude/features/contract/test/test-check-prompts-section.py`
- `.claude/features/contract/test/test-build-prompt.py`
- `.claude/features/contract/test/test-prompt-injector-hook.py`
- `.claude/features/contract/test/test-policy-block-lib.py`
- `.claude/features/contract/test/test-runtime-cleanup-old-prompts.py`
- `.claude/features/contract/test/test-runtime-check-prompt-injection-failures.py`

Modify:
- `.claude/features/contract/lib/checks.py` — add `validate_prompts_section`, `check_prompts_section`; extend `validate_meta_contract` dispatch
- `.claude/features/contract/lib/runtime.py` — add `cleanup_old_prompts`, `check_prompt_injection_failures`
- `.claude/features/contract/schemas/feature.json.schema.json` — add `prompts` as optional `$ref`
- `.claude/features/contract/schemas/runtime.schema.json` — add 2 new APIs to closed enum
- `.claude/features/contract/scripts/policy-block.py` — refactor to import shared framing from `lib/policy_block.py`
- `.claude/features/contract/feature.json` — populate `manifest` (one `publish_hook` entry) and `runtime` (two Stop entries) sections
- `.claude/features/contract/docs/spec/spec.md` — amend "Meta-contract sections" paragraph, add invariants (Inv 51–55) for prompts schema / lint / build-prompt.py / hook / runtime APIs
- `.claude/features/contract/test/run.py` — wire in 7 new tests
- `.claude/features/contract/test/test-runtime-schema-shape.py` — add 2 new APIs

**Phase B (tdd-subagent feature):**

Create:
- `.claude/features/contract/templates/prompts/tdd-subagent.txt` (owned by contract, but content authored here)
- `.claude/features/tdd-subagent/test/test-dispatch-uses-build-prompt.py`

Modify:
- `.claude/features/tdd-subagent/scripts/dispatch-tdd-subagent.py` — replace inline f-string assembly with `build-prompt.py` invocation
- `.claude/features/tdd-subagent/feature.json` — add `prompts` section with `tdd-subagent` entry
- `.claude/features/tdd-subagent/docs/spec/spec.md` — amend invariants Inv 7–24 to reference the template file rather than f-string assembly
- `.claude/features/tdd-subagent/test/run.py` — wire in new test

**Phase C (per-feature sweep — parallelizable):**

For each of {rabbit-feature, rabbit-file, rabbit-config}:

Create:
- One template file per declared callable at `.claude/features/contract/templates/prompts/<id>.txt`
- One test asserting the `prompts` section is present and valid

Modify:
- `.claude/features/<X>/feature.json` — add `prompts` section
- `.claude/features/<X>/docs/spec/spec.md` — add invariant describing the `prompts` section
- `.claude/features/<X>/test/run.py` — wire in new test

**Phase D (cleanup on contract):**

Delete:
- `.claude/features/contract/templates/subagent-launch-template.txt` (dead, superseded by per-callable templates)

Modify:
- `.claude/features/contract/docs/spec/spec.md` — remove the deleted template from Surface list

---

# Phase A — Contract Foundation

Goal: land the schema, lib extensions, assembler, hook, and runtime APIs. After Phase A lands, no behavior changes anywhere — no feature declares a `prompts` entry yet. Phase A is shippable in isolation.

**Execution:** one `rabbit-feature-touch` cycle on `contract`. The cycle's impl-suggestion combines Tasks A1–A6 below into a single TDD round. If size becomes a concern at dispatch time (the 90KB observation from CONTRACT-BACKLOG-1), split into two cycles: (A1+A2+A6) "schema + lint + spec amendment" then (A3+A4+A5) "assembler + hook + runtime".

## Task A1: prompts schema

**Files:**
- Create: `.claude/features/contract/schemas/prompts.schema.json`
- Create: `.claude/features/contract/test/test-prompts-schema-shape.py`
- Modify: `.claude/features/contract/schemas/feature.json.schema.json`
- Modify: `.claude/features/contract/test/run.py`

- [ ] **Step 1: Write the failing shape test**

Create `.claude/features/contract/test/test-prompts-schema-shape.py`:

```python
#!/usr/bin/env python3
"""Shape test for prompts.schema.json — verifies schema_version/owner/deprecation_criterion
metadata, draft-07 declaration, top-level type=array, item shape, and field constraints."""

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]
SCHEMA = REPO_ROOT / ".claude/features/contract/schemas/prompts.schema.json"

def main():
    if not SCHEMA.exists():
        print(f"FAIL: schema file missing: {SCHEMA}")
        return 1
    schema = json.loads(SCHEMA.read_text())

    failures = []
    def ok(msg): print(f"OK: {msg}")
    def fail(msg): failures.append(msg); print(f"FAIL: {msg}")

    # spec-rules.md required metadata
    for key in ("schema_version", "owner", "deprecation_criterion"):
        v = schema.get(key)
        if not isinstance(v, str) or not v:
            fail(f"{key} missing or empty")
        else:
            ok(f"{key} present")

    # draft-07
    if schema.get("$schema") != "http://json-schema.org/draft-07/schema#":
        fail("$schema is not draft-07")
    else:
        ok("$schema is draft-07")

    # top-level type
    if schema.get("type") != "array":
        fail("top-level type must be 'array'")
    else:
        ok("top-level type is array")

    # item shape
    items = schema.get("items", {})
    if items.get("type") != "object" or items.get("additionalProperties") is not False:
        fail("items must be type=object with additionalProperties=false")
    else:
        ok("items are closed objects")

    required = items.get("required", [])
    for f in ("id", "kind", "inject", "slots"):
        if f not in required:
            fail(f"items.required is missing '{f}'")
        else:
            ok(f"items.required includes '{f}'")

    props = items.get("properties", {})
    if props.get("kind", {}).get("enum") != ["skill", "subagent"]:
        fail("kind enum must be exactly ['skill', 'subagent']")
    else:
        ok("kind enum is closed to skill|subagent")

    if props.get("inject", {}).get("minItems") != 1:
        fail("inject minItems must be 1 (non-empty)")
    else:
        ok("inject is non-empty array")

    if props.get("id", {}).get("pattern") != "^[a-z][a-z0-9-]*$":
        fail("id pattern must be ^[a-z][a-z0-9-]*$")
    else:
        ok("id pattern enforces lowercase+dashes")

    if failures:
        print(f"\n{len(failures)} failure(s)")
        return 1
    print("\nAll checks passed.")
    return 0

if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 .claude/features/contract/test/test-prompts-schema-shape.py`
Expected: `FAIL: schema file missing: .../prompts.schema.json`, exit 1.

- [ ] **Step 3: Create the schema**

Create `.claude/features/contract/schemas/prompts.schema.json`:

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "schema_version": "1.0.0",
  "owner": "rabbit-workflow team",
  "deprecation_criterion": "when prompt-contract assembly is native to Claude Code",
  "type": "array",
  "items": {
    "type": "object",
    "additionalProperties": false,
    "required": ["id", "kind", "inject", "slots"],
    "properties": {
      "id":     {"type": "string", "pattern": "^[a-z][a-z0-9-]*$"},
      "kind":   {"type": "string", "enum": ["skill", "subagent"]},
      "inject": {"type": "array", "items": {"type": "string"}, "minItems": 1},
      "slots":  {"type": "array", "items": {"type": "string", "pattern": "^[a-z][a-z0-9_]*$"}}
    }
  }
}
```

- [ ] **Step 4: Extend feature.json.schema.json**

Modify `.claude/features/contract/schemas/feature.json.schema.json`: under the top-level `properties` object (where `manifest`, `runtime`, `configuration` are declared as optional `$ref` properties), add:

```json
"prompts": {"$ref": "./prompts.schema.json"}
```

- [ ] **Step 5: Wire test into run.py**

Add `run_test("test-prompts-schema-shape.py")` to `.claude/features/contract/test/run.py` in alphabetical position.

- [ ] **Step 6: Run test to verify it passes**

Run: `python3 .claude/features/contract/test/test-prompts-schema-shape.py`
Expected: `All checks passed.`, exit 0.

- [ ] **Step 7: Run the full contract test suite**

Run: `python3 .claude/features/contract/test/run.py`
Expected: all existing tests pass, new test passes.

## Task A2: prompts-section validator + lint check

**Files:**
- Modify: `.claude/features/contract/lib/checks.py`
- Create: `.claude/features/contract/scripts/enforcement/check-prompts-section.py`
- Create: `.claude/features/contract/test/test-check-prompts-section.py`
- Modify: `.claude/features/contract/test/run.py`

- [ ] **Step 1: Write the failing test**

Create `.claude/features/contract/test/test-check-prompts-section.py`. The test creates a tmp tree with a faked feature.json carrying a prompts section, then asserts:

```python
#!/usr/bin/env python3
"""Behaviour test for contract.lib.checks.check_prompts_section."""

import json
import os
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO_ROOT / ".claude/features/contract"))

from lib.checks import check_prompts_section, CheckResult  # noqa: E402

def _setup(tmpdir, feature_name, prompts_section, templates):
    """Set up a tmp .claude/features/<X>/ tree with a feature.json prompts section
    and matching template files."""
    feat_dir = Path(tmpdir) / ".claude/features" / feature_name
    feat_dir.mkdir(parents=True)
    (feat_dir / "feature.json").write_text(json.dumps({
        "name": feature_name, "version": "1.0.0",
        "owner": "rabbit-workflow team",
        "deprecation_criterion": "n/a",
        "prompts": prompts_section,
    }))
    tdir = Path(tmpdir) / ".claude/features/contract/templates/prompts"
    tdir.mkdir(parents=True, exist_ok=True)
    for tid, body in templates.items():
        (tdir / f"{tid}.txt").write_text(body)
    pol = Path(tmpdir) / ".claude/features/policy"
    pol.mkdir(parents=True, exist_ok=True)
    (pol / "philosophy.md").write_text("philosophy")
    (pol / "spec-rules.md").write_text("spec-rules")
    return tmpdir

def main():
    failures = []
    def ok(msg): print(f"OK: {msg}")
    def fail(msg): failures.append(msg); print(f"FAIL: {msg}")

    # t1: valid entry passes
    with tempfile.TemporaryDirectory() as t:
        _setup(t, "fakefeat",
               [{"id": "fakefeat-skill", "kind": "skill",
                 "inject": [".claude/features/policy/philosophy.md"],
                 "slots": ["args"]}],
               {"fakefeat-skill": "{{args}}"})
        r = check_prompts_section(str(Path(t) / ".claude/features"))
        if not r.passed:
            fail(f"t1 valid entry should pass; messages={r.messages}")
        else:
            ok("t1: valid entry passes")

    # t2: missing philosophy.md inject is rejected
    with tempfile.TemporaryDirectory() as t:
        _setup(t, "fakefeat",
               [{"id": "fakefeat-skill", "kind": "skill",
                 "inject": [".claude/features/policy/spec-rules.md"],
                 "slots": ["args"]}],
               {"fakefeat-skill": "{{args}}"})
        r = check_prompts_section(str(Path(t) / ".claude/features"))
        if r.passed:
            fail("t2 missing philosophy.md should fail")
        else:
            ok("t2: missing philosophy.md rejected")

    # t3: duplicate id across features is rejected
    with tempfile.TemporaryDirectory() as t:
        _setup(t, "feat1",
               [{"id": "shared-id", "kind": "skill",
                 "inject": [".claude/features/policy/philosophy.md"],
                 "slots": ["args"]}],
               {"shared-id": "{{args}}"})
        _setup(t, "feat2",
               [{"id": "shared-id", "kind": "skill",
                 "inject": [".claude/features/policy/philosophy.md"],
                 "slots": ["args"]}],
               {})  # template already created above
        r = check_prompts_section(str(Path(t) / ".claude/features"))
        if r.passed:
            fail("t3 duplicate id should fail")
        else:
            ok("t3: duplicate id rejected")

    # t4: missing template file is rejected
    with tempfile.TemporaryDirectory() as t:
        _setup(t, "fakefeat",
               [{"id": "fakefeat-skill", "kind": "skill",
                 "inject": [".claude/features/policy/philosophy.md"],
                 "slots": ["args"]}],
               {})  # no template
        r = check_prompts_section(str(Path(t) / ".claude/features"))
        if r.passed:
            fail("t4 missing template should fail")
        else:
            ok("t4: missing template rejected")

    # t5: slot/placeholder mismatch is rejected
    with tempfile.TemporaryDirectory() as t:
        _setup(t, "fakefeat",
               [{"id": "fakefeat-skill", "kind": "skill",
                 "inject": [".claude/features/policy/philosophy.md"],
                 "slots": ["args"]}],
               {"fakefeat-skill": "{{args}} and {{extra}}"})  # extra placeholder
        r = check_prompts_section(str(Path(t) / ".claude/features"))
        if r.passed:
            fail("t5 orphan placeholder should fail")
        else:
            ok("t5: orphan placeholder rejected")

    if failures:
        print(f"\n{len(failures)} failure(s)")
        return 1
    print("\nAll checks passed.")
    return 0

if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 .claude/features/contract/test/test-check-prompts-section.py`
Expected: `ImportError: cannot import name 'check_prompts_section' from 'lib.checks'`.

- [ ] **Step 3: Implement check_prompts_section**

Modify `.claude/features/contract/lib/checks.py`. Add:

```python
import re

def check_prompts_section(features_root: str) -> CheckResult:
    """Validate prompts sections across all feature.json files.

    Walks features_root for feature.json files, extracts the optional
    `prompts` array from each, and enforces:
      - Schema validation (matches prompts.schema.json)
      - Globally unique `id` across all features
      - Every `inject` path exists on disk
      - Every entry includes `.claude/features/policy/philosophy.md` in inject
      - Template at .../templates/prompts/<id>.txt exists
      - Bidirectional slot/placeholder correspondence
      - Soft-warn: subagent id SHOULD start with owner feature name
    """
    features_root_p = Path(features_root)
    repo_root = features_root_p.parent.parent  # .claude/features → repo root
    templates_dir = features_root_p / "contract" / "templates" / "prompts"
    messages = []
    seen_ids = {}  # id → owner_feature
    passed = True

    for feat_json in sorted(features_root_p.glob("*/feature.json")):
        owner = feat_json.parent.name
        try:
            data = json.loads(feat_json.read_text())
        except Exception as e:
            messages.append(f"{owner}: feature.json unreadable: {e}")
            passed = False
            continue

        prompts = data.get("prompts")
        if prompts is None:
            continue
        if not isinstance(prompts, list):
            messages.append(f"{owner}: prompts must be a list")
            passed = False
            continue

        for entry in prompts:
            if not isinstance(entry, dict):
                messages.append(f"{owner}: prompts entry must be an object")
                passed = False
                continue

            eid = entry.get("id")
            ekind = entry.get("kind")
            einject = entry.get("inject", [])
            eslots = entry.get("slots", [])

            # required fields
            for f in ("id", "kind", "inject", "slots"):
                if f not in entry:
                    messages.append(f"{owner}:{eid}: missing required field '{f}'")
                    passed = False

            # id format
            if not isinstance(eid, str) or not re.match(r"^[a-z][a-z0-9-]*$", eid):
                messages.append(f"{owner}:{eid}: id must match ^[a-z][a-z0-9-]*$")
                passed = False
                continue  # rest depends on eid

            # kind enum
            if ekind not in ("skill", "subagent"):
                messages.append(f"{owner}:{eid}: kind must be 'skill' or 'subagent'")
                passed = False

            # global uniqueness
            if eid in seen_ids:
                messages.append(f"{owner}:{eid}: duplicate id (also declared by {seen_ids[eid]})")
                passed = False
            else:
                seen_ids[eid] = owner

            # inject non-empty + each path exists + philosophy required
            if not isinstance(einject, list) or not einject:
                messages.append(f"{owner}:{eid}: inject must be non-empty array")
                passed = False
            else:
                if ".claude/features/policy/philosophy.md" not in einject:
                    messages.append(f"{owner}:{eid}: inject must include philosophy.md")
                    passed = False
                for path in einject:
                    if not (repo_root / path).is_file():
                        messages.append(f"{owner}:{eid}: inject path missing on disk: {path}")
                        passed = False

            # template exists + slot/placeholder bidirectional match
            tpath = templates_dir / f"{eid}.txt"
            if not tpath.is_file():
                messages.append(f"{owner}:{eid}: template missing: {tpath}")
                passed = False
            else:
                body = tpath.read_text()
                placeholders = set(re.findall(r"\{\{([a-z][a-z0-9_]*)\}\}", body))
                declared = set(eslots) if isinstance(eslots, list) else set()
                orphan_in_template = placeholders - declared
                orphan_in_slots = declared - placeholders
                if orphan_in_template:
                    messages.append(
                        f"{owner}:{eid}: template has placeholders not in slots: "
                        f"{sorted(orphan_in_template)}"
                    )
                    passed = False
                if orphan_in_slots:
                    messages.append(
                        f"{owner}:{eid}: slots declared but absent from template: "
                        f"{sorted(orphan_in_slots)}"
                    )
                    passed = False

            # soft-warn: subagent id should start with owner feature name
            if ekind == "subagent" and isinstance(eid, str) and not eid.startswith(owner):
                messages.append(f"WARN: {owner}:{eid}: subagent id should start with owner feature name")

    return CheckResult(passed=passed, messages=messages)


def validate_prompts_section(feature_dir: str) -> CheckResult:
    """Per-feature validation wrapper used by validate_meta_contract dispatch.

    Validates just one feature's prompts section against schema rules
    (without the cross-feature uniqueness check, which only the
    cross-feature lint can perform).
    """
    feat_json = Path(feature_dir) / "feature.json"
    try:
        data = json.loads(feat_json.read_text())
    except Exception as e:
        return CheckResult(passed=False, messages=[f"feature.json unreadable: {e}"])
    prompts = data.get("prompts")
    if prompts is None:
        return CheckResult(passed=True, messages=[])
    if not isinstance(prompts, list):
        return CheckResult(passed=False, messages=["prompts must be a list"])
    msgs = []
    for entry in prompts:
        if not isinstance(entry, dict):
            msgs.append("entry must be an object"); continue
        for f in ("id", "kind", "inject", "slots"):
            if f not in entry:
                msgs.append(f"entry missing '{f}'")
        eid = entry.get("id", "")
        if not re.match(r"^[a-z][a-z0-9-]*$", eid):
            msgs.append(f"{eid}: id pattern violation")
        if entry.get("kind") not in ("skill", "subagent"):
            msgs.append(f"{eid}: kind must be skill|subagent")
        if not isinstance(entry.get("inject"), list) or not entry["inject"]:
            msgs.append(f"{eid}: inject must be non-empty list")
    return CheckResult(passed=not msgs, messages=msgs)
```

Also extend `validate_meta_contract` to call `validate_prompts_section`:

```python
def validate_meta_contract(feature_dir):
    # ... existing manifest/runtime/configuration validation ...
    prompts_result = validate_prompts_section(feature_dir)
    if not prompts_result.passed:
        all_messages.extend(f"prompts: {m}" for m in prompts_result.messages)
        all_passed = False
    # ... return aggregated result ...
```

(Adapt the snippet to whatever existing structure `validate_meta_contract` uses — append the new dispatch case in the same shape as the existing manifest/runtime/configuration cases.)

- [ ] **Step 4: Create the CLI shim**

Create `.claude/features/contract/scripts/enforcement/check-prompts-section.py`:

```python
#!/usr/bin/env python3
"""check-prompts-section.py — CLI shim around contract.lib.checks.check_prompts_section.

Walks .claude/features/*/feature.json and validates every prompts section.
Exit 0 on pass, 1 on failure (messages printed to stderr).

Version: 1.0.0
Owner: rabbit-workflow team (contract)
Deprecation criterion: when prompt-contract assembly is native to Claude Code.
"""

import os
import subprocess
import sys
from pathlib import Path

CONTRACT_LIB = Path(__file__).resolve().parents[2] / "lib"
sys.path.insert(0, str(CONTRACT_LIB.parent))
from lib.checks import check_prompts_section  # noqa: E402


def _repo_root():
    env = os.environ.get("RABBIT_ROOT")
    if env:
        return env
    try:
        return subprocess.run(
            ["git", "-C", str(Path(__file__).parent), "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, check=True
        ).stdout.strip()
    except subprocess.CalledProcessError:
        return None


def main():
    repo_root = _repo_root()
    if not repo_root:
        print("ERROR: cannot determine repo root", file=sys.stderr)
        return 2
    features_root = os.path.join(repo_root, ".claude", "features")
    result = check_prompts_section(features_root)
    for m in result.messages:
        print(m, file=sys.stderr if not result.passed else sys.stdout)
    return 0 if result.passed else 1


if __name__ == "__main__":
    sys.exit(main())
```

Make executable: `chmod +x .claude/features/contract/scripts/enforcement/check-prompts-section.py`.

- [ ] **Step 5: Wire test into run.py**

Add `run_test("test-check-prompts-section.py")`.

- [ ] **Step 6: Run test to verify it passes**

Run: `python3 .claude/features/contract/test/test-check-prompts-section.py`
Expected: `All checks passed.`, exit 0.

## Task A3: build-prompt.py + policy_block library extraction

**Files:**
- Create: `.claude/features/contract/lib/policy_block.py`
- Create: `.claude/features/contract/scripts/build-prompt.py`
- Create: `.claude/features/contract/test/test-policy-block-lib.py`
- Create: `.claude/features/contract/test/test-build-prompt.py`
- Modify: `.claude/features/contract/scripts/policy-block.py` — refactor to import from lib
- Modify: `.claude/features/contract/test/run.py`

- [ ] **Step 1: Write the policy_block lib test**

Create `.claude/features/contract/test/test-policy-block-lib.py`:

```python
#!/usr/bin/env python3
"""Test that contract.lib.policy_block emits the canonical policy framing
(sentinel line, header, per-file sections, footer) when given a list of policy files."""

import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO_ROOT / ".claude/features/contract"))
from lib.policy_block import render_policy_block  # noqa: E402


def main():
    failures = []
    def ok(msg): print(f"OK: {msg}")
    def fail(msg): failures.append(msg); print(f"FAIL: {msg}")

    with tempfile.TemporaryDirectory() as t:
        p1 = Path(t) / "a.md"; p1.write_text("alpha content")
        p2 = Path(t) / "b.md"; p2.write_text("beta content")
        block = render_policy_block([str(p1), str(p2)])

        if "RABBIT-POLICY-BLOCK-v1" not in block:
            fail("sentinel line missing")
        else:
            ok("sentinel line present")
        if "MANDATORY POLICY" not in block:
            fail("header banner missing")
        else:
            ok("header banner present")
        if "a.md" not in block or "alpha content" not in block:
            fail("first file not embedded")
        else:
            ok("first file embedded")
        if "b.md" not in block or "beta content" not in block:
            fail("second file not embedded")
        else:
            ok("second file embedded")
        if "END POLICY" not in block:
            fail("footer banner missing")
        else:
            ok("footer banner present")

    if failures:
        print(f"\n{len(failures)} failure(s)")
        return 1
    print("\nAll checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2: Run to verify it fails**

Expected: `ImportError: cannot import name 'render_policy_block' from 'lib.policy_block'`.

- [ ] **Step 3: Create policy_block lib**

Create `.claude/features/contract/lib/policy_block.py`:

```python
"""policy_block.py — canonical rabbit-workflow policy block renderer.

Shared by:
  - scripts/policy-block.py (CLI shim)
  - scripts/build-prompt.py (assembler)

Both prepend the same sentinel-line + header + per-file sections + footer
framing to any subagent prompt. Hoisting it here eliminates the duplication
that lived only in policy-block.py before CONTRACT-BACKLOG-1 landed.

Version: 1.0.0
Owner: rabbit-workflow team (contract)
Deprecation criterion: when policy injection is handled natively by Claude Code.
"""

from pathlib import Path

_SENTINEL = "RABBIT-POLICY-BLOCK-v1"

_HEADER = """\
═══════════════════════════════════════════════════════════════════════════════
MANDATORY POLICY — READ THIS BEFORE ANY ACTION
═══════════════════════════════════════════════════════════════════════════════

You are operating within the rabbit workflow. The following policy files are
NOT optional reading. They govern every choice you make in this invocation.
Failure to comply is a constitution violation.

If you have not yet internalized these principles, STOP and read them now
before doing anything else. Re-read them whenever you are uncertain about
how to proceed. They are the source of truth for every decision in this
session."""

_FOOTER = """\
═══════════════════════════════════════════════════════════════════════════════
END POLICY — internalize the above, then proceed. Every action must reflect it.
═══════════════════════════════════════════════════════════════════════════════"""


def render_policy_block(paths: list[str]) -> str:
    """Render the canonical policy block embedding each path in order.

    Args:
        paths: list of file paths to embed. Each must be readable.

    Returns:
        The complete policy block as a single string (no trailing newline).

    Raises:
        FileNotFoundError: if any path is missing.
    """
    parts = [_SENTINEL, _HEADER]
    for p in paths:
        pp = Path(p)
        if not pp.is_file():
            raise FileNotFoundError(f"policy file not readable: {p}")
        sep = "─" * 18
        parts.append(f"{sep} {pp.name} {sep}")
        parts.append(pp.read_text())
    parts.append(_FOOTER)
    return "\n".join(parts)
```

- [ ] **Step 4: Refactor existing policy-block.py to use lib**

Modify `.claude/features/contract/scripts/policy-block.py` to import and call `render_policy_block` instead of inlining the framing. Specifically replace the `emit_section` helper and the inline header/footer literals with:

```python
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from lib.policy_block import render_policy_block

# Then in main():
all_paths = [phil, spec_rules, coding_rules] + includes
print(render_policy_block(all_paths))
```

Keep all existing CLI behavior (`--include`, exit codes, etc.) and the existing tests in `test-policy-block.py` must still pass — verify after the refactor.

- [ ] **Step 5: Write the build-prompt test**

Create `.claude/features/contract/test/test-build-prompt.py`. Tests:

```python
#!/usr/bin/env python3
"""End-to-end test for build-prompt.py — sets up a tmp tree with a faked
feature.json + template, invokes the script, asserts a prompt file is
written and contains the expected sections."""

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]
SCRIPT = REPO_ROOT / ".claude/features/contract/scripts/build-prompt.py"


def main():
    failures = []
    def ok(msg): print(f"OK: {msg}")
    def fail(msg): failures.append(msg); print(f"FAIL: {msg}")

    # The script walks real .claude/features for entries — to test in
    # isolation, we use RABBIT_ROOT pointing at a tmp dir we control.
    with tempfile.TemporaryDirectory() as t:
        feats = Path(t) / ".claude/features"
        # Set up policy
        pol = feats / "policy"
        pol.mkdir(parents=True)
        (pol / "philosophy.md").write_text("PHILOSOPHY CONTENT")
        # Set up contract templates dir
        cdir = feats / "contract"
        (cdir / "templates" / "prompts").mkdir(parents=True)
        (cdir / "templates" / "prompts" / "test-callable.txt").write_text(
            "TASK: {{task_description}} (feature={{feature_name}})"
        )
        # Set up a faked feature.json declaring the entry
        ffeat = feats / "fakefeat"
        ffeat.mkdir(parents=True)
        (ffeat / "feature.json").write_text(json.dumps({
            "name": "fakefeat", "version": "1.0.0",
            "owner": "test", "deprecation_criterion": "n/a",
            "prompts": [
                {"id": "test-callable", "kind": "subagent",
                 "inject": [".claude/features/policy/philosophy.md"],
                 "slots": ["task_description", "feature_name"]}
            ]
        }))
        # Prompts output dir
        (Path(t) / ".rabbit/prompts").mkdir(parents=True)

        env = {**os.environ, "RABBIT_ROOT": t}

        # t1: missing slot fails
        r = subprocess.run(
            [sys.executable, str(SCRIPT), "--callable-id", "test-callable",
             "--slot", "task_description=Foo"],  # missing feature_name
            capture_output=True, text=True, env=env
        )
        if r.returncode != 1:
            fail(f"t1 missing slot should exit 1; got {r.returncode}")
        else:
            ok("t1: missing slot exits 1")

        # t2: unknown callable_id exits 2
        r = subprocess.run(
            [sys.executable, str(SCRIPT), "--callable-id", "nonexistent"],
            capture_output=True, text=True, env=env
        )
        if r.returncode != 2:
            fail(f"t2 unknown id should exit 2; got {r.returncode}")
        else:
            ok("t2: unknown id exits 2")

        # t3: success path
        r = subprocess.run(
            [sys.executable, str(SCRIPT), "--callable-id", "test-callable",
             "--slot", "task_description=Foo",
             "--slot", "feature_name=fakefeat"],
            capture_output=True, text=True, env=env
        )
        if r.returncode != 0:
            fail(f"t3 success should exit 0; got {r.returncode}, stderr={r.stderr}")
        else:
            ok("t3: success exits 0")
            path = r.stdout.strip()
            if not Path(path).is_file():
                fail(f"t3: prompt file not at {path}")
            else:
                ok(f"t3: prompt file at {path}")
                body = Path(path).read_text()
                if "PHILOSOPHY CONTENT" not in body:
                    fail("t3: policy not embedded")
                else:
                    ok("t3: policy embedded")
                if "TASK: Foo (feature=fakefeat)" not in body:
                    fail("t3: slots not substituted")
                else:
                    ok("t3: slots substituted")
                if "RABBIT-POLICY-BLOCK-v1" not in body:
                    fail("t3: sentinel missing")
                else:
                    ok("t3: sentinel present")

    if failures:
        print(f"\n{len(failures)} failure(s)")
        return 1
    print("\nAll checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 6: Run to verify build-prompt test fails**

Expected: script missing or `FileNotFoundError`.

- [ ] **Step 7: Create build-prompt.py**

Create `.claude/features/contract/scripts/build-prompt.py`:

```python
#!/usr/bin/env python3
"""build-prompt.py — assemble a subagent/skill prompt from a registered
prompts entry in any feature.json plus run-time slot values.

Walks .claude/features/*/feature.json for the entry whose `id` matches
--callable-id, reads its `inject` files via lib/policy_block, reads the
template at .claude/features/contract/templates/prompts/<id>.txt,
substitutes {{slot_name}} placeholders with --slot name=value pairs,
writes the assembled prompt to .rabbit/prompts/<id>-<pid>-<ts>.txt, and
prints the file path to stdout.

Usage:
  build-prompt.py --callable-id <id> [--slot <name>=<value> ...]

Exit:
  0  success — prompt file written, path on stdout
  1  read error (registry / template / policy), missing slot, orphan placeholder
  2  no entry matches --callable-id, or invocation error

Version: 1.0.0
Owner: rabbit-workflow team (contract)
Deprecation criterion: when prompt-contract assembly is native to Claude Code.
"""

import argparse
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR.parent))
from lib.policy_block import render_policy_block  # noqa: E402


def _repo_root():
    env = os.environ.get("RABBIT_ROOT")
    if env:
        return env
    try:
        return subprocess.run(
            ["git", "-C", str(SCRIPT_DIR), "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, check=True
        ).stdout.strip()
    except subprocess.CalledProcessError:
        return None


def _find_entry(features_root, callable_id):
    for feat_json in sorted(Path(features_root).glob("*/feature.json")):
        try:
            data = json.loads(feat_json.read_text())
        except Exception:
            continue
        for entry in data.get("prompts", []) or []:
            if entry.get("id") == callable_id:
                return entry, feat_json.parent.name
    return None, None


def main():
    parser = argparse.ArgumentParser(prog="build-prompt.py")
    parser.add_argument("--callable-id", required=True)
    parser.add_argument("--slot", action="append", default=[],
                        help="name=value (repeatable)")
    try:
        args = parser.parse_args()
    except SystemExit as e:
        return e.code if e.code else 2

    repo_root = _repo_root()
    if not repo_root:
        print("ERROR: cannot determine repo root", file=sys.stderr); return 2
    repo_root = Path(repo_root)

    features_root = repo_root / ".claude" / "features"
    entry, owner = _find_entry(str(features_root), args.callable_id)
    if entry is None:
        print(f"ERROR: no prompts entry with id '{args.callable_id}'", file=sys.stderr)
        return 2

    # Parse slots
    slots = {}
    for s in args.slot:
        if "=" not in s:
            print(f"ERROR: malformed --slot '{s}' (expected name=value)", file=sys.stderr)
            return 2
        k, _, v = s.partition("=")
        slots[k] = v

    # Validate slot completeness
    missing = [s for s in entry.get("slots", []) if s not in slots]
    if missing:
        print(f"ERROR: missing required slots: {missing}", file=sys.stderr)
        return 1

    # Render policy block
    try:
        inject_paths = [str(repo_root / p) for p in entry.get("inject", [])]
        policy = render_policy_block(inject_paths)
    except FileNotFoundError as e:
        print(f"ERROR: {e}", file=sys.stderr); return 1

    # Read template
    tpath = repo_root / ".claude/features/contract/templates/prompts" / f"{args.callable_id}.txt"
    if not tpath.is_file():
        print(f"ERROR: template missing: {tpath}", file=sys.stderr); return 1
    body = tpath.read_text()

    # Substitute slots (single-pass replace; order does not matter because
    # placeholder values are not themselves placeholders)
    for k, v in slots.items():
        body = body.replace("{{" + k + "}}", v)

    # Check for orphan placeholders
    orphans = re.findall(r"\{\{[a-z][a-z0-9_]*\}\}", body)
    if orphans:
        print(f"ERROR: orphan placeholders after substitution: {sorted(set(orphans))}",
              file=sys.stderr)
        return 1

    # Assemble + write
    assembled = policy + "\n\n" + body
    outdir = repo_root / ".rabbit" / "prompts"
    outdir.mkdir(parents=True, exist_ok=True)
    ts = time.strftime("%Y%m%d-%H%M%S") + f"-{int(time.time() * 1000) % 1000:03d}"
    outfile = outdir / f"{args.callable_id}-{os.getpid()}-{ts}.txt"
    outfile.write_text(assembled)
    print(str(outfile))
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

Make executable: `chmod +x .claude/features/contract/scripts/build-prompt.py`.

- [ ] **Step 8: Wire tests into run.py**

Add `run_test("test-policy-block-lib.py")` and `run_test("test-build-prompt.py")` in alphabetical position.

- [ ] **Step 9: Run new tests**

Run: `python3 .claude/features/contract/test/test-policy-block-lib.py`
Run: `python3 .claude/features/contract/test/test-build-prompt.py`
Both expected: `All checks passed.`, exit 0.

- [ ] **Step 10: Run existing test-policy-block.py to confirm refactor didn't break it**

Run: `python3 .claude/features/contract/test/test-policy-block.py`
Expected: passes unchanged.

## Task A4: PreToolUse hook source

**Files:**
- Create: `.claude/features/contract/hooks/prompt-injector.py`
- Create: `.claude/features/contract/test/test-prompt-injector-hook.py`
- Modify: `.claude/features/contract/test/run.py`

- [ ] **Step 1: Write the failing test**

Create `.claude/features/contract/test/test-prompt-injector-hook.py`. The test pipes JSON to the hook stdin and asserts the stdout shape:

```python
#!/usr/bin/env python3
"""Test the prompt-injector PreToolUse hook end-to-end:
  - Skill call with registered id → emits additionalContext
  - Skill call with unregistered id → emits {} silently
  - Agent call → emits {} (hook is skill-only)
  - Failure case → logs to .injection-failures.log, emits {} (never blocks)
"""

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]
HOOK = REPO_ROOT / ".claude/features/contract/hooks/prompt-injector.py"


def _setup_tree(tmpdir):
    """Set up a tmp .claude/features tree with a registered skill."""
    feats = Path(tmpdir) / ".claude/features"
    pol = feats / "policy"
    pol.mkdir(parents=True)
    (pol / "philosophy.md").write_text("philosophy")
    cdir = feats / "contract"
    (cdir / "templates" / "prompts").mkdir(parents=True)
    (cdir / "templates" / "prompts" / "test-skill.txt").write_text("ARGS={{args}}")
    # Also copy the contract scripts dir so build-prompt.py works in tmp
    # (the hook subprocess-invokes build-prompt.py from the real repo).
    # For simplicity, we let the hook use the real repo's build-prompt
    # but point it at the tmp features tree via RABBIT_ROOT.
    ffeat = feats / "fakefeat"
    ffeat.mkdir(parents=True)
    (ffeat / "feature.json").write_text(json.dumps({
        "name": "fakefeat", "version": "1.0.0",
        "owner": "test", "deprecation_criterion": "n/a",
        "prompts": [
            {"id": "test-skill", "kind": "skill",
             "inject": [".claude/features/policy/philosophy.md"],
             "slots": ["args"]}
        ]
    }))
    (Path(tmpdir) / ".rabbit/prompts").mkdir(parents=True)


def _invoke(stdin_json, env):
    return subprocess.run(
        [sys.executable, str(HOOK)],
        input=json.dumps(stdin_json), capture_output=True, text=True, env=env
    )


def main():
    failures = []
    def ok(msg): print(f"OK: {msg}")
    def fail(msg): failures.append(msg); print(f"FAIL: {msg}")

    # Note: hook must locate the assembler script. Because the assembler
    # lives at a known path relative to the hook (../scripts/build-prompt.py
    # via the contract feature layout), we need to also stage that or use
    # the real repo's contract dir. We mock by creating a symlink to the
    # real contract dir under tmpdir's features tree.
    with tempfile.TemporaryDirectory() as t:
        _setup_tree(t)
        # Symlink contract scripts + lib so build-prompt.py is reachable
        real_contract = REPO_ROOT / ".claude/features/contract"
        tmp_contract = Path(t) / ".claude/features/contract"
        for sub in ("scripts", "lib"):
            tgt = tmp_contract / sub
            if tgt.exists():
                continue
            tgt.symlink_to(real_contract / sub)

        env = {**os.environ, "RABBIT_ROOT": t}

        # t1: Skill call with registered id
        r = _invoke({"tool_name": "Skill",
                     "tool_input": {"skill": "test-skill", "args": "hello"}}, env)
        if r.returncode != 0:
            fail(f"t1: hook exit {r.returncode}, stderr={r.stderr}")
        else:
            ok("t1: hook exits 0")
            try:
                out = json.loads(r.stdout) if r.stdout else {}
                ctx = out.get("hookSpecificOutput", {}).get("additionalContext", "")
                if "philosophy" not in ctx or "ARGS=hello" not in ctx:
                    fail(f"t1: additionalContext missing expected content; got {ctx!r}")
                else:
                    ok("t1: additionalContext contains policy + filled template")
            except json.JSONDecodeError as e:
                fail(f"t1: stdout not JSON: {e}")

        # t2: Skill call with UNregistered id → silent {}
        r = _invoke({"tool_name": "Skill",
                     "tool_input": {"skill": "unknown-skill", "args": ""}}, env)
        if r.returncode != 0:
            fail(f"t2: exit {r.returncode}")
        else:
            out = json.loads(r.stdout) if r.stdout else {}
            if out and out.get("hookSpecificOutput", {}).get("additionalContext"):
                fail(f"t2: unexpected additionalContext for unknown skill: {out}")
            else:
                ok("t2: unknown skill → silent no-op")

        # t3: Agent call → silent {}
        r = _invoke({"tool_name": "Agent",
                     "tool_input": {"subagent_type": "x", "prompt": "y"}}, env)
        if r.returncode != 0:
            fail(f"t3: exit {r.returncode}")
        else:
            out = json.loads(r.stdout) if r.stdout else {}
            if out and out.get("hookSpecificOutput", {}).get("additionalContext"):
                fail(f"t3: hook fired on Agent call: {out}")
            else:
                ok("t3: Agent call → silent no-op")

    if failures:
        print(f"\n{len(failures)} failure(s)")
        return 1
    print("\nAll checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2: Run test to verify it fails**

Expected: hook missing.

- [ ] **Step 3: Create the hook**

Create `.claude/features/contract/hooks/prompt-injector.py`:

```python
#!/usr/bin/env python3
"""prompt-injector.py — Claude Code PreToolUse hook that injects assembled
policy + template content as additionalContext on registered Skill calls.

Reads PreToolUse JSON from stdin. If tool is Skill and the skill name matches
a registered `prompts` entry (kind: skill) in any feature.json, invokes
build-prompt.py and emits the result via hookSpecificOutput.additionalContext.

On Agent or other tools: silent no-op (subagent dispatchers assemble their
own prompts via build-prompt.py directly).

On failure (assembler error, missing template, etc.): appends a JSON line to
.rabbit/prompts/.injection-failures.log and returns silent {} — NEVER blocks
the user's skill call. Failures surface via the Stop-event runtime API
check_prompt_injection_failures.

Version: 1.0.0
Owner: rabbit-workflow team (contract)
Deprecation criterion: when prompt-contract assembly is native to Claude Code.
"""

import json
import os
import subprocess
import sys
import time
from pathlib import Path


def _repo_root():
    env = os.environ.get("RABBIT_ROOT")
    if env:
        return env
    try:
        return subprocess.run(
            ["git", "-C", str(Path(__file__).parent), "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, check=True
        ).stdout.strip()
    except subprocess.CalledProcessError:
        return None


def _find_skill_entry(features_root, skill_name):
    for feat_json in sorted(Path(features_root).glob("*/feature.json")):
        try:
            data = json.loads(feat_json.read_text())
        except Exception:
            continue
        for entry in data.get("prompts", []) or []:
            if entry.get("kind") == "skill" and entry.get("id") == skill_name:
                return entry
    return None


def _log_failure(repo_root, skill, callable_id, error):
    log_dir = Path(repo_root) / ".rabbit/prompts"
    log_dir.mkdir(parents=True, exist_ok=True)
    log = log_dir / ".injection-failures.log"
    with log.open("a") as f:
        f.write(json.dumps({
            "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "skill": skill, "callable_id": callable_id, "error": error
        }) + "\n")


def main():
    # Best-effort: never raise, never block.
    try:
        payload = json.load(sys.stdin)
    except Exception:
        print("{}"); return 0

    tool_name = payload.get("tool_name")
    if tool_name != "Skill":
        print("{}"); return 0

    tool_input = payload.get("tool_input", {}) or {}
    skill = tool_input.get("skill")
    if not skill:
        print("{}"); return 0

    repo_root = _repo_root()
    if not repo_root:
        print("{}"); return 0

    features_root = Path(repo_root) / ".claude" / "features"
    entry = _find_skill_entry(str(features_root), skill)
    if entry is None:
        print("{}"); return 0

    # Slot resolution: skill tool args carries one free-text 'args' field.
    args_value = tool_input.get("args", "") or ""
    declared = set(entry.get("slots", []))

    # If entry declares slots other than 'args', it's mis-declared for a skill.
    extra = declared - {"args"}
    if extra:
        _log_failure(repo_root, skill, entry["id"],
                     f"skill entry declares non-args slots: {sorted(extra)}")
        print("{}"); return 0

    # Invoke build-prompt.py
    build_prompt = Path(repo_root) / ".claude/features/contract/scripts/build-prompt.py"
    slot_args = []
    if "args" in declared:
        slot_args = ["--slot", f"args={args_value}"]
    try:
        r = subprocess.run(
            [sys.executable, str(build_prompt), "--callable-id", entry["id"], *slot_args],
            capture_output=True, text=True, timeout=10, env=os.environ.copy()
        )
        if r.returncode != 0:
            _log_failure(repo_root, skill, entry["id"], r.stderr.strip()[:500])
            print("{}"); return 0
        prompt_file = Path(r.stdout.strip())
        if not prompt_file.is_file():
            _log_failure(repo_root, skill, entry["id"], "prompt file not at returned path")
            print("{}"); return 0
        body = prompt_file.read_text()
    except Exception as e:
        _log_failure(repo_root, skill, entry["id"], str(e))
        print("{}"); return 0

    output = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "additionalContext": body
        }
    }
    print(json.dumps(output))
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

Make executable: `chmod +x .claude/features/contract/hooks/prompt-injector.py`.

- [ ] **Step 4: Wire test into run.py**

Add `run_test("test-prompt-injector-hook.py")`.

- [ ] **Step 5: Run test to verify it passes**

Run: `python3 .claude/features/contract/test/test-prompt-injector-hook.py`
Expected: `All checks passed.`, exit 0.

## Task A5: runtime APIs (cleanup + failure alerts) + runtime schema extension

**Files:**
- Modify: `.claude/features/contract/lib/runtime.py`
- Modify: `.claude/features/contract/schemas/runtime.schema.json`
- Create: `.claude/features/contract/test/test-runtime-cleanup-old-prompts.py`
- Create: `.claude/features/contract/test/test-runtime-check-prompt-injection-failures.py`
- Modify: `.claude/features/contract/test/test-runtime-schema-shape.py`
- Modify: `.claude/features/contract/test/run.py`

- [ ] **Step 1: Write the failing cleanup test**

Create `.claude/features/contract/test/test-runtime-cleanup-old-prompts.py`:

```python
#!/usr/bin/env python3
"""Test contract.lib.runtime.cleanup_old_prompts."""

import sys
import tempfile
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO_ROOT / ".claude/features/contract"))
from lib.runtime import cleanup_old_prompts  # noqa: E402


def main():
    failures = []
    def ok(msg): print(f"OK: {msg}")
    def fail(msg): failures.append(msg); print(f"FAIL: {msg}")

    with tempfile.TemporaryDirectory() as t:
        pdir = Path(t) / ".rabbit/prompts"
        pdir.mkdir(parents=True)
        # Old file (timestamp 2020)
        old = pdir / "x-1234-20200101-000000-000.txt"
        old.write_text("old")
        # Fresh file (today)
        today = time.strftime("%Y%m%d-%H%M%S")
        fresh = pdir / f"x-5678-{today}-000.txt"
        fresh.write_text("fresh")

        r = cleanup_old_prompts(max_age_days=7, repo_root=t)
        if not r.passed:
            fail(f"cleanup failed: {r.messages}")
        else:
            ok("cleanup passed")
        if old.exists():
            fail("old file not deleted")
        else:
            ok("old file deleted")
        if not fresh.exists():
            fail("fresh file unexpectedly deleted")
        else:
            ok("fresh file preserved")

        # t2: missing dir is ok
        with tempfile.TemporaryDirectory() as t2:
            r = cleanup_old_prompts(max_age_days=7, repo_root=t2)
            if not r.passed:
                fail("missing dir should pass (no-op)")
            else:
                ok("missing dir = no-op pass")

    if failures:
        print(f"\n{len(failures)} failure(s)")
        return 1
    print("\nAll checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2: Write the failing failure-alert test**

Create `.claude/features/contract/test/test-runtime-check-prompt-injection-failures.py`:

```python
#!/usr/bin/env python3
"""Test contract.lib.runtime.check_prompt_injection_failures."""

import json
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO_ROOT / ".claude/features/contract"))
from lib.runtime import check_prompt_injection_failures  # noqa: E402


def main():
    failures = []
    def ok(msg): print(f"OK: {msg}")
    def fail(msg): failures.append(msg); print(f"FAIL: {msg}")

    # t1: empty log → ok_result
    with tempfile.TemporaryDirectory() as t:
        log_path = ".rabbit/prompts/.injection-failures.log"
        results = check_prompt_injection_failures(log_path=log_path, repo_root=t)
        # The function returns a list of results — sift for non-ok
        if not isinstance(results, list):
            results = [results]
        non_ok = [r for r in results if r.kind != "ok"]
        if non_ok:
            fail(f"t1 empty log should be ok; got {non_ok}")
        else:
            ok("t1: empty log = ok")

    # t2: log with entries → print_result
    with tempfile.TemporaryDirectory() as t:
        log = Path(t) / ".rabbit/prompts/.injection-failures.log"
        log.parent.mkdir(parents=True)
        log.write_text(
            json.dumps({"ts": "2026-05-26T00:00:00Z", "skill": "test-skill",
                        "callable_id": "test-skill", "error": "boom"}) + "\n"
        )
        results = check_prompt_injection_failures(log_path=".rabbit/prompts/.injection-failures.log",
                                                  repo_root=t)
        if not isinstance(results, list):
            results = [results]
        prints = [r for r in results if r.kind == "print"]
        if not prints:
            fail("t2 log with entries should produce a print result")
        else:
            ok("t2: log produces print result")
        # Log should be emptied after surfacing
        if log.read_text():
            fail("t2: log not emptied after surfacing")
        else:
            ok("t2: log emptied")

    if failures:
        print(f"\n{len(failures)} failure(s)")
        return 1
    print("\nAll checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 3: Implement the runtime APIs**

Modify `.claude/features/contract/lib/runtime.py`. Add:

```python
import json as _json
import time as _time
from pathlib import Path as _Path

# Reuse existing result-factory helpers (print_result, ok_result, etc.).

def cleanup_old_prompts(max_age_days: int, *, repo_root: str):
    """Delete files in .rabbit/prompts/ older than max_age_days.

    Uses the <YYYYMMDD-HHMMSS-ms> timestamp prefix in the filename rather
    than stat() for deterministic behavior. Returns ok_result() on success
    or when the dir doesn't exist. Idempotent.
    """
    pdir = _Path(repo_root) / ".rabbit" / "prompts"
    if not pdir.is_dir():
        return ok_result()
    cutoff = _time.time() - max_age_days * 86400
    for f in pdir.iterdir():
        if not f.is_file() or not f.suffix == ".txt":
            continue
        # filename: <id>-<pid>-<YYYYMMDD>-<HHMMSS>-<ms>.txt
        parts = f.stem.split("-")
        if len(parts) < 4:
            continue
        try:
            date_str = f"{parts[-3]} {parts[-2]}"
            ts = _time.mktime(_time.strptime(date_str, "%Y%m%d %H%M%S"))
        except (ValueError, IndexError):
            continue
        if ts < cutoff:
            try:
                f.unlink()
            except OSError:
                pass
    return ok_result()


def check_prompt_injection_failures(log_path: str, *, repo_root: str):
    """If the failure log has new entries, emit a print result summarizing
    them and empty the log. Otherwise return ok_result.
    """
    log = _Path(repo_root) / log_path
    if not log.is_file() or log.stat().st_size == 0:
        return ok_result()
    lines = [l for l in log.read_text().strip().split("\n") if l.strip()]
    if not lines:
        return ok_result()
    skills = []
    for line in lines:
        try:
            skills.append(_json.loads(line).get("skill", "?"))
        except _json.JSONDecodeError:
            continue
    # Empty the log after surfacing (consume pattern, matches check_marker_consume_alert)
    log.write_text("")
    text = f"Prompt-injection failed for {len(skills)} skill call(s): {', '.join(sorted(set(skills)))}"
    return print_result(text, "📢", "red")
```

(`print_result` and `ok_result` are already defined in `lib/runtime.py` per Inv 47; this code reuses them.)

- [ ] **Step 4: Add APIs to runtime.schema.json closed enum**

Modify `.claude/features/contract/schemas/runtime.schema.json`. In the `call_list` definition's enum (the one that names every runtime API), add `check_prompt_injection_failures` and `cleanup_old_prompts` to the existing list. Per Inv 41 of contract spec.

- [ ] **Step 5: Update the schema-shape test**

Modify `.claude/features/contract/test/test-runtime-schema-shape.py` — add the two new API names to whatever existing list/set the test asserts the runtime enum contains. (Match the existing pattern in that file.)

- [ ] **Step 6: Wire new tests into run.py**

Add `run_test("test-runtime-cleanup-old-prompts.py")` and `run_test("test-runtime-check-prompt-injection-failures.py")`.

- [ ] **Step 7: Run new + modified tests**

Run: `python3 .claude/features/contract/test/test-runtime-cleanup-old-prompts.py`
Run: `python3 .claude/features/contract/test/test-runtime-check-prompt-injection-failures.py`
Run: `python3 .claude/features/contract/test/test-runtime-schema-shape.py`
All expected: pass.

## Task A6: contract feature.json + spec amendments

**Files:**
- Modify: `.claude/features/contract/feature.json` — add `manifest` (one entry) + `runtime` (two entries)
- Modify: `.claude/features/contract/docs/spec/spec.md` — amend "Meta-contract sections" paragraph, add Inv 51–55

- [ ] **Step 1: Update contract's feature.json**

Replace the contract feature.json's `manifest` (currently absent/empty) and `runtime` (currently `{}`) sections:

```json
"manifest": [
  {"api": "publish_hook",
   "args": {"event": "PreToolUse", "source": "hooks/prompt-injector.py"}}
],
"runtime": {
  "Stop": [
    {"api": "check_prompt_injection_failures",
     "args": {"log_path": ".rabbit/prompts/.injection-failures.log"}},
    {"api": "cleanup_old_prompts",
     "args": {"max_age_days": 7}}
  ]
}
```

- [ ] **Step 2: Amend the "Meta-contract sections" paragraph in contract spec.md**

Replace the existing paragraph (currently asserts contract has no manifest/runtime/configuration) with text along the lines of:

> Contract owns the publish/observe surface for the prompt-injection
> machinery only — one `publish_hook` entry in `manifest` (the
> PreToolUse `prompt-injector.py` source) and two Stop entries in
> `runtime` (`check_prompt_injection_failures` and `cleanup_old_prompts`).
> No broader Claude Code event integration; `configuration` remains
> empty.

- [ ] **Step 3: Add invariants Inv 51–55**

Append to the Invariants section of contract spec.md:

- **Inv 51** — `schemas/prompts.schema.json` exists, valid JSON, draft-07, carries spec-rules.md metadata, declares `type: array` with items requiring `{id, kind, inject, slots}` and the `kind` enum closed to `["skill", "subagent"]`. Enforced by `test-prompts-schema-shape.py`.
- **Inv 52** — `feature.json.schema.json` declares `prompts` as an OPTIONAL `$ref` to `prompts.schema.json`, matching the pattern used for `manifest` / `runtime` / `configuration`.
- **Inv 53** — `contract.lib.checks.check_prompts_section(features_root)` walks every feature.json, asserts globally unique `id`s, every inject path exists, every entry includes `philosophy.md`, every entry's template exists at the conventional path, and slot/placeholder bidirectional correspondence. CLI shim at `scripts/enforcement/check-prompts-section.py` returns 0/1. Wired into `test/run.py`. Enforced by `test-check-prompts-section.py`.
- **Inv 54** — `scripts/build-prompt.py` exists, executable, accepts `--callable-id <id>` plus repeatable `--slot name=value`, walks feature.json files to find the entry, reads its inject + the conventional template, substitutes placeholders, writes to `.rabbit/prompts/<id>-<pid>-<ts>.txt`, prints path. Exit 0/1/2 per design doc. Reuses `lib.policy_block.render_policy_block` for framing.
- **Inv 55** — `hooks/prompt-injector.py` exists, executable, PreToolUse hook. Fires on Skill calls only (Agent and others = silent `{}`); looks up the `prompts` entry; invokes `build-prompt.py`; emits result as `additionalContext`. Failure path: appends to `.rabbit/prompts/.injection-failures.log` and emits silent `{}` (never blocks). Contract's `manifest` publishes via `publish_hook` PreToolUse. Contract's `runtime.Stop` calls `check_prompt_injection_failures` (consumes log, surfaces alert) and `cleanup_old_prompts` (7-day default).

- [ ] **Step 4: Run full contract test suite**

Run: `python3 .claude/features/contract/test/run.py`
Expected: all tests pass including the new 7. The new invariants now have test coverage.

## Phase A → TDD-cycle completion

After Tasks A1–A6, dispatch `rabbit-feature-touch` on the `contract` feature with the impl-suggestion being Tasks A1–A6 content. The TDD subagent runs the 7-step cycle (LOCK → TEST-WRITE → TEST-RED → IMPLEMENT → CODE-REVIEW → TEST-GREEN → UNLOCK), commits along the way, and emits HANDOFF. Verify HANDOFF reports `test_result: pass`. Phase A is now shippable as a PR.

---

# Phase B — tdd-subagent migration

Goal: extract the existing inline TDD prompt body into the contract template, declare the `prompts` entry, and reduce `dispatch-tdd-subagent.py` to argument-validation + slot-fill + assembler invocation.

**Execution:** one `rabbit-feature-touch` cycle on `tdd-subagent`.

## Task B1: extract template + declare prompts entry + rewrite dispatcher

**Files:**
- Create: `.claude/features/contract/templates/prompts/tdd-subagent.txt`
- Modify: `.claude/features/tdd-subagent/feature.json` — add `prompts` section
- Modify: `.claude/features/tdd-subagent/scripts/dispatch-tdd-subagent.py` — replace inline f-string assembly
- Modify: `.claude/features/tdd-subagent/docs/spec/spec.md` — amend Inv 7–24 to reference template
- Create: `.claude/features/tdd-subagent/test/test-dispatch-uses-build-prompt.py`
- Modify: `.claude/features/tdd-subagent/test/run.py`

NOTE: This task creates a file under `.claude/features/contract/templates/prompts/` — that's a cross-feature edit. The `rabbit-feature-touch` cycle for tdd-subagent will hit a SCOPE BOUNDARY red flag at IMPLEMENT step when it tries to write the template. The correct routing per the contract design: the template file is **content-authored by tdd-subagent's owner** but **stored in contract**. Resolve by either (a) splitting into two TDD cycles — one on contract that adds the template file (under approved cross-feature exception), then one on tdd-subagent that wires the entry + rewrites dispatcher; or (b) running both edits inside Phase A's contract cycle and reducing this phase to just dispatcher + feature.json + spec changes. Approach (b) is simpler and recommended — append the template-file creation step to Phase A's Task A1 (or as Task A7).

For this plan, **assume approach (b)**: the template file is created during Phase A. Phase B's tasks therefore reduce to the dispatcher rewrite + feature.json edit + spec amendment + new regression test.

Re-stated Phase B file list (after approach-b adjustment):
- Modify: `.claude/features/tdd-subagent/feature.json`
- Modify: `.claude/features/tdd-subagent/scripts/dispatch-tdd-subagent.py`
- Modify: `.claude/features/tdd-subagent/docs/spec/spec.md`
- Create: `.claude/features/tdd-subagent/test/test-dispatch-uses-build-prompt.py`
- Modify: `.claude/features/tdd-subagent/test/run.py`

(Phase A's Task A1 grows to additionally write the template file from `dispatch-tdd-subagent.py` lines 339–596, with every `{python_format_var}` replaced by `{{python_format_var}}`. That work is mechanical copy/replace.)

- [ ] **Step 1: Write the failing regression test**

Create `.claude/features/tdd-subagent/test/test-dispatch-uses-build-prompt.py`:

```python
#!/usr/bin/env python3
"""Regression: dispatch-tdd-subagent.py must invoke build-prompt.py rather
than assembling the prompt inline via f-string.

Greps the script for:
  - presence of a subprocess call to build-prompt.py
  - absence of the canonical f-string assembly markers
    (e.g. literal '════════════════════════════════════════════════════════════════════════'
    that used to live inline as the section banners)
"""

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]
SCRIPT = REPO_ROOT / ".claude/features/tdd-subagent/scripts/dispatch-tdd-subagent.py"


def main():
    failures = []
    def ok(msg): print(f"OK: {msg}")
    def fail(msg): failures.append(msg); print(f"FAIL: {msg}")

    src = SCRIPT.read_text()
    if "build-prompt.py" not in src:
        fail("script does not reference build-prompt.py")
    else:
        ok("references build-prompt.py")

    if re.search(r'^\s*prompt\s*=\s*f"""', src, re.MULTILINE):
        fail("inline f-string assembly still present")
    else:
        ok("inline f-string assembly removed")

    # Sanity: TDD-cycle section banners (long ═ separators) belong in the
    # template now, not the script.
    banner_count = src.count("════════════════════════════════════════════════════════════════════════")
    if banner_count > 0:
        fail(f"section banners ({banner_count}) still inline — should be template-only")
    else:
        ok("section banners moved to template")

    if failures:
        print(f"\n{len(failures)} failure(s)")
        return 1
    print("\nAll checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2: Run test to verify it fails**

Expected: failures — script still has inline f-string assembly and banners.

- [ ] **Step 3: Add prompts entry to feature.json**

Modify `.claude/features/tdd-subagent/feature.json`. Add `prompts` section:

```json
"prompts": [
  {
    "id": "tdd-subagent",
    "kind": "subagent",
    "inject": [
      ".claude/features/policy/philosophy.md",
      ".claude/features/policy/spec-rules.md",
      ".claude/features/policy/coding-rules.md"
    ],
    "slots": [
      "feature_name", "spec_content", "impl_suggestion_block",
      "bypass_preamble_note", "feature_dir", "tdd_step_py",
      "repo_root", "max_iterations", "code_review_loop_note",
      "linked_item_value", "item_type_value",
      "close_calls_block", "handoff_closed_items_block",
      "handoff_closed_items_json"
    ]
  }
]
```

- [ ] **Step 4: Rewrite dispatch-tdd-subagent.py**

Replace lines 339–596 of `dispatch-tdd-subagent.py` (the inline `prompt = f"""..."""` block + stdout write) with:

```python
    # Build slot dict from values computed above.
    slots = {
        "feature_name": feature_name,
        "spec_content": spec_content,
        "impl_suggestion_block": impl_suggestion_block,
        "bypass_preamble_note": bypass_preamble_note,
        "feature_dir": feature_dir,
        "tdd_step_py": tdd_step_py,
        "repo_root": repo_root,
        "max_iterations": str(args.max_iterations),
        "code_review_loop_note": code_review_loop_note,
        "linked_item_value": linked_item_value,
        "item_type_value": item_type_value,
        "close_calls_block": close_calls_block,
        "handoff_closed_items_block": handoff_closed_items_block,
        "handoff_closed_items_json": handoff_closed_items_json,
    }
    build_prompt_py = os.path.join(
        repo_root, ".claude", "features", "contract", "scripts", "build-prompt.py"
    )
    slot_flags = []
    for k, v in slots.items():
        slot_flags.extend(["--slot", f"{k}={v}"])
    res = subprocess.run(
        [sys.executable, build_prompt_py, "--callable-id", "tdd-subagent", *slot_flags],
        capture_output=True, text=True, check=False,
    )
    if res.returncode != 0:
        sys.stderr.write(res.stderr)
        return res.returncode
    prompt_file = res.stdout.strip()
    with open(prompt_file) as f:
        sys.stdout.write(f.read())
    sys.stderr.write(f"dispatch-tdd-subagent: prompt ready for feature '{feature_name}'\n")
    return 0
```

Remove the now-unused `_policy_block` helper and its call. (The assembler emits the policy block from the entry's `inject` list — direct `policy-block.py` invocation is dead.) Remove the corresponding `policy_block = _policy_block(repo_root)` line.

- [ ] **Step 5: Amend tdd-subagent spec invariants**

Modify `.claude/features/tdd-subagent/docs/spec/spec.md`. For each of Inv 7–24 (which describe content of the assembled prompt), update the wording to reference the template file rather than the inline f-string. Example for Inv 8:

> **Inv 8 — 7-step section banners.** The template at
> `.claude/features/contract/templates/prompts/tdd-subagent.txt` contains
> a labelled section per step using the names `LOCK`, `TEST-WRITE`,
> `TEST-RED`, `IMPLEMENT`, `CODE-REVIEW`, `TEST-GREEN`, `UNLOCK`, in that
> order, numbered STEP 1 through STEP 7. Spec context-loading and human
> approval are owned by the dispatcher (`rabbit-feature-touch`) and
> absent from the template.

(Each of Inv 7, 9–18, 19–22 gets analogous wording — the substantive constraint is unchanged; the artifact under constraint changes from the script's f-string to the template file.)

Add **Inv 45** — `dispatch-tdd-subagent.py` MUST NOT assemble the prompt inline. It MUST build a slot dict and invoke `.claude/features/contract/scripts/build-prompt.py --callable-id tdd-subagent --slot <name>=<value>` for every declared slot in `feature.json`'s `prompts.tdd-subagent` entry, write the resulting file's contents to stdout, and return the assembler's exit code on failure. Enforced by `test-dispatch-uses-build-prompt.py`.

- [ ] **Step 6: Wire test into run.py**

Add `run_test("test-dispatch-uses-build-prompt.py")` to `.claude/features/tdd-subagent/test/run.py`.

- [ ] **Step 7: Run new + existing tests**

Run: `python3 .claude/features/tdd-subagent/test/run.py`
Expected: all tests pass. Specifically, the existing `test-bypass-marker-note.py` test (Inv 23/24) still passes because the bypass note continues to flow through `rabbit_print` from the script, slotted into the template via `bypass_preamble_note`.

- [ ] **Step 8: End-to-end sanity check**

Run: `python3 .claude/features/tdd-subagent/scripts/dispatch-tdd-subagent.py --scope contract --spec .claude/features/contract/docs/spec/spec.md` (or any real feature).
Expected: prints a valid assembled prompt to stdout that contains the policy block, the SPEC section, all 7 named steps, and the HANDOFF schema. Verify the content matches what the previous f-string version produced (modulo whitespace).

## Phase B → TDD-cycle completion

Dispatch `rabbit-feature-touch` on tdd-subagent. HANDOFF should report `test_result: pass`.

---

# Phase C — per-feature sweep (parallelizable)

Goal: register every currently-surfaced skill in its owner feature's `feature.json` with a `prompts` entry + a minimal template. Skill bodies themselves are not edited — the PreToolUse hook adds policy via `additionalContext` alongside the existing body.

**Execution:** three independent `rabbit-feature-touch` cycles (rabbit-feature, rabbit-file, rabbit-config), parallelizable. Each cycle creates its own templates under contract; the cross-feature template-file creation follows the same approach-b pattern from Phase B (templates created in a small bundled contract sub-cycle as part of each Phase-C feature's TDD cycle).

To avoid the cross-feature scope-boundary blocker on every Phase C cycle, **bundle the template-file creations into a single contract sub-cycle that runs first**, then run the three feature cycles in parallel.

## Task C0: contract sub-cycle — create all Phase C templates

**Files:**
- Create: `.claude/features/contract/templates/prompts/rabbit-feature-touch.txt`
- Create: `.claude/features/contract/templates/prompts/rabbit-feature-spec.txt`
- Create: `.claude/features/contract/templates/prompts/rabbit-feature-new.txt`
- Create: `.claude/features/contract/templates/prompts/rabbit-feature-audit.txt`
- Create: `.claude/features/contract/templates/prompts/rabbit-feature-scope.txt`
- Create: `.claude/features/contract/templates/prompts/rabbit-file.txt`
- Create: `.claude/features/contract/templates/prompts/rabbit-config.txt`

For each skill, the template body is a single-line passthrough:

```
{{args}}
```

(The skill body itself is still loaded by the Skill tool from its SKILL.md file. The template is the additional context the hook injects alongside; for skills whose existing SKILL.md prose already covers the work, the passthrough just preserves whatever the orchestrator passed as `args`. If a skill later wants richer context shaping, edit its template.)

- [ ] **Step 1: Create the 7 template files** (each one-line `{{args}}`)

- [ ] **Step 2: Run contract test suite**

Run: `python3 .claude/features/contract/test/run.py`
Expected: passes. The lint check `test-check-prompts-section.py` does NOT fail because no feature.json yet declares entries for these new templates (slot/placeholder check only fires once both entry and template exist).

## Tasks C1, C2, C3 — per-feature feature.json + spec + test (parallel)

For each of {rabbit-feature, rabbit-file, rabbit-config}, run the following pattern. The three are independent and can be dispatched in parallel.

### Task C1: rabbit-feature

**Files:**
- Modify: `.claude/features/rabbit-feature/feature.json`
- Modify: `.claude/features/rabbit-feature/docs/spec/spec.md`
- Create: `.claude/features/rabbit-feature/test/test-prompts-declared.py`
- Modify: `.claude/features/rabbit-feature/test/run.py`

- [ ] **Step 1: Write the failing test**

Create `.claude/features/rabbit-feature/test/test-prompts-declared.py`:

```python
#!/usr/bin/env python3
"""Assert rabbit-feature's feature.json declares prompts entries for each
of its 5 skills (touch, spec, new, audit, scope)."""

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]
FEAT = REPO_ROOT / ".claude/features/rabbit-feature/feature.json"
EXPECTED = {"rabbit-feature-touch", "rabbit-feature-spec",
            "rabbit-feature-new", "rabbit-feature-audit",
            "rabbit-feature-scope"}


def main():
    data = json.loads(FEAT.read_text())
    prompts = {e["id"] for e in data.get("prompts", []) if e.get("kind") == "skill"}
    missing = EXPECTED - prompts
    extra = prompts - EXPECTED
    if missing:
        print(f"FAIL: missing skill entries: {sorted(missing)}")
        return 1
    if extra:
        print(f"FAIL: unexpected skill entries: {sorted(extra)}")
        return 1
    print("OK: all 5 skill entries present")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2: Run to verify it fails**

Expected: `FAIL: missing skill entries: [...]`.

- [ ] **Step 3: Add prompts section to feature.json**

Modify `.claude/features/rabbit-feature/feature.json`. Add:

```json
"prompts": [
  {"id": "rabbit-feature-touch", "kind": "skill",
   "inject": [".claude/features/policy/philosophy.md",
              ".claude/features/policy/spec-rules.md",
              ".claude/features/policy/coding-rules.md"],
   "slots": ["args"]},
  {"id": "rabbit-feature-spec", "kind": "skill",
   "inject": [".claude/features/policy/philosophy.md",
              ".claude/features/policy/spec-rules.md"],
   "slots": ["args"]},
  {"id": "rabbit-feature-new", "kind": "skill",
   "inject": [".claude/features/policy/philosophy.md",
              ".claude/features/policy/coding-rules.md"],
   "slots": ["args"]},
  {"id": "rabbit-feature-audit", "kind": "skill",
   "inject": [".claude/features/policy/philosophy.md",
              ".claude/features/policy/coding-rules.md"],
   "slots": ["args"]},
  {"id": "rabbit-feature-scope", "kind": "skill",
   "inject": [".claude/features/policy/philosophy.md"],
   "slots": ["args"]}
]
```

- [ ] **Step 4: Add spec invariant**

In `.claude/features/rabbit-feature/docs/spec/spec.md`, append an invariant:

> **Inv N** — `feature.json` declares a `prompts` entry (`kind: skill`) for
> each of the five surfaced skills (`rabbit-feature-touch`,
> `rabbit-feature-spec`, `rabbit-feature-new`, `rabbit-feature-audit`,
> `rabbit-feature-scope`), with `inject` lists matching the policy bundle
> documented in the prompt-contract design (touch/spec get spec-rules.md;
> touch/new/audit get coding-rules.md; scope gets philosophy.md only).
> Enforced by `test-prompts-declared.py`.

(Use whatever the next available invariant number is in the existing list.)

- [ ] **Step 5: Wire test into run.py**

Add `run_test("test-prompts-declared.py")`.

- [ ] **Step 6: Run new test + full suite**

Run: `python3 .claude/features/rabbit-feature/test/run.py`
Expected: passes.

- [ ] **Step 7: Sanity-check the lint**

Run: `python3 .claude/features/contract/scripts/enforcement/check-prompts-section.py`
Expected: exit 0 — all 5 entries valid, all templates exist (from Task C0), no slot/placeholder mismatch.

### Task C2: rabbit-file

Same shape as Task C1. Skill: `rabbit-file` (one skill). `inject`: philosophy + coding-rules (rabbit-file is code-authoring, files bugs and edits item.json).

### Task C3: rabbit-config

Same shape as Task C1. Skill: `rabbit-config` (one skill). `inject`: philosophy + coding-rules (rabbit-config mutates settings.local.json and marker files).

## Phase C → cycle completions

Three `rabbit-feature-touch` cycles, one per feature. Each emits its own HANDOFF + PR. Parallel-safe per the contract feature-touch design.

---

# Phase D — Cleanup

Goal: delete the dead `subagent-launch-template.txt` (superseded by per-callable templates under `templates/prompts/`).

**Execution:** one `rabbit-feature-touch` cycle on `contract`.

## Task D1: delete subagent-launch-template.txt + spec edit

**Files:**
- Delete: `.claude/features/contract/templates/subagent-launch-template.txt`
- Modify: `.claude/features/contract/docs/spec/spec.md` — remove the entry from Surface list

- [ ] **Step 1: Write the failing test**

Create `.claude/features/contract/test/test-no-subagent-launch-template.py`:

```python
#!/usr/bin/env python3
"""Regression: subagent-launch-template.txt MUST NOT exist (superseded by
per-callable templates under templates/prompts/)."""

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]
DEAD = REPO_ROOT / ".claude/features/contract/templates/subagent-launch-template.txt"


def main():
    if DEAD.exists():
        print(f"FAIL: dead template still present: {DEAD}")
        return 1
    print("OK: dead template absent")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2: Run to verify it fails**

Expected: `FAIL: dead template still present`.

- [ ] **Step 3: Delete the file**

```bash
git rm .claude/features/contract/templates/subagent-launch-template.txt
```

- [ ] **Step 4: Remove from spec Surface list**

In `.claude/features/contract/docs/spec/spec.md`, remove the line:
```
- `.claude/features/contract/templates/subagent-launch-template.txt`
```
from the **templates/** sub-list under Surface.

- [ ] **Step 5: Wire test into run.py**

Add `run_test("test-no-subagent-launch-template.py")`.

- [ ] **Step 6: Run full contract test suite**

Run: `python3 .claude/features/contract/test/run.py`
Expected: all tests pass; the new regression test passes; existing tests unaffected.

## Phase D → cycle completion

One `rabbit-feature-touch` cycle on contract. Final HANDOFF + PR.

---

# Close CONTRACT-BACKLOG-1

After Phase D lands, close the backlog item with the final impl SHA:

```bash
python3 .claude/features/rabbit-file/scripts/item-status.py set \
  --feature contract --type backlog --id CONTRACT-BACKLOG-1 \
  --status close \
  --reason "Implemented via Phases A–D — per-feature prompts section federated; assembler + PreToolUse hook + runtime APIs in contract; tdd-subagent migrated; per-feature sweep complete; cleanup landed." \
  --fix-commits "<Phase A SHA>,<Phase B SHA>,<Phase C1 SHA>,<Phase C2 SHA>,<Phase C3 SHA>,<Phase D SHA>"
```

(`--fix-commits` is comma-separated; collect the impl SHAs from each phase's `tdd-report-*.json`.)

---

## Self-review notes

- **Spec coverage:** every section of the design doc has at least one task:
  - Schema (design §"Schema: prompts section") → Task A1
  - Multi-callable example → Tasks C1–C3
  - validate_meta_contract integration → Task A2
  - Lint check → Task A2
  - Assembler script → Task A3
  - policy_block extraction → Task A3
  - PreToolUse hook → Task A4
  - Runtime APIs (cleanup + failure alerts) → Task A5
  - Schema enum updates → Task A5
  - Contract feature.json amendments → Task A6
  - Contract spec amendments → Task A6
  - tdd-subagent migration steps 1–5 → Phase B / Task B1 (with template-creation deferred to A1)
  - Other-features additive migration → Phase C
  - Dead template cleanup → Phase D
  - Migration sequence → Phases A→B→C→D map directly

- **Placeholder scan:** no TBD / TODO / "fill in"; every code block is concrete.

- **Cross-task consistency:** function names (`render_policy_block`, `check_prompts_section`, `validate_prompts_section`, `cleanup_old_prompts`, `check_prompt_injection_failures`, `build-prompt.py`, `prompt-injector.py`) used identically in every reference. Slot list for `tdd-subagent` (14 slots) is the same list in the design doc and in Task B1's feature.json snippet. The `{{slot_name}}` placeholder syntax is consistent across schema, template body, lint check, and assembler implementation.

- **Cross-feature work routing:** Phase B's note re: template-file creation under contract is explicitly handled by bundling into Phase A (approach-b). Phase C's Task C0 is a similar bundled contract sub-cycle. No phase has a hidden scope-boundary blocker.
