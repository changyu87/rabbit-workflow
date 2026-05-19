#!/usr/bin/env python3
# test-bug-29-multi-issue.py — e2e tests for RABBIT-FEATURE-SCOPE-BUG-29.
#
# Covers:
#   (a) version sync — spec.md, SKILL.md, and feature.json must agree on version
#   (b) Inv 7 enforcement is verified in test-no-inline-python3.py
#       (this file asserts the test file actually greps for forbidden patterns)
#   (c) contract.md documents exit 1 (runtime error) alongside exit 0/2

import json
import re
import subprocess
from pathlib import Path

repo_root = subprocess.check_output(["git", "rev-parse", "--show-toplevel"], text=True).strip()
feature_dir = Path(repo_root) / ".claude/features/rabbit-feature-scope"
spec_md = feature_dir / "docs/spec/spec.md"
contract_md = feature_dir / "docs/spec/contract.md"
skill_md = feature_dir / "skills/rabbit-feature-scope/SKILL.md"
feature_json = feature_dir / "feature.json"
inv7_test = feature_dir / "test/test-no-inline-python3.py"

PASS = 0
FAIL = 0


def ok(msg):
    global PASS
    print(f"PASS: {msg}")
    PASS += 1


def fail(msg):
    global FAIL
    print(f"FAIL: {msg}")
    FAIL += 1


# ---------------------------------------------------------------------------
# (a) Version sync. spec.md frontmatter `version:` MUST equal SKILL.md
# frontmatter `version:` AND feature.json `version`.
# ---------------------------------------------------------------------------
def extract_frontmatter_version(path):
    text = path.read_text()
    # YAML frontmatter is delimited by --- lines at the top.
    m = re.match(r"---\n(.*?)\n---", text, re.DOTALL)
    if not m:
        return None
    for line in m.group(1).splitlines():
        if line.startswith("version:"):
            return line.split(":", 1)[1].strip()
    return None


spec_version = extract_frontmatter_version(spec_md)
skill_version = extract_frontmatter_version(skill_md)
with open(feature_json) as f:
    fj_version = json.load(f).get("version")

if spec_version and skill_version and fj_version:
    if spec_version == skill_version == fj_version:
        ok(f"BUG-29(a): versions aligned across spec/skill/feature.json: {spec_version}")
    else:
        fail(
            f"BUG-29(a): version skew — spec={spec_version}, "
            f"skill={skill_version}, feature.json={fj_version}"
        )
else:
    fail(
        f"BUG-29(a): could not extract version (spec={spec_version}, "
        f"skill={skill_version}, feature.json={fj_version})"
    )

# ---------------------------------------------------------------------------
# (b) test-no-inline-python3.py must actually grep resolve-scope.py for
# forbidden patterns (the test name promises Inv 7 enforcement).
# ---------------------------------------------------------------------------
inv7_src = inv7_test.read_text()
# The test source must mention the forbidden patterns it is meant to detect.
required_markers = ["python3 -c", "heredoc"]
missing = [m for m in required_markers if m not in inv7_src]
if not missing:
    ok("BUG-29(b): test-no-inline-python3.py references forbidden patterns")
else:
    fail(f"BUG-29(b): test-no-inline-python3.py missing markers: {missing}")

# Also: the test must actually read resolve-scope.py source (not just check
# shebang). Look for a `.read_text()` or `open(...).read()` call paired with
# a regex/`re.search` or `in src` check.
if "read_text()" in inv7_src and ("re.search" in inv7_src or " in src" in inv7_src):
    ok("BUG-29(b): test-no-inline-python3.py reads source and pattern-matches")
else:
    fail("BUG-29(b): test-no-inline-python3.py does not pattern-match source")

# ---------------------------------------------------------------------------
# (c) contract.md must document exit 1 (runtime error) alongside exit 0/2.
# ---------------------------------------------------------------------------
contract_text = contract_md.read_text()
if re.search(r"exit\s*1\b", contract_text, re.IGNORECASE):
    ok("BUG-29(c): contract.md documents exit 1")
else:
    fail("BUG-29(c): contract.md missing exit 1 documentation")

# Sanity: exit 0 and exit 2 must also be documented (no regression).
for code in ("0", "2"):
    if re.search(rf"exit\s*{code}\b", contract_text, re.IGNORECASE):
        ok(f"BUG-29(c): contract.md retains exit {code} documentation")
    else:
        fail(f"BUG-29(c): contract.md missing exit {code} documentation")

print()
print(f"Results: {PASS} passed, {FAIL} failed")
import sys
sys.exit(0 if FAIL == 0 else 1)
