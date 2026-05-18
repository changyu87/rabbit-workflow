#!/usr/bin/env python3
# test-skill-md-routing-and-main-session-red-flags.py — BACKLOG-2
# Asserts:
#   Inv 20: assembled TDD subagent prompt contains the SKILL.md routing
#           rule directing edits through Skill("skill-creator:skill-creator"),
#           placed in the IMPLEMENT-step region.
#   Inv 21: rabbit-feature-touch SKILL.md Red Flags forbids main-session
#           Write/Edit on any file under .claude/features/.
#   Inv 22: rabbit-feature-touch SKILL.md Red Flags forbids main-session
#           creation of .rabbit-scope-active markers (global and per-feature).
#   Inv 19 cleanup: SKILL.md (deployed and source) does NOT contain the
#           stale string "human-approval gated".
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
SKILL_PATHS = [
    os.path.join(
        REPO_ROOT, ".claude", "features", "tdd-subagent",
        "skills", "rabbit-feature-touch", "SKILL.md",
    ),
    os.path.join(REPO_ROOT, ".claude", "skills", "rabbit-feature-touch", "SKILL.md"),
]


def _generate_prompt():
    res = subprocess.run(
        ["python3", DISPATCH_PY, "--scope", "tdd-subagent", "--spec", SPEC_PATH],
        capture_output=True, text=True, check=False,
    )
    if res.returncode != 0:
        return None, f"dispatch-tdd-subagent.py exited {res.returncode}: {res.stderr}"
    return res.stdout, None


def check_inv20_prompt_routing():
    prompt, err = _generate_prompt()
    if prompt is None:
        return f"FAIL (Inv 20): {err}"

    # Required literal substrings for the routing rule.
    required = [
        'Skill("skill-creator:skill-creator")',
        "SKILL.md ROUTING",
        "basename is `SKILL.md`",
    ]
    missing = [s for s in required if s not in prompt]
    if missing:
        return f"FAIL (Inv 20): assembled prompt missing required substrings: {missing}"

    # Routing block must appear in IMPLEMENT-step region: before STEP 7 CODE-REVIEW
    # and after the E2E TEST RULE block. (Acceptable locations: anywhere before
    # STEP 7, since IMPLEMENT is STEP 6.)
    if "E2E TEST RULE" not in prompt or "STEP 7 — CODE-REVIEW" not in prompt:
        return "FAIL (Inv 20): anchor sections not found in prompt"
    routing_idx = prompt.index("SKILL.md ROUTING")
    code_review_idx = prompt.index("STEP 7 — CODE-REVIEW")
    e2e_idx = prompt.index("E2E TEST RULE")
    if not (e2e_idx < routing_idx < code_review_idx):
        return (
            f"FAIL (Inv 20): SKILL.md ROUTING idx={routing_idx} not between "
            f"E2E TEST RULE idx={e2e_idx} and STEP 7 idx={code_review_idx}"
        )
    return None


def check_inv21_red_flag_no_main_session_write():
    for path in SKILL_PATHS:
        if not os.path.isfile(path):
            return f"FAIL (Inv 21): SKILL.md not found at {path}"
        with open(path) as f:
            content = f.read()
        if "## Red Flags" not in content:
            return f"FAIL (Inv 21): '## Red Flags' header missing in {path}"
        red_flags_idx = content.index("## Red Flags")
        red_flags = content[red_flags_idx:]
        if "Write or Edit on any file under `.claude/features/`" not in red_flags:
            return (
                f"FAIL (Inv 21): Red Flags in {path} missing the literal "
                f"'Write or Edit on any file under `.claude/features/`'"
            )
    return None


def check_inv22_red_flag_no_main_session_scope_markers():
    for path in SKILL_PATHS:
        with open(path) as f:
            content = f.read()
        red_flags_idx = content.index("## Red Flags")
        red_flags = content[red_flags_idx:]
        required = [
            ".rabbit-scope-active",
            ".rabbit-scope-active-<feature>",
        ]
        missing = [s for s in required if s not in red_flags]
        if missing:
            return (
                f"FAIL (Inv 22): Red Flags in {path} missing required substrings: {missing}"
            )
        # Must explicitly mention this is a main-session prohibition.
        if "Main session" not in red_flags and "main session" not in red_flags:
            return (
                f"FAIL (Inv 22): Red Flags in {path} does not name 'main session' "
                f"as the prohibited actor"
            )
    return None


def check_inv19_cleanup_stale_string_absent():
    stale = "human-approval gated"
    for path in SKILL_PATHS:
        with open(path) as f:
            content = f.read()
        if stale in content:
            return f"FAIL (Inv 19 cleanup): {path} still contains stale '{stale}'"
    return None


def main():
    checks = [
        ("Inv 20: SKILL.md routing in assembled prompt", check_inv20_prompt_routing),
        ("Inv 21: Red Flag — no main-session Write/Edit", check_inv21_red_flag_no_main_session_write),
        ("Inv 22: Red Flag — no main-session scope markers", check_inv22_red_flag_no_main_session_scope_markers),
        ("Inv 19 cleanup: stale 'human-approval gated' absent", check_inv19_cleanup_stale_string_absent),
    ]
    fail_count = 0
    for label, fn in checks:
        err = fn()
        if err is None:
            print(f"PASS: {label}")
        else:
            print(err)
            fail_count += 1
    if fail_count:
        print(f"FAIL: {fail_count} check(s) failed")
        return 1
    print("PASS: all SKILL.md routing + main-session Red Flag checks")
    return 0


if __name__ == "__main__":
    sys.exit(main())
