#!/usr/bin/env python3
"""test-spec-surface-prompts-list-matches-disk.py — #870

End-to-end guard: the `## Surface` section's `templates/prompts/` bullet list in
docs/spec.md MUST enumerate exactly the *.txt template files that exist on disk
under .claude/features/contract/templates/prompts/ — no stale entries, no
omissions. This closes the regression where the Surface list named six
skill-passthrough templates (rabbit-feature-touch.txt, rabbit-spec-update.txt,
rabbit-feature-scaffold.txt, rabbit-feature-audit.txt, rabbit-feature-scope.txt,
rabbit-issue.txt) that Inv 47 explicitly asserts MUST NOT exist, while omitting
the live spec-create.txt. The expected set is derived from disk at test time —
a hardcoded list would silently rot when templates are added or removed.
"""

import os
import re
import sys

FEATURE_DIR = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
SPEC = os.path.join(FEATURE_DIR, "docs", "spec.md")
PROMPTS_DIR = os.path.join(FEATURE_DIR, "templates", "prompts")

FAIL = 0

# Truth from disk: the actual *.txt template basenames.
on_disk = {f for f in os.listdir(PROMPTS_DIR) if f.endswith(".txt")}

# Parse the `## Surface` section's `templates/prompts/` bullet list out of spec.md.
with open(SPEC) as f:
    lines = f.read().splitlines()

listed = set()
in_block = False
for line in lines:
    if line.strip().startswith("**templates/prompts/**"):
        in_block = True
        continue
    if in_block:
        m = re.match(r"\s*-\s+`(.+?)`\s*$", line)
        if m:
            listed.add(os.path.basename(m.group(1)))
            continue
        # A blank line or the next bold header ends the block.
        if line.strip() == "" or line.strip().startswith("**"):
            break

if not in_block:
    print("FAIL: could not locate '**templates/prompts/**' block in docs/spec.md", file=sys.stderr)
    sys.exit(1)

if listed == on_disk:
    print(f"PASS: Surface templates/prompts/ list matches disk exactly: {sorted(on_disk)}")
else:
    FAIL = 1
    stale = listed - on_disk
    missing = on_disk - listed
    if stale:
        print(f"FAIL: Surface lists templates absent on disk: {sorted(stale)}", file=sys.stderr)
    if missing:
        print(f"FAIL: Surface omits on-disk templates: {sorted(missing)}", file=sys.stderr)

if FAIL:
    print("test-spec-surface-prompts-list-matches-disk: FAIL", file=sys.stderr)
    sys.exit(1)

print("test-spec-surface-prompts-list-matches-disk: all checks passed.")
