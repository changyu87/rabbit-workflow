#!/usr/bin/env python3
# test-scope-boundary-red-flag.py — BUG-4
# Asserts that the assembled TDD subagent prompt contains a SCOPE BOUNDARY
# RED FLAG section prohibiting creation of out-of-scope scope markers, with
# a blocked HANDOFF template specifying cross_feature_dependency,
# unwritten_paths, and notes fields.
import os
import subprocess
import sys

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
DISPATCH_PY = os.path.join(
    REPO_ROOT, ".claude", "features", "tdd-subagent", "scripts", "dispatch-tdd-subagent.py"
)
SPEC_PATH = os.path.join(
    REPO_ROOT, ".claude", "features", "tdd-subagent", "docs", "spec", "spec.md"
)


def main():
    feature = "tdd-subagent"
    res = subprocess.run(
        ["python3", DISPATCH_PY, "--scope", feature, "--spec", SPEC_PATH],
        capture_output=True, text=True, check=False,
    )
    if res.returncode != 0:
        print(f"FAIL: dispatch-tdd-subagent.py exited {res.returncode}\nSTDERR: {res.stderr}")
        return 1
    prompt = res.stdout

    required = [
        "SCOPE BOUNDARY",
        "RED FLAG",
        "tdd_state: blocked",
        "cross_feature_dependency",
        "unwritten_paths",
        f"MUST NOT create any .rabbit-scope-active-<X> marker where X != {feature}",
    ]
    missing = [s for s in required if s not in prompt]
    if missing:
        print(f"FAIL: assembled prompt missing required substrings: {missing}")
        return 1

    # The section must appear between E2E TEST RULE and STEP 1 SPEC-READ.
    if "E2E TEST RULE" not in prompt or "STEP 1 — SPEC-READ" not in prompt:
        print("FAIL: anchor sections not found in prompt")
        return 1
    e2e_idx = prompt.index("E2E TEST RULE")
    step1_idx = prompt.index("STEP 1 — SPEC-READ")
    scope_idx = prompt.index("SCOPE BOUNDARY")
    if not (e2e_idx < scope_idx < step1_idx):
        print(
            f"FAIL: SCOPE BOUNDARY (idx={scope_idx}) is not between "
            f"E2E TEST RULE (idx={e2e_idx}) and STEP 1 SPEC-READ (idx={step1_idx})"
        )
        return 1

    print("PASS: assembled prompt contains SCOPE BOUNDARY red flag with blocked HANDOFF template")
    return 0


if __name__ == "__main__":
    sys.exit(main())
