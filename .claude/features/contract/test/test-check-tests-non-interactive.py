#!/usr/bin/env python3
# test-check-tests-non-interactive.py — assert check-tests-non-interactive.py
# scans Python test files (.py) with Python interactive constructs.
#
# Invariant 17: scanner must detect bare input(), getpass.getpass(),
# click.prompt(), click.confirm() in .py files under <feature-dir>/test/.
# Vacuous case (no test/ dir) exits 0.
#
# Non-interactive. Exits non-zero on failure.

import os
import sys
import shutil
import subprocess
import tempfile

FEATURE_DIR = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
SCRIPT = os.path.join(FEATURE_DIR, "scripts", "enforcement", "check-tests-non-interactive.py")
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


def run(feature_dir):
    return subprocess.run(
        ["python3", SCRIPT, feature_dir],
        capture_output=True,
        text=True,
    )


def make_feature(tmp, test_files):
    """Create a fake feature dir with given {filename: content} test files."""
    fdir = os.path.join(tmp, "fakefeature")
    tdir = os.path.join(fdir, "test")
    os.makedirs(tdir, exist_ok=True)
    for name, content in test_files.items():
        with open(os.path.join(tdir, name), "w") as f:
            f.write(content)
    return fdir


# t0: script exists and is executable
if not os.path.isfile(SCRIPT):
    fail("t0", f"script missing: {SCRIPT}")
    print(f"Results: {PASS} passed, {FAIL} failed")
    sys.exit(1)
ok("t0", "script exists")

# t1: vacuous — no test/ dir → exit 0
with tempfile.TemporaryDirectory() as tmp:
    fdir = os.path.join(tmp, "empty_feature")
    os.makedirs(fdir)
    r = run(fdir)
    if r.returncode == 0:
        ok("t1", "no test/ dir exits 0 (vacuous)")
    else:
        fail("t1", f"expected exit 0, got {r.returncode}; stderr={r.stderr}")

# t2: clean .py file → exit 0
with tempfile.TemporaryDirectory() as tmp:
    fdir = make_feature(tmp, {
        "test_clean.py": "import sys\nprint('hello')\nsys.exit(0)\n",
    })
    r = run(fdir)
    if r.returncode == 0:
        ok("t2", "clean .py test file exits 0")
    else:
        fail("t2", f"expected exit 0, got {r.returncode}; stderr={r.stderr}")

# t3: bare input() → exit 1, stderr names file and 'input'
with tempfile.TemporaryDirectory() as tmp:
    fdir = make_feature(tmp, {
        "test_input.py": "x = input('go? ')\nprint(x)\n",
    })
    r = run(fdir)
    if r.returncode == 1 and "test_input.py" in r.stderr and "input" in r.stderr:
        ok("t3", "bare input() detected (exit 1, file named)")
    else:
        fail("t3", f"expected exit 1 + filename + 'input' in stderr; got exit {r.returncode}; stderr={r.stderr}")

# t4: getpass.getpass() → exit 1
with tempfile.TemporaryDirectory() as tmp:
    fdir = make_feature(tmp, {
        "test_pw.py": "import getpass\npw = getpass.getpass('pw: ')\n",
    })
    r = run(fdir)
    if r.returncode == 1 and "test_pw.py" in r.stderr and "getpass" in r.stderr:
        ok("t4", "getpass.getpass() detected (exit 1, file named)")
    else:
        fail("t4", f"expected exit 1 + filename + 'getpass'; got exit {r.returncode}; stderr={r.stderr}")

# t5: click.prompt() → exit 1
with tempfile.TemporaryDirectory() as tmp:
    fdir = make_feature(tmp, {
        "test_cli.py": "import click\nv = click.prompt('name')\n",
    })
    r = run(fdir)
    if r.returncode == 1 and "test_cli.py" in r.stderr and "click.prompt" in r.stderr:
        ok("t5", "click.prompt() detected (exit 1, file named)")
    else:
        fail("t5", f"expected exit 1 + filename + 'click.prompt'; got exit {r.returncode}; stderr={r.stderr}")

# t6: click.confirm() → exit 1
with tempfile.TemporaryDirectory() as tmp:
    fdir = make_feature(tmp, {
        "test_confirm.py": "import click\nif click.confirm('ok?'):\n    pass\n",
    })
    r = run(fdir)
    if r.returncode == 1 and "test_confirm.py" in r.stderr and "click.confirm" in r.stderr:
        ok("t6", "click.confirm() detected (exit 1, file named)")
    else:
        fail("t6", f"expected exit 1 + filename + 'click.confirm'; got exit {r.returncode}; stderr={r.stderr}")

# t7: commented-out interactive call → exit 0 (comments stripped)
with tempfile.TemporaryDirectory() as tmp:
    fdir = make_feature(tmp, {
        "test_comment.py": "# x = input('ignored')\nprint('ok')\n",
    })
    r = run(fdir)
    if r.returncode == 0:
        ok("t7", "commented-out input() does not trigger violation")
    else:
        fail("t7", f"expected exit 0 (comment stripped), got {r.returncode}; stderr={r.stderr}")

# t8: identifier shadowing — 'my_input()' must NOT match bare input(
with tempfile.TemporaryDirectory() as tmp:
    fdir = make_feature(tmp, {
        "test_shadow.py": "def my_input():\n    return 42\nprint(my_input())\n",
    })
    r = run(fdir)
    if r.returncode == 0:
        ok("t8", "my_input() does not false-positive as input()")
    else:
        fail("t8", f"expected exit 0 (no bare input), got {r.returncode}; stderr={r.stderr}")

# t9: .sh files inside test/ are ignored (repo is Python-only)
with tempfile.TemporaryDirectory() as tmp:
    fdir = make_feature(tmp, {
        "test_clean.py": "print('ok')\n",
        "stray.sh": "read x\n",  # would have triggered old scanner
    })
    r = run(fdir)
    if r.returncode == 0:
        ok("t9", ".sh files in test/ are ignored (only .py is scanned)")
    else:
        fail("t9", f"expected exit 0 (.sh ignored), got {r.returncode}; stderr={r.stderr}")

print()
print(f"Results: {PASS} passed, {FAIL} failed")

if FAIL > 0:
    print("test-check-tests-non-interactive: FAIL", file=sys.stderr)
    sys.exit(1)

print("test-check-tests-non-interactive: all checks passed.")
