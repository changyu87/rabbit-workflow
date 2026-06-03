#!/usr/bin/env python3
"""test-specs-layout.py — specs/ migration (issue #399 Phase 2)

End-to-end test verifying rabbit-meta's spec artifacts live under the new
specs/ layout and the legacy docs/spec/ directory is gone, while docs/bugs/
is retained:
  - t1: specs/spec.md exists and is non-empty
  - t2: specs/contract.md exists and is non-empty
  - t3: docs/spec/ directory no longer exists
  - t4: docs/bugs/ directory is retained
  - t5: specs/spec.md frontmatter declares feature: rabbit-meta
"""

import os
import re
import sys

FEATURE_DIR = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

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


# t1: specs/spec.md exists and non-empty
spec_md = os.path.join(FEATURE_DIR, "specs", "spec.md")
if os.path.isfile(spec_md) and os.path.getsize(spec_md) > 0:
    ok("t1", "specs/spec.md exists and is non-empty")
else:
    fail_t("t1", f"specs/spec.md missing or empty at {spec_md}")

# t2: specs/contract.md exists and non-empty
contract_md = os.path.join(FEATURE_DIR, "specs", "contract.md")
if os.path.isfile(contract_md) and os.path.getsize(contract_md) > 0:
    ok("t2", "specs/contract.md exists and is non-empty")
else:
    fail_t("t2", f"specs/contract.md missing or empty at {contract_md}")

# t3: docs/spec/ no longer exists
legacy = os.path.join(FEATURE_DIR, "docs", "spec")
if not os.path.exists(legacy):
    ok("t3", "docs/spec/ is gone")
else:
    fail_t("t3", f"legacy docs/spec/ still present at {legacy}")

# t4: docs/bugs/ retained
bugs = os.path.join(FEATURE_DIR, "docs", "bugs")
if os.path.isdir(bugs):
    ok("t4", "docs/bugs/ retained")
else:
    fail_t("t4", f"docs/bugs/ missing at {bugs}")

# t5: specs/spec.md frontmatter feature: rabbit-meta
try:
    with open(spec_md) as f:
        body = f.read()
except OSError:
    body = ""
m = re.search(r"^feature:\s*(.+)$", body, re.MULTILINE)
if m and m.group(1).strip() == "rabbit-meta":
    ok("t5", "specs/spec.md declares feature: rabbit-meta")
else:
    got = m.group(1).strip() if m else "<missing>"
    fail_t("t5", f"specs/spec.md feature is {got!r}, expected 'rabbit-meta'")

print()
print(f"Results: {PASS} passed, {FAIL} failed")
sys.exit(0 if FAIL == 0 else 1)
