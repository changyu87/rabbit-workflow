#!/usr/bin/env python3
"""test-skill-structure.py — Inv 5 and 7.

  t5: Inv 5 — SKILL.md exists at skills/rabbit-config/SKILL.md with non-empty
      content that mentions 'rabbit-config'.
  t7: Inv 7 — rabbit-config.py interpreter exists at
      skills/rabbit-config/scripts/rabbit-config.py and begins with the
      Python3 shebang line.

  Inv 6 (description shape) is covered by test-skill-description.py.
"""

import os
import sys

FEATURE_DIR = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
SKILL_MD = os.path.join(FEATURE_DIR, "skills/rabbit-config/SKILL.md")
INTERPRETER = os.path.join(FEATURE_DIR, "skills/rabbit-config/scripts/rabbit-config.py")

FAIL = 0


def fail(n, msg):
    global FAIL
    print(f"FAIL t{n}: {msg}", file=sys.stderr)
    FAIL = 1


def ok(n, msg):
    print(f"ok t{n}: {msg}")


# t5: SKILL.md
if not os.path.isfile(SKILL_MD):
    fail(5, f"SKILL.md not found: {SKILL_MD}")
else:
    with open(SKILL_MD) as f:
        content = f.read()
    if len(content.strip()) < 20:
        fail(5, "SKILL.md is empty or nearly empty")
    elif "rabbit-config" not in content:
        fail(5, "SKILL.md does not mention 'rabbit-config'")
    else:
        ok(5, "SKILL.md exists and mentions rabbit-config")

# t7: interpreter
if not os.path.isfile(INTERPRETER):
    fail(7, f"interpreter not found: {INTERPRETER}")
else:
    with open(INTERPRETER) as f:
        first_line = f.readline().strip()
    if first_line != "#!/usr/bin/env python3":
        fail(7, f"interpreter first line must be '#!/usr/bin/env python3', got {first_line!r}")
    else:
        ok(7, "interpreter exists with correct shebang")

if FAIL:
    print("test-skill-structure: FAIL", file=sys.stderr)
    sys.exit(1)
print("test-skill-structure: all checks passed.")
