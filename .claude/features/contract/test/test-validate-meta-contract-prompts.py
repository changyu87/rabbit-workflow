#!/usr/bin/env python3
"""test-validate-meta-contract-prompts.py — exercises the prompts-section
arm of validate_meta_contract. Per spec Inv 53, validate_meta_contract
MUST be extended to dispatch to validate_prompts_section.

validate_prompts_section is the per-feature wrapper: it validates schema
shape only (no cross-feature uniqueness, no template existence, no
inject-path existence checks — those belong to check_prompts_section).
"""

import os
import sys
import json
import tempfile

sys.path.insert(0, os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")))
from lib.checks import validate_meta_contract, validate_prompts_section  # noqa: E402

BASE = {"name": "x", "version": "1.0.0", "owner": "x", "tdd_state": "spec",
        "summary": "x", "surface": {}, "deprecation_criterion": "x"}

FAIL = 0


def fail(msg):
    global FAIL
    print(f"FAIL: {msg}", file=sys.stderr)
    FAIL = 1


def ok(msg):
    print(f"PASS: {msg}")


def write(tmpdir, prompts):
    data = dict(BASE)
    data["prompts"] = prompts
    with open(os.path.join(tmpdir, "feature.json"), "w") as f:
        json.dump(data, f)
    return tmpdir


VALID = [{
    "id": "x",
    "kind": "skill",
    "inject": [".claude/features/policy/philosophy.md"],
    "slots": [],
}]

# t1: empty prompts array via validate_meta_contract -> pass
with tempfile.TemporaryDirectory() as td:
    r = validate_meta_contract(write(td, []))
    if r.passed:
        ok("t1: empty prompts array accepted by validate_meta_contract")
    else:
        fail(f"t1: empty prompts rejected: {r.messages}")

# t2: valid entry via validate_meta_contract -> pass
with tempfile.TemporaryDirectory() as td:
    r = validate_meta_contract(write(td, VALID))
    if r.passed:
        ok("t2: valid prompts entry accepted by validate_meta_contract")
    else:
        fail(f"t2: valid prompts rejected: {r.messages}")

# t3: non-array prompts via validate_meta_contract -> fail
with tempfile.TemporaryDirectory() as td:
    r = validate_meta_contract(write(td, {"id": "x"}))
    if not r.passed and any("array" in m for m in r.messages):
        ok("t3: non-array prompts rejected by validate_meta_contract")
    else:
        fail(f"t3: non-array acceptance bug: passed={r.passed}, messages={r.messages}")

# t4: entry missing required 'kind' via validate_meta_contract -> fail
with tempfile.TemporaryDirectory() as td:
    bad = [dict(VALID[0])]
    del bad[0]["kind"]
    r = validate_meta_contract(write(td, bad))
    if not r.passed and any("kind" in m for m in r.messages):
        ok("t4: missing kind rejected by validate_meta_contract")
    else:
        fail(f"t4: missing-kind acceptance bug: passed={r.passed}, messages={r.messages}")

# t5: invalid kind enum -> fail
with tempfile.TemporaryDirectory() as td:
    bad = [dict(VALID[0])]
    bad[0]["kind"] = "wizard"
    r = validate_meta_contract(write(td, bad))
    if not r.passed and any("kind" in m for m in r.messages):
        ok("t5: invalid kind enum rejected by validate_meta_contract")
    else:
        fail(f"t5: bad-kind acceptance bug: passed={r.passed}, messages={r.messages}")

# t6: entry with inject minItems=0 -> fail
with tempfile.TemporaryDirectory() as td:
    bad = [dict(VALID[0])]
    bad[0]["inject"] = []
    r = validate_meta_contract(write(td, bad))
    if not r.passed and any("inject" in m for m in r.messages):
        ok("t6: empty inject rejected by validate_meta_contract")
    else:
        fail(f"t6: empty-inject acceptance bug: passed={r.passed}, messages={r.messages}")

# t7: validate_prompts_section direct invocation on per-feature dir with no prompts
with tempfile.TemporaryDirectory() as td:
    data = dict(BASE)
    with open(os.path.join(td, "feature.json"), "w") as f:
        json.dump(data, f)
    r = validate_prompts_section(td)
    if r.passed:
        ok("t7: feature with no prompts section passes validate_prompts_section vacuously")
    else:
        fail(f"t7: no-prompts vacuous bug: {r.messages}")

# t8: validate_prompts_section direct invocation: schema-shape only, NOT
# cross-feature checks (so missing template, missing inject path, missing
# philosophy MUST NOT fail it).
with tempfile.TemporaryDirectory() as td:
    # use a valid schema-shape entry whose template and inject path don't exist
    r = validate_prompts_section(write(td, [{
        "id": "x",
        "kind": "skill",
        "inject": ["nonexistent.md"],  # cross-feature check would flag, but per-feature shouldn't
        "slots": [],
    }]))
    if r.passed:
        ok("t8: validate_prompts_section validates schema shape only (no cross-feature checks)")
    else:
        fail(f"t8: per-feature wrapper should not run cross-feature checks: {r.messages}")

if FAIL:
    print("test-validate-meta-contract-prompts: FAIL", file=sys.stderr)
    sys.exit(1)
print("test-validate-meta-contract-prompts: all checks passed.")
