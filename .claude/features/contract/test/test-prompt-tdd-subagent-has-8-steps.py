#!/usr/bin/env python3
"""test-prompt-tdd-subagent-has-8-steps.py — Inv 57 (tdd-subagent.txt body shape)

End-to-end test verifying the tdd-subagent.txt prompt template carries the
8-step TDD cycle (with SYNC-DEPLOYED inserted as STEP 5 between IMPLEMENT and
CODE-REVIEW), the moved git-commit ordering (commit lands at end of STEP 5,
not inside STEP 4 IMPLEMENT loop), and the bumped template_version marker.

This test backs the cross-feature dependency: tdd-subagent's state machine
gained a `sync-deployed` state between `impl` and `test-green`; the prompt
template body MUST reflect that state-machine shape so the running subagent
actually performs the sync-deployed step.
"""

import os
import re
import sys

FEATURE_DIR = os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
)
TEMPLATE_PATH = os.path.join(
    FEATURE_DIR, "templates", "prompts", "tdd-subagent.txt"
)

PASS = 0
FAIL = 0


def ok(n, msg):
    global PASS
    print(f"  PASS {n}: {msg}")
    PASS += 1


def fail_t(n, msg):
    global FAIL
    print(f"  FAIL {n}: {msg}", file=sys.stderr)
    FAIL += 1


with open(TEMPLATE_PATH) as f:
    content = f.read()
lines = content.split("\n")

# t-template-version-bumped: first line is a semver marker strictly greater
# than the pre-change baseline of 1.2.0. We assert >= 1.3.0 (the next bump
# captured by this change).
MARKER_RE = re.compile(r"^# template_version: (\d+)\.(\d+)\.(\d+)$")
m = MARKER_RE.match(lines[0]) if lines else None
if m:
    major, minor, patch = int(m.group(1)), int(m.group(2)), int(m.group(3))
    ver = (major, minor, patch)
    if ver >= (1, 3, 0):
        ok("t-template-version-bumped", f"first line marker {lines[0]!r} >= 1.3.0")
    else:
        fail_t(
            "t-template-version-bumped",
            f"first line marker {lines[0]!r} must be bumped to >= 1.3.0",
        )
else:
    fail_t(
        "t-template-version-bumped",
        f"first line must be '# template_version: X.Y.Z', got {lines[0] if lines else '<empty>'!r}",
    )

# t-eight-steps-in-order: every STEP banner appears in order with the
# expected name. The new step is STEP 5 SYNC-DEPLOYED; CODE-REVIEW moves to
# STEP 6, TEST-GREEN to STEP 7, UNLOCK to STEP 8.
EXPECTED = [
    (1, "LOCK"),
    (2, "TEST-WRITE"),
    (3, "TEST-RED"),
    (4, "IMPLEMENT"),
    (5, "SYNC-DEPLOYED"),
    (6, "CODE-REVIEW"),
    (7, "TEST-GREEN"),
    (8, "UNLOCK"),
]
STEP_BANNER_RE = re.compile(r"^STEP (\d+) — (.+)$")
found_banners = []
for line in lines:
    m = STEP_BANNER_RE.match(line)
    if m:
        found_banners.append((int(m.group(1)), m.group(2).strip()))

if found_banners == EXPECTED:
    ok(
        "t-eight-steps-in-order",
        f"all 8 STEP banners present in order: {found_banners!r}",
    )
else:
    fail_t(
        "t-eight-steps-in-order",
        f"expected {EXPECTED!r}, got {found_banners!r}",
    )

# t-mentions-7-steps-corrected: header preamble should reference 8 steps,
# not 7. The old template said "Execute the 7 named steps below IN ORDER".
if re.search(r"\b8 named steps\b", content):
    ok("t-mentions-8-steps", "preamble mentions '8 named steps'")
else:
    fail_t(
        "t-mentions-8-steps",
        "preamble must say '8 named steps' (was '7' before this change)",
    )


# --- helpers to slice STEP sections by header position ---

def _section(step_num):
    """Return the body text between STEP <step_num> header and the next STEP header."""
    start_re = re.compile(rf"^STEP {step_num} — ", re.MULTILINE)
    end_re = re.compile(rf"^STEP {step_num + 1} — ", re.MULTILINE)
    sm = start_re.search(content)
    if not sm:
        return None
    after = content[sm.end():]
    em = end_re.search(after)
    if em:
        return after[: em.start()]
    return after


# t-sync-deployed-body: STEP 5 body must mention all four byte-copy publish
# APIs, the tdd-step.py sync-deployed transition, and the fail-HANDOFF shape
# with tdd_state: impl.
step5 = _section(5)
if step5 is None:
    fail_t("t-sync-deployed-body", "STEP 5 section not found")
else:
    missing = []
    for needle in [
        "publish_file",
        "publish_hook",
        "publish_skill",
        "publish_settings",
        "sync-deployed",
        "tdd_state: impl",
    ]:
        if needle not in step5:
            missing.append(needle)
    if not missing:
        ok(
            "t-sync-deployed-body",
            "STEP 5 mentions all four publish APIs + sync-deployed transition + fail-HANDOFF",
        )
    else:
        fail_t(
            "t-sync-deployed-body",
            f"STEP 5 body missing required mentions: {missing!r}",
        )

# t-step5-banner-name: header line literal banner is SYNC-DEPLOYED.
if re.search(r"^STEP 5 — SYNC-DEPLOYED$", content, re.MULTILINE):
    ok("t-step5-banner-name", "STEP 5 banner is 'SYNC-DEPLOYED'")
else:
    fail_t(
        "t-step5-banner-name",
        "STEP 5 banner header must be 'SYNC-DEPLOYED'",
    )

# t-step4-implement-no-in-loop-commit: STEP 4 IMPLEMENT body must NOT contain
# the in-loop `git commit -m "fix({{feature_name}}): ...` line. The commit
# moves to STEP 5. Detection: the substring `git commit -m "fix(` is the
# unique marker for the old in-loop commit instruction.
step4 = _section(4)
if step4 is None:
    fail_t("t-step4-no-in-loop-commit", "STEP 4 section not found")
else:
    if 'git commit -m "fix(' in step4:
        fail_t(
            "t-step4-no-in-loop-commit",
            "STEP 4 IMPLEMENT body still contains an in-loop `git commit -m \"fix(...\"` "
            "instruction — the commit must move to end of STEP 5 SYNC-DEPLOYED",
        )
    else:
        ok(
            "t-step4-no-in-loop-commit",
            "STEP 4 IMPLEMENT body has no in-loop 'fix(' commit instruction",
        )

# t-placeholders-preserved: the original 9 placeholder names must still all
# appear at least once (Inv 57 bidirectional slot correspondence is enforced
# separately by test-templates-prompts-bundle.py, but this is an extra guard
# against accidental rename during the rewrite).
REQUIRED_PLACEHOLDERS = {
    "feature_name",
    "spec_content",
    "impl_suggestion_block",
    "bypass_preamble_note",
    "feature_dir",
    "tdd_step_py",
    "repo_root",
    "max_iterations",
    "code_review_loop_note",
    "scope_marker_path",  # added #304 for mode-aware LOCK/UNLOCK path
}
found_placeholders = set(re.findall(r"\{\{([a-z][a-z0-9_]*)\}\}", content))
missing_p = REQUIRED_PLACEHOLDERS - found_placeholders
extra_p = found_placeholders - REQUIRED_PLACEHOLDERS
if not missing_p and not extra_p:
    ok(
        "t-placeholders-preserved",
        f"all 9 declared placeholders present, no extras",
    )
else:
    fail_t(
        "t-placeholders-preserved",
        f"missing={sorted(missing_p)} extra={sorted(extra_p)}",
    )

print()
print(f"Results: {PASS} passed, {FAIL} failed")
sys.exit(0 if FAIL == 0 else 1)
