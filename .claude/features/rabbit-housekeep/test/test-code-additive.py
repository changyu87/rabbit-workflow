#!/usr/bin/env python3
"""test-code-additive.py — gate for issue #1207: --code is additive (docs AND
code), not mutually exclusive with docs.

The fix in v0.10.0 removes the mutual exclusivity surprise: when --code is
passed, the SKILL runs BOTH the doc dimension AND the code dimension (additive),
not docs OR code. --docs-only remains the escape hatch for cheap doc-only waves.
The default (no flag) stays doc-only.

Coverage:

  t0: SKILL.md must NOT describe --code as operating "instead of" or as
      replacing the doc dimension (the old mutually-exclusive framing in the
      Inputs section: "the wave operates on the feature's src/ source, measured
      with count --code" implied docs OR code).

  t1: SKILL.md must document --docs-only as the escape hatch for doc-only waves.

  t2: command.md (rabbit-housekeep.md) must NOT contain "instead of slimming
      doc surfaces" for the --code flag description.

  t3: command.md must document --docs-only as an opt-in doc-only mode.

  t4: SKILL.md must contain a signal that --code is additive (BOTH doc AND
      code dimensions), not replacing.

Non-interactive. Exits non-zero on failure.

Version: 0.1.0
Owner: rabbit-workflow team
Deprecation criterion: when rabbit-housekeep is retired.
"""
import os
import sys

TEST_DIR = os.path.dirname(os.path.abspath(__file__))
FEATURE_DIR = os.path.normpath(os.path.join(TEST_DIR, ".."))
SKILL = os.path.join(FEATURE_DIR, "skills", "rabbit-housekeep", "SKILL.md")
COMMAND = os.path.join(FEATURE_DIR, "commands", "rabbit-housekeep.md")

PASS = 0
FAIL = 0


def ok(name, msg):
    global PASS
    print(f"  PASS {name}: {msg}")
    PASS += 1


def fail(name, msg):
    global FAIL
    print(f"  FAIL {name}: {msg}", file=sys.stderr)
    FAIL += 1


with open(SKILL, encoding="utf-8") as f:
    skill_text = f.read()

with open(COMMAND, encoding="utf-8") as f:
    command_text = f.read()

# t0: SKILL.md Inputs section must NOT describe --code as operating exclusively
# on src/ (the old mutually-exclusive framing). The old text was (across lines):
#   `--code` → the OPT-IN CODE dimension (below): the wave operates on the
#   feature's `src/` source, measured with `count --code`.
# After the fix, --code is additive: it runs BOTH doc AND code dimensions.
# The Inputs bullet for --code must reflect the additive semantics.
# Check for the distinctive tail of the old exclusive bullet (single line):
old_exclusive_tail = "feature's `src/` source, measured with `count --code`."
if old_exclusive_tail in skill_text:
    fail("t0", "SKILL.md Inputs section still contains the mutually-exclusive "
               "--code framing — update to additive semantics")
else:
    ok("t0", "SKILL.md Inputs section does not contain the old mutually-exclusive "
             "--code framing")

# t1: SKILL.md must document --docs-only as an escape hatch for doc-only waves.
if "--docs-only" not in skill_text:
    fail("t1", "SKILL.md does not mention --docs-only as the doc-only escape hatch")
else:
    ok("t1", "SKILL.md mentions --docs-only")

# t2: command.md --code description must NOT say "instead of" doc surfaces.
old_command_phrase = "instead of slimming doc surfaces"
if old_command_phrase in command_text:
    fail("t2", f"command.md still contains the mutually-exclusive framing: "
               f"{old_command_phrase!r}")
else:
    ok("t2", "command.md does not contain the old mutually-exclusive --code framing")

# t3: command.md must document --docs-only as an opt-in doc-only mode.
if "--docs-only" not in command_text:
    fail("t3", "command.md does not document --docs-only as the doc-only mode")
else:
    ok("t3", "command.md documents --docs-only")

# t4: SKILL.md Inputs section must carry a signal that --code is additive
# (runs BOTH doc AND code dimensions). The additive semantics should be
# expressed near the --code Inputs bullet. We check for a phrase combining
# --code with "additive" or "BOTH" or "doc" context.
# Accepted signals: "docs AND code", "BOTH doc", "additive", "in addition to doc"
additive_signals = [
    "docs AND code",
    "BOTH doc",
    "additive",
    "in addition to doc",
    "doc dimension AND the code",
    "doc AND code",
]
found_additive = any(sig in skill_text for sig in additive_signals)
if not found_additive:
    fail("t4", "SKILL.md does not document additive --code semantics in the "
               "Inputs section (look for 'docs AND code', 'BOTH doc', "
               "'additive', or 'in addition to doc')")
else:
    ok("t4", "SKILL.md documents additive --code semantics")

print()
print(f"Results: {PASS} passed, {FAIL} failed")
sys.exit(0 if FAIL == 0 else 1)
