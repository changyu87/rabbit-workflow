#!/usr/bin/env python3
"""test-detect-scheduler.py — e2e tests for scripts/detect-scheduler.py
(Inv 34 / D2, issue #521).

`detect-scheduler.py` probes `crontab -l` via the `RABBIT_CRONTAB_CMD` env
override (so the real crontab is never touched) and emits JSON
`{"scheduler":"crontab"|"croncreate","reason":...}` on stdout, exit 0.

Scenarios:
  A) crontab usable (shim exits 0)                  -> scheduler == crontab
  B) legitimate empty "no crontab for user" (exit 1, NO permission denial)
                                                     -> scheduler == crontab
  C) restricted host ("not allowed", exit 1)        -> scheduler == croncreate
  D) --help smoke                                    -> exit 0
"""

import json
import os
import subprocess
import sys
import tempfile
import textwrap

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.normpath(os.path.join(HERE, "..", "scripts"))
DETECT = os.path.join(SCRIPTS, "detect-scheduler.py")

FAIL = 0


def fail(msg):
    global FAIL
    print(f"FAIL: {msg}", file=sys.stderr)
    FAIL = 1


def ok(msg):
    print(f"PASS: {msg}")


def make_shim(dirpath, body):
    shim = os.path.join(dirpath, "crontab")
    with open(shim, "w") as f:
        f.write(f"#!{sys.executable}\n" + textwrap.dedent(body))
    os.chmod(shim, 0o755)
    return shim


USABLE = """
    import sys
    if sys.argv[1:] == ["-l"]:
        sys.stdout.write("0 0 * * * /usr/bin/backup.sh\\n")
        sys.exit(0)
    sys.exit(0)
"""

EMPTY = """
    import sys
    sys.stderr.write("no crontab for testuser\\n")
    sys.exit(1)
"""

RESTRICTED = """
    import sys
    sys.stderr.write("You (testuser) are not allowed to use this program "
                     "(crontab)\\n")
    sys.exit(1)
"""


def run(shim):
    env = os.environ.copy()
    env["RABBIT_CRONTAB_CMD"] = shim
    return subprocess.run(
        [sys.executable, DETECT],
        capture_output=True, text=True, env=env,
    )


def parsed(proc):
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError:
        return None


# A — usable
with tempfile.TemporaryDirectory() as d:
    proc = run(make_shim(d, USABLE))
    j = parsed(proc)
    if proc.returncode == 0 and j and j.get("scheduler") == "crontab":
        ok("A: usable crontab -> scheduler == crontab")
    else:
        fail(f"A: expected crontab; rc={proc.returncode} out={proc.stdout!r} "
             f"err={proc.stderr!r}")

# B — legitimate empty
with tempfile.TemporaryDirectory() as d:
    proc = run(make_shim(d, EMPTY))
    j = parsed(proc)
    if proc.returncode == 0 and j and j.get("scheduler") == "crontab":
        ok("B: empty 'no crontab for user' -> scheduler == crontab")
    else:
        fail(f"B: expected crontab for empty case; rc={proc.returncode} "
             f"out={proc.stdout!r} err={proc.stderr!r}")

# C — restricted
with tempfile.TemporaryDirectory() as d:
    proc = run(make_shim(d, RESTRICTED))
    j = parsed(proc)
    if proc.returncode == 0 and j and j.get("scheduler") == "croncreate":
        ok("C: restricted host -> scheduler == croncreate")
    else:
        fail(f"C: expected croncreate; rc={proc.returncode} out={proc.stdout!r} "
             f"err={proc.stderr!r}")

# D — --help smoke
proc = subprocess.run(
    [sys.executable, DETECT, "--help"], capture_output=True, text=True,
)
if proc.returncode == 0 and "scheduler" in (proc.stdout + proc.stderr).lower():
    ok("D: --help exits 0 with recognizable usage")
else:
    fail(f"D: --help exit {proc.returncode}; out={proc.stdout!r}")

sys.exit(FAIL)
