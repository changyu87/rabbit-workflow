#!/usr/bin/env python3
"""test-specs-layout.py — flat docs/ layout (issue #399 Phase 2b)

End-to-end test verifying rabbit-issue's spec artifacts live under the flat
docs/ layout, the legacy specs/ directory is gone, the root CHANGELOG.md is
relocated, and the pre-existing docs/bugs/ subtree is preserved as a sibling:
  - t1: docs/spec.md exists and is non-empty
  - t2: docs/contract.md exists and is non-empty
  - t3: specs/ directory no longer exists
  - t4: docs/bugs/ directory is retained (sibling, never replaced)
  - t5: docs/spec.md frontmatter declares feature: rabbit-issue
  - t6: docs/CHANGELOG.md exists and is non-empty
  - t7: root CHANGELOG.md no longer exists (moved under docs/)
  - t8: (E2E) the contract resolver resolves spec.md + contract.md at the
        flat docs/ location for rabbit-issue

Owner: rabbit-workflow team
"""

import importlib.util
import os
import re
import sys

FEATURE_DIR = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
FEATURES_ROOT = os.path.dirname(FEATURE_DIR)
CHECKS_PATH = os.path.join(FEATURES_ROOT, "contract", "lib", "checks.py")

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


# t1: docs/spec.md exists and non-empty
spec_md = os.path.join(FEATURE_DIR, "docs", "spec.md")
if os.path.isfile(spec_md) and os.path.getsize(spec_md) > 0:
    ok("t1", "docs/spec.md exists and is non-empty")
else:
    fail_t("t1", f"docs/spec.md missing or empty at {spec_md}")

# t2: docs/contract.md exists and non-empty
contract_md = os.path.join(FEATURE_DIR, "docs", "contract.md")
if os.path.isfile(contract_md) and os.path.getsize(contract_md) > 0:
    ok("t2", "docs/contract.md exists and is non-empty")
else:
    fail_t("t2", f"docs/contract.md missing or empty at {contract_md}")

# t3: specs/ no longer exists
legacy = os.path.join(FEATURE_DIR, "specs")
if not os.path.exists(legacy):
    ok("t3", "specs/ is gone")
else:
    fail_t("t3", f"legacy specs/ still present at {legacy}")

# t4: docs/bugs/ retained
bugs = os.path.join(FEATURE_DIR, "docs", "bugs")
if os.path.isdir(bugs):
    ok("t4", "docs/bugs/ retained")
else:
    fail_t("t4", f"docs/bugs/ missing at {bugs}")

# t5: docs/spec.md frontmatter feature: rabbit-issue
try:
    with open(spec_md) as f:
        body = f.read()
except OSError:
    body = ""
m = re.search(r"^feature:\s*(.+)$", body, re.MULTILINE)
if m and m.group(1).strip() == "rabbit-issue":
    ok("t5", "docs/spec.md declares feature: rabbit-issue")
else:
    got = m.group(1).strip() if m else "<missing>"
    fail_t("t5", f"docs/spec.md feature is {got!r}, expected 'rabbit-issue'")

# t6: docs/CHANGELOG.md exists and non-empty
changelog_md = os.path.join(FEATURE_DIR, "docs", "CHANGELOG.md")
if os.path.isfile(changelog_md) and os.path.getsize(changelog_md) > 0:
    ok("t6", "docs/CHANGELOG.md exists and is non-empty")
else:
    fail_t("t6", f"docs/CHANGELOG.md missing or empty at {changelog_md}")

# t7: root CHANGELOG.md is gone (relocated under docs/)
root_changelog = os.path.join(FEATURE_DIR, "CHANGELOG.md")
if not os.path.exists(root_changelog):
    ok("t7", "root CHANGELOG.md is gone (moved to docs/CHANGELOG.md)")
else:
    fail_t("t7", f"root CHANGELOG.md still present at {root_changelog}")

# t8: (E2E) the contract resolver targets the flat docs/ location
spec = importlib.util.spec_from_file_location("checks", CHECKS_PATH)
checks = importlib.util.module_from_spec(spec)
spec.loader.exec_module(checks)
resolved_spec = checks.resolve_spec_path(FEATURE_DIR, "spec.md")
resolved_contract = checks.resolve_spec_path(FEATURE_DIR, "contract.md")
expected_spec = os.path.join(FEATURE_DIR, "docs", "spec.md")
expected_contract = os.path.join(FEATURE_DIR, "docs", "contract.md")
if resolved_spec == expected_spec and resolved_contract == expected_contract:
    ok("t8", "contract resolver targets flat docs/spec.md + docs/contract.md")
else:
    fail_t(
        "t8",
        f"resolver returned {resolved_spec!r} / {resolved_contract!r}, "
        f"expected {expected_spec!r} / {expected_contract!r}",
    )

print()
print(f"Results: {PASS} passed, {FAIL} failed")
sys.exit(0 if FAIL == 0 else 1)
