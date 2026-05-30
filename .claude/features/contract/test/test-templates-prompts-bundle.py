#!/usr/bin/env python3
"""test-templates-prompts-bundle.py — Inv 57

End-to-end test verifying the templates/prompts/ bundle:
  - directory exists
  - bidirectional correspondence between declared prompts[].id values (across
    every .claude/features/*/feature.json) and on-disk *.txt template files
    under .claude/features/contract/templates/prompts/ (no hardcoded list — a
    hardcoded list silently rots when features add or remove prompts entries)
  - each file's first line matches the canonical '# template_version: X.Y.Z' semver marker
    (per-file versions are independent — files may evolve at different cadences)
  - the skill passthrough templates (kind=='skill' entries) are exactly 2 lines
    (marker + '{{args}}'), marker pinned at 1.0.0 per Inv 57 (b)
  - tdd-subagent.txt carries exactly the 9 declared placeholders (set equality)
  - tdd-subagent.txt does NOT contain '{{policy_block}}' (assembler prepends)
"""

import glob
import json
import os
import re
import sys

FEATURE_DIR = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
PROMPTS_DIR = os.path.join(FEATURE_DIR, "templates", "prompts")
FEATURES_ROOT = os.path.normpath(os.path.join(FEATURE_DIR, ".."))

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
}

MARKER_RE = re.compile(r"^# template_version: \d+\.\d+\.\d+$")
# Skill passthroughs are stable two-line files; their marker is pinned at 1.0.0
# per Inv 57 (b) until their structural shape itself changes.
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


# Derive the declared set from every feature.json's prompts[] entries.
# DECLARED_IDS  -> set of all ids
# DECLARED_BY_KIND -> dict[id] = kind
DECLARED_IDS = set()
DECLARED_BY_KIND = {}
for feat_json in sorted(glob.glob(os.path.join(FEATURES_ROOT, "*", "feature.json"))):
    try:
        with open(feat_json) as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        continue
    for entry in data.get("prompts", []) or []:
        pid = entry.get("id")
        kind = entry.get("kind")
        if not pid:
            continue
        DECLARED_IDS.add(pid)
        DECLARED_BY_KIND[pid] = kind

# t-dir-exists
if os.path.isdir(PROMPTS_DIR):
    ok("t-dir-exists", f"{PROMPTS_DIR} exists")
else:
    fail_t("t-dir-exists", f"{PROMPTS_DIR} is not a directory")

# Compute on-disk ids: strip .txt suffix from each file in the prompts dir.
ON_DISK_IDS = set()
if os.path.isdir(PROMPTS_DIR):
    for fname in os.listdir(PROMPTS_DIR):
        if fname.endswith(".txt"):
            ON_DISK_IDS.add(fname[:-4])

# t-bidirectional: declared == on-disk (no orphan templates, no missing templates)
missing_templates = DECLARED_IDS - ON_DISK_IDS
orphan_templates = ON_DISK_IDS - DECLARED_IDS
if not missing_templates and not orphan_templates:
    ok(
        "t-bidirectional",
        f"declared==on-disk ({len(DECLARED_IDS)} ids: {sorted(DECLARED_IDS)})",
    )
else:
    parts = []
    if missing_templates:
        parts.append(f"declared but missing on disk: {sorted(missing_templates)}")
    if orphan_templates:
        parts.append(f"on disk but undeclared: {sorted(orphan_templates)}")
    fail_t("t-bidirectional", "; ".join(parts))

# t-marker-on-line-1 — every declared id's template carries the semver marker
for pid in sorted(DECLARED_IDS):
    fpath = os.path.join(PROMPTS_DIR, f"{pid}.txt")
    if not os.path.isfile(fpath):
        continue  # already flagged by t-bidirectional
    with open(fpath) as f:
        first_line = f.readline().rstrip("\n")
    if MARKER_RE.match(first_line):
        ok(f"t-marker-on-line-1[{pid}.txt]", f"semver marker matches: {first_line!r}")
    else:
        fail_t(
            f"t-marker-on-line-1[{pid}.txt]",
            f"expected '# template_version: X.Y.Z' semver, got {first_line!r}",
        )

# t-skill-passthroughs: exactly 2 lines, line 2 == '{{args}}', marker pinned 1.0.0
# Derived from DECLARED_BY_KIND filtered to kind == "skill".
SKILL_PASSTHROUGH_IDS = sorted(pid for pid, kind in DECLARED_BY_KIND.items() if kind == "skill")
for pid in SKILL_PASSTHROUGH_IDS:
    fpath = os.path.join(PROMPTS_DIR, f"{pid}.txt")
    if not os.path.isfile(fpath):
        continue
    with open(fpath) as f:
        content = f.read()
    lines = content.split("\n")
    # Trailing newline yields an empty string at end of split; expect that.
    if lines and lines[-1] == "":
        lines = lines[:-1]
    if len(lines) == 2 and lines[0] == PASSTHROUGH_MARKER and lines[1] == "{{args}}":
        ok(f"t-skill-passthroughs[{pid}.txt]", "exactly 2 lines, marker + '{{args}}'")
    else:
        fail_t(
            f"t-skill-passthroughs[{pid}.txt]",
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
