#!/usr/bin/env python3
"""test-check-sentinel-dispatch-scope.py — Inv 17 (#1132).

check_sentinel's Inv 17 scope is DISPATCH/AGENT-PROMPT SCRIPTS ONLY — not every
.py file. A directory walk MUST require the policy-block sentinel only in files
that are dispatch scripts (those that wrap contract's build-prompt.py prompt
assembler, per Inv 56), and MUST NOT flag ordinary library or test source that
should not carry the sentinel.

End-to-end via both the library function and the CLI shim:

  - a plain lib/*.py with no sentinel and no dispatch marker is NOT flagged;
  - a dispatch script (references build-prompt) WITH the sentinel passes;
  - a dispatch script (references build-prompt) WITHOUT the sentinel IS flagged
    (positive enforcement preserved — the check is not neutered);
  - a single-file invocation of an explicit dispatch-script path retains
    current behavior (flagged when the sentinel is missing).
"""

import os
import sys
import subprocess
import tempfile

FEATURE_DIR = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, FEATURE_DIR)
from lib.checks import check_sentinel, CheckResult  # noqa: E402

SHIM = os.path.join(FEATURE_DIR, "scripts/enforcement/check-sentinel.py")
SENTINEL = "RABBIT-POLICY-BLOCK-v1"

FAIL = 0


def ok(t, msg):
    print(f"PASS {t}: {msg}")


def bad(t, msg):
    global FAIL
    print(f"FAIL {t}: {msg}", file=sys.stderr)
    FAIL = 1


def _write(path, body):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write(body)


# A realistic dispatch script body: wraps contract's build-prompt.py. Its
# source proof-of-dispatch is the build-prompt reference. For this fixture we
# toggle the sentinel presence to exercise both arms.
DISPATCH_BODY_WITH = (
    "#!/usr/bin/env python3\n"
    f"# {SENTINEL}\n"
    'BUILD_PROMPT = "../contract/scripts/build-prompt.py"\n'
    "print('dispatch')\n"
)
DISPATCH_BODY_WITHOUT = (
    "#!/usr/bin/env python3\n"
    'BUILD_PROMPT = "../contract/scripts/build-prompt.py"\n'
    "print('dispatch')\n"
)
PLAIN_LIB_BODY = (
    "#!/usr/bin/env python3\n"
    '"""notification_emitter — ordinary library; no sentinel expected."""\n'
    "def emit(x):\n    return x\n"
)
PLAIN_TEST_BODY = (
    "#!/usr/bin/env python3\n"
    "print('ordinary test/run.py — no sentinel expected')\n"
)


# t1: feature dir with a plain lib + a dispatch script WITH sentinel -> pass,
#     and the plain lib file is NOT named in any message.
with tempfile.TemporaryDirectory() as tmp:
    _write(os.path.join(tmp, "lib", "notification_emitter.py"), PLAIN_LIB_BODY)
    _write(os.path.join(tmp, "test", "run.py"), PLAIN_TEST_BODY)
    _write(os.path.join(tmp, "scripts", "dispatch-thing.py"), DISPATCH_BODY_WITH)
    res = check_sentinel(tmp)
    if (isinstance(res, CheckResult)
            and res.passed
            and not any("notification_emitter.py" in m for m in res.messages)
            and not any("run.py" in m for m in res.messages)):
        ok("t1", "plain lib/test not flagged; dispatch script with sentinel passes")
    else:
        bad("t1", f"unexpected result: {res!r}")

# t2: same tree but the dispatch script is MISSING the sentinel -> fail, and
#     ONLY the dispatch script is named (plain lib/test still not flagged).
with tempfile.TemporaryDirectory() as tmp:
    _write(os.path.join(tmp, "lib", "notification_emitter.py"), PLAIN_LIB_BODY)
    _write(os.path.join(tmp, "test", "run.py"), PLAIN_TEST_BODY)
    _write(os.path.join(tmp, "scripts", "dispatch-thing.py"), DISPATCH_BODY_WITHOUT)
    res = check_sentinel(tmp)
    if (not res.passed
            and any("dispatch-thing.py" in m for m in res.messages)
            and not any("notification_emitter.py" in m for m in res.messages)
            and not any("run.py" in m for m in res.messages)):
        ok("t2", "dispatch script missing sentinel IS flagged; plain files are not")
    else:
        bad("t2", f"unexpected result: {res!r}")

# t3: single-file invocation of an explicit dispatch-script path retains current
#     behavior — flagged when the sentinel is missing (callers passing an
#     explicit path are not regressed).
with tempfile.TemporaryDirectory() as tmp:
    p = os.path.join(tmp, "dispatch-thing.py")
    _write(p, DISPATCH_BODY_WITHOUT)
    res = check_sentinel(p)
    if not res.passed and any("dispatch-thing.py" in m for m in res.messages):
        ok("t3", "single-file dispatch-script path still flagged when missing sentinel")
    else:
        bad("t3", f"unexpected result: {res!r}")

# t4 (CLI shim, end-to-end): a feature dir whose only .py-without-sentinel is a
#     PLAIN lib file (no dispatch script) exits 0 — no false positive.
with tempfile.TemporaryDirectory() as tmp:
    _write(os.path.join(tmp, "lib", "plain.py"), PLAIN_LIB_BODY)
    proc = subprocess.run(["python3", SHIM, tmp], capture_output=True, text=True)
    if proc.returncode == 0:
        ok("t4", "CLI shim exits 0 on a dir of plain lib code (no dispatch script)")
    else:
        bad("t4", f"shim returned {proc.returncode}; stderr={proc.stderr!r}")

# t5 (CLI shim, end-to-end): a feature dir with a dispatch script missing the
#     sentinel exits 1 (enforcement preserved through the shim).
with tempfile.TemporaryDirectory() as tmp:
    _write(os.path.join(tmp, "lib", "plain.py"), PLAIN_LIB_BODY)
    _write(os.path.join(tmp, "scripts", "dispatch-x.py"), DISPATCH_BODY_WITHOUT)
    proc = subprocess.run(["python3", SHIM, tmp], capture_output=True, text=True)
    if proc.returncode == 1 and "dispatch-x.py" in proc.stderr:
        ok("t5", "CLI shim exits 1 when a dispatch script is missing the sentinel")
    else:
        bad("t5", f"shim rc={proc.returncode}; stderr={proc.stderr!r}")

if FAIL:
    print("test-check-sentinel-dispatch-scope: FAIL", file=sys.stderr)
    sys.exit(1)
print("test-check-sentinel-dispatch-scope: all checks passed.")
