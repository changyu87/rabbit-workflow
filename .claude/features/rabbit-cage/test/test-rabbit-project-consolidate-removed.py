#!/usr/bin/env python3
"""test-rabbit-project-consolidate-removed.py

E2E regression: the `consolidate` subcommand and its helper script have
been removed from rabbit-project. The implementation suggestion for this
cycle states:

- Delete rabbit-project-consolidate.py entirely.
- Remove the consolidate branch from rabbit-project.py; init/set-path/map
  remain.
- Nothing under rabbit-cage should reference rabbit-project-consolidate.py
  after this change (commands doc, contract.md, scripts).

This test asserts the post-state directly by invoking the surviving
script and inspecting the surface artifacts.
"""

import os
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
CAGE = REPO / ".claude/features/rabbit-cage"
SCRIPTS = CAGE / "scripts"
RABBIT_PROJECT_PY = SCRIPTS / "rabbit-project.py"
CONSOLIDATE_PY = SCRIPTS / "rabbit-project-consolidate.py"
COMMANDS_MD = CAGE / "commands/rabbit-project.md"
CONTRACT_MD = CAGE / "docs/spec/contract.md"

pass_n = 0
fail_n = 0


def ok(t, msg):
    global pass_n
    print(f"  PASS t{t}: {msg}")
    pass_n += 1


def ko(t, msg):
    global fail_n
    print(f"  FAIL t{t}: {msg}")
    fail_n += 1


print("test-rabbit-project-consolidate-removed.py")

# t1: rabbit-project-consolidate.py does not exist
if not CONSOLIDATE_PY.exists():
    ok(1, "scripts/rabbit-project-consolidate.py does not exist")
else:
    ko(1, f"scripts/rabbit-project-consolidate.py still exists at {CONSOLIDATE_PY}")

# t2: rabbit-project.py source has no "consolidate" reference
src = RABBIT_PROJECT_PY.read_text()
if "consolidate" not in src:
    ok(2, "rabbit-project.py source contains no 'consolidate' reference")
else:
    ko(2, "rabbit-project.py source still contains 'consolidate' reference(s)")

# t3: invoking `rabbit-project.py consolidate <name>` returns nonzero
#     (unknown subcommand) with a usage hint on stderr
res = subprocess.run(
    [sys.executable, str(RABBIT_PROJECT_PY), "consolidate", "demo"],
    capture_output=True, text=True,
)
if res.returncode != 0 and "consolidate" not in res.stderr.lower().split("unknown subcommand")[0]:
    # The error message names the unknown subcommand ('consolidate') in the
    # `unknown subcommand 'consolidate'` line, but the printed usage that
    # follows MUST NOT mention consolidate as a supported verb.
    pass
if res.returncode != 0:
    # Usage block printed to stderr after the unknown-subcommand line MUST
    # NOT advertise consolidate.
    usage_lines = [l for l in res.stderr.splitlines() if l.strip().startswith("rabbit-project.py")]
    usage_blob = "\n".join(usage_lines)
    if "consolidate" not in usage_blob:
        ok(3, "rabbit-project.py rejects 'consolidate' (rc nonzero) and usage hint omits it")
    else:
        ko(3, f"rabbit-project.py usage still advertises consolidate: {usage_blob!r}")
else:
    ko(3, f"rabbit-project.py consolidate returned 0 (expected nonzero): stdout={res.stdout!r}")

# t4: surviving subcommands are still recognized by usage (init/set-path/map).
#     Invoke each with no args; expect rc 2 (bad invocation) and usage on stderr.
for sub in ("init", "set-path", "map"):
    r = subprocess.run(
        [sys.executable, str(RABBIT_PROJECT_PY), sub],
        capture_output=True, text=True,
    )
    if r.returncode == 2 and sub in r.stderr:
        ok(f"4.{sub}", f"'{sub}' subcommand recognized (rc=2, usage names it)")
    else:
        ko(f"4.{sub}", f"'{sub}' subcommand check failed: rc={r.returncode} stderr={r.stderr!r}")

# t5: commands/rabbit-project.md does not mention consolidate
cmd_doc = COMMANDS_MD.read_text()
if "consolidate" not in cmd_doc:
    ok(5, "commands/rabbit-project.md does not mention consolidate")
else:
    ko(5, "commands/rabbit-project.md still mentions consolidate")

# t6: docs/spec/contract.md does not list rabbit-project-consolidate.py
contract_text = CONTRACT_MD.read_text()
if "rabbit-project-consolidate" not in contract_text:
    ok(6, "contract.md does not reference rabbit-project-consolidate")
else:
    ko(6, "contract.md still references rabbit-project-consolidate")

print()
print(f"Results: {pass_n} passed, {fail_n} failed")
sys.exit(0 if fail_n == 0 else 1)
