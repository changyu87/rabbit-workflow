#!/usr/bin/env python3
"""test-mutation-run-feature-script.py — exercises run_feature_script: the
mutation API escape hatch. Invokes a feature-owned script (feature-dir-
relative path) with given args. Returns CheckResult based on exit code:
passed=True iff exit 0. Captures stdout/stderr into messages.
"""

import os
import sys
import stat
import tempfile

FEATURE_DIR = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, FEATURE_DIR)

from lib.mutation import run_feature_script  # noqa: E402

FAIL = 0


def fail(msg):
    global FAIL
    print(f"FAIL: {msg}", file=sys.stderr)
    FAIL = 1


def ok(msg):
    print(f"PASS: {msg}")


def write_script(feat, relpath, body):
    p = os.path.join(feat, relpath)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w") as f:
        f.write(body)
    os.chmod(p, os.stat(p).st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return p


# t1: successful exit-0 script
with tempfile.TemporaryDirectory() as feat:
    write_script(feat, "scripts/ok.py",
                 "#!/usr/bin/env python3\nimport sys\nprint('did the thing')\nsys.exit(0)\n")
    r = run_feature_script("scripts/ok.py", [], feature_dir=feat)
    if not r.passed:
        fail(f"t1: exit-0 script failed: {r.messages}")
    elif not any("did the thing" in m for m in r.messages):
        fail(f"t1: stdout not captured: {r.messages}")
    else:
        ok("t1: exit-0 script returns passed=True with stdout in messages")

# t2: exit-1 script → passed=False with stderr captured
with tempfile.TemporaryDirectory() as feat:
    write_script(feat, "scripts/bad.py",
                 "#!/usr/bin/env python3\nimport sys\nprint('oops', file=sys.stderr)\nsys.exit(1)\n")
    r = run_feature_script("scripts/bad.py", [], feature_dir=feat)
    if r.passed:
        fail("t2: exit-1 script should return passed=False")
    elif not any("oops" in m for m in r.messages):
        fail(f"t2: stderr not captured: {r.messages}")
    else:
        ok("t2: exit-1 script returns passed=False with stderr captured")

# t3: args forwarded
with tempfile.TemporaryDirectory() as feat:
    write_script(feat, "scripts/echo.py",
                 "#!/usr/bin/env python3\nimport sys\nprint(' '.join(sys.argv[1:]))\n")
    r = run_feature_script("scripts/echo.py", ["lock", "x"], feature_dir=feat)
    if not r.passed:
        fail(f"t3: echo failed: {r.messages}")
    elif not any("lock x" in m for m in r.messages):
        fail(f"t3: args not forwarded: {r.messages}")
    else:
        ok("t3: args forwarded to script")

# t4: missing script → passed=False with descriptive error (not raise)
with tempfile.TemporaryDirectory() as feat:
    r = run_feature_script("scripts/nope.py", [], feature_dir=feat)
    if r.passed:
        fail("t4: missing script should return passed=False")
    elif not any(
        s in " ".join(r.messages).lower()
        for s in ("not found", "missing", "no such")
    ):
        fail(f"t4: error should mention missing script: {r.messages}")
    else:
        ok("t4: missing script returns passed=False with descriptive error")

# t5: empty args list works (covers "no args" branch)
with tempfile.TemporaryDirectory() as feat:
    write_script(feat, "scripts/noargs.py",
                 "#!/usr/bin/env python3\nprint('hello')\n")
    r = run_feature_script("scripts/noargs.py", [], feature_dir=feat)
    if not r.passed:
        fail(f"t5: no-args invocation failed: {r.messages}")
    else:
        ok("t5: empty args list works")

if FAIL:
    print("test-mutation-run-feature-script: FAIL", file=sys.stderr)
    sys.exit(1)
print("test-mutation-run-feature-script: all checks passed.")
