#!/usr/bin/env python3
"""test-housekeeping-683-redundancy-removed.py — #683 measured-removal pass.

#683 ("Housekeeping round 2 under #639") mandates REMOVAL of dead/redundant
doc content (lines deleted), not rewording. This E2E regression pins the
specific redundancy collapses landed by the pass and guards the load-bearing
content that MUST survive.

Each assertion derives from a #639 prove-it-dead-or-flag check recorded in
docs/CHANGELOG.md (v1.8.0):

  t1: spec.md no longer carries a "## Tech Stack" section. The Tech-Stack
      blurb ("Python 3 stdlib only. Imports contract.lib.mutation at runtime.
      No Bash runtime dependency.") was duplicated VERBATIM between docs/spec.md
      and docs/contract.md; no validator requires it in spec.md. Collapsed to
      one authoritative copy in contract.md.
  t2: contract.md RETAINS the authoritative "## Tech Stack" section (the
      surviving single copy).
  t3: the load-bearing "retired" status-enum literal stays at spec.md line 44,
      preserving the contract strict-tier ALLOWLIST line-pin
      ("rabbit-config", "spec.md", 44, "retired"). Any deletion above line 44
      would shift it and break the cross-feature gate.
  t4: SKILL.md body no longer re-enumerates the subcommand catalog (the
      "## Subcommands" bullet list and the "Values-style" / "Actions-style"
      usage sub-blocks). The catalog lives authoritatively in the SKILL.md
      frontmatter `description` (load-bearing, enforced by
      test-skill-description.py).
  t5: every active configurable remains named in SKILL.md (frontmatter
      description carries them) — regression guard mirroring
      test-skill-no-dead-permissions t-keep1/t-keep2.
"""

import os
import re
import sys

FEATURE_DIR = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
SPEC_MD = os.path.join(FEATURE_DIR, "docs/spec.md")
CONTRACT_MD = os.path.join(FEATURE_DIR, "docs/contract.md")
SKILL_MD = os.path.join(FEATURE_DIR, "skills/rabbit-config/SKILL.md")

FAIL = 0


def fail(n, msg):
    global FAIL
    print(f"FAIL t{n}: {msg}", file=sys.stderr)
    FAIL = 1


def ok(n, msg):
    print(f"ok t{n}: {msg}")


with open(SPEC_MD) as f:
    spec = f.read()
with open(CONTRACT_MD) as f:
    contract = f.read()
with open(SKILL_MD) as f:
    skill = f.read()

# t1: spec.md no longer carries a Tech Stack section.
if re.search(r"(?m)^##\s+Tech Stack\s*$", spec):
    fail(1, "spec.md still carries a '## Tech Stack' section (redundant with contract.md)")
else:
    ok(1, "spec.md has no '## Tech Stack' section")

# t2: contract.md retains the authoritative Tech Stack section.
if not re.search(r"(?m)^##\s+Tech Stack\s*$", contract):
    fail(2, "contract.md no longer carries the authoritative '## Tech Stack' section")
else:
    ok(2, "contract.md retains the authoritative '## Tech Stack' section")

# t3: the 'retired' literal stays at spec.md line 44 (allowlist line-pin).
spec_lines = spec.splitlines()
if len(spec_lines) < 44 or "retired" not in spec_lines[43]:
    got = spec_lines[43] if len(spec_lines) >= 44 else "<no line 44>"
    fail(3, f"'retired' literal not on spec.md line 44 (allowlist line-pin broken); line 44 = {got!r}")
else:
    ok(3, "'retired' literal preserved at spec.md line 44 (allowlist line-pin intact)")

# t4: SKILL.md body no longer re-enumerates the subcommand catalog.
if re.search(r"(?m)^##\s+Subcommands\s*$", skill):
    fail(4, "SKILL.md still carries a redundant '## Subcommands' enumeration section")
elif re.search(r"(?m)^###\s+Values-style", skill) or re.search(r"(?m)^###\s+Actions-style", skill):
    fail(4, "SKILL.md still carries redundant Values-style/Actions-style usage sub-blocks")
else:
    ok(4, "SKILL.md body no longer re-enumerates the subcommand catalog")

# t5: every active configurable remains documented in SKILL.md (frontmatter).
required = ["human-approval", "bypass-permissions", "prompt-threshold",
           "allowed-tools", "bash-allow"]
missing = [c for c in required if c not in skill]
if missing:
    fail(5, f"SKILL.md no longer documents active configurables: {missing!r}")
else:
    ok(5, "all active configurables still documented in SKILL.md")

if FAIL:
    print("test-housekeeping-683-redundancy-removed: FAIL", file=sys.stderr)
    sys.exit(1)
print("test-housekeeping-683-redundancy-removed: all checks passed.")
