#!/usr/bin/env python3
"""test-templates-prompts-bundle.py — Inv 57

End-to-end test verifying the templates/prompts/ bundle:
  - directory exists with exactly 8 plain-text template files
  - each file's first line matches the canonical '# template_version: X.Y.Z' semver marker
    (per-file versions are independent — files may evolve at different cadences)
  - the 6 skill passthrough templates are exactly 2 lines (marker + '{{args}}')
  - tdd-subagent.txt carries exactly the 14 declared placeholders (set equality)
  - tdd-subagent.txt does NOT contain '{{policy_block}}' (assembler prepends)
"""

import os
import re
import sys

FEATURE_DIR = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
PROMPTS_DIR = os.path.join(FEATURE_DIR, "templates", "prompts")

EXPECTED_FILES = [
    "tdd-subagent.txt",
    "rabbit-feature-touch.txt",
    "rabbit-feature-spec.txt",
    "rabbit-feature-new.txt",
    "rabbit-feature-audit.txt",
    "rabbit-feature-scope.txt",
    "rabbit-config.txt",
    "spec-seeder.txt",
]

SKILL_PASSTHROUGH_FILES = [
    "rabbit-feature-touch.txt",
    "rabbit-feature-spec.txt",
    "rabbit-feature-new.txt",
    "rabbit-feature-audit.txt",
    "rabbit-feature-scope.txt",
    "rabbit-config.txt",
]

DECLARED_TDD_PLACEHOLDERS = {
    "feature_name",
    "spec_content",
    "impl_suggestion_block",
    "bypass_preamble_note",
    "feature_dir",
    "tdd_step_py",
    "repo_root",
    "max_iterations",
    "code_review_loop_note",
    "linked_item_value",
    "item_type_value",
    "close_calls_block",
    "handoff_closed_items_block",
    "handoff_closed_items_json",
}

MARKER_RE = re.compile(r"^# template_version: \d+\.\d+\.\d+$")
# Skill passthroughs are stable two-line files; their marker has not been bumped.
PASSTHROUGH_MARKER = "# template_version: 1.0.0"

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


# t-dir-exists
if os.path.isdir(PROMPTS_DIR):
    ok("t-dir-exists", f"{PROMPTS_DIR} exists")
else:
    fail_t("t-dir-exists", f"{PROMPTS_DIR} is not a directory")

# t-file-exists
for fname in EXPECTED_FILES:
    fpath = os.path.join(PROMPTS_DIR, fname)
    if os.path.isfile(fpath):
        ok(f"t-file-exists[{fname}]", "present")
    else:
        fail_t(f"t-file-exists[{fname}]", f"missing: {fpath}")

# t-marker-on-line-1
for fname in EXPECTED_FILES:
    fpath = os.path.join(PROMPTS_DIR, fname)
    if not os.path.isfile(fpath):
        continue
    with open(fpath) as f:
        first_line = f.readline().rstrip("\n")
    if MARKER_RE.match(first_line):
        ok(f"t-marker-on-line-1[{fname}]", f"semver marker matches: {first_line!r}")
    else:
        fail_t(
            f"t-marker-on-line-1[{fname}]",
            f"expected '# template_version: X.Y.Z' semver, got {first_line!r}",
        )

# t-skill-passthroughs: exactly 2 lines, line 2 == '{{args}}'
for fname in SKILL_PASSTHROUGH_FILES:
    fpath = os.path.join(PROMPTS_DIR, fname)
    if not os.path.isfile(fpath):
        continue
    with open(fpath) as f:
        content = f.read()
    lines = content.split("\n")
    # Trailing newline yields an empty string at end of split; expect that.
    # Allow trailing empty entry for trailing newline.
    if lines and lines[-1] == "":
        lines = lines[:-1]
    if len(lines) == 2 and lines[0] == PASSTHROUGH_MARKER and lines[1] == "{{args}}":
        ok(f"t-skill-passthroughs[{fname}]", "exactly 2 lines, marker + '{{args}}'")
    else:
        fail_t(
            f"t-skill-passthroughs[{fname}]",
            f"expected 2 lines ({PASSTHROUGH_MARKER!r}, '{{{{args}}}}'), got {lines!r}",
        )

# t-tdd-subagent-placeholders: set equality
tdd_path = os.path.join(PROMPTS_DIR, "tdd-subagent.txt")
if os.path.isfile(tdd_path):
    with open(tdd_path) as f:
        tdd_content = f.read()
    found = set(re.findall(r"\{\{([a-z][a-z0-9_]*)\}\}", tdd_content))
    if found == DECLARED_TDD_PLACEHOLDERS:
        ok("t-tdd-subagent-placeholders", f"set equals {len(DECLARED_TDD_PLACEHOLDERS)} declared placeholders")
    else:
        missing = DECLARED_TDD_PLACEHOLDERS - found
        extra = found - DECLARED_TDD_PLACEHOLDERS
        fail_t(
            "t-tdd-subagent-placeholders",
            f"missing={sorted(missing)} extra={sorted(extra)}",
        )

    # t-no-policy-block-placeholder
    if "{{policy_block}}" not in tdd_content:
        ok("t-no-policy-block-placeholder", "'{{policy_block}}' absent")
    else:
        fail_t(
            "t-no-policy-block-placeholder",
            "'{{policy_block}}' MUST NOT appear in tdd-subagent.txt (Inv 57)",
        )

print()
print(f"Results: {PASS} passed, {FAIL} failed")
sys.exit(0 if FAIL == 0 else 1)
