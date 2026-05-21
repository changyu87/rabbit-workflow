#!/usr/bin/env python3
"""RABBIT-CAGE-BUG-97 — natural-language regression pin (Inv 95).

Pins the natural-language → CLI mapping that motivated the BUG-97 revert
of the BACKLOG-31 rename:

  "turn off human approval"        → /rabbit-config human-approval false
                                     → .rabbit-human-approval-bypass WRITTEN
                                       (bypass ACTIVE)

  "turn on human approval"         → /rabbit-config human-approval true
  "re-enable approval"             → /rabbit-config human-approval true
                                     → .rabbit-human-approval-bypass REMOVED
                                       (gate ACTIVE)

This test is belt-and-suspenders against future re-rename attempts that
would re-introduce the natural-language misparse documented in Inv 91.
A failure here is a hard signal that the subcommand naming has drifted
away from the natural-language contract.

Per Inv 44: the test runs in an isolated tempdir; no live source file is
mutated. The subprocess invokes the live rabbit-config.py with `cwd=wd`
so the marker (a CWD-relative path inside rabbit-config.py) is created
inside the tempdir, not at the repo root.
"""
import os
import shutil
import subprocess
import sys
import tempfile

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = subprocess.run(
    ["git", "-C", SCRIPT_DIR, "rev-parse", "--show-toplevel"],
    capture_output=True, text=True, check=True,
).stdout.strip()

RABBIT_CONFIG_PY = os.path.join(
    REPO_ROOT,
    ".claude/features/rabbit-cage/skills/rabbit-config/scripts/rabbit-config.py",
)
MARKER = ".rabbit-human-approval-bypass"

pass_n = 0
fail_n = 0


def ok(t, msg):
    global pass_n
    print(f"  PASS t{t}: {msg}")
    pass_n += 1


def fail_t(t, msg):
    global fail_n
    print(f"  FAIL t{t}: {msg}")
    fail_n += 1


def run_cfg(args, wd):
    return subprocess.run(
        [sys.executable, RABBIT_CONFIG_PY] + list(args),
        cwd=wd, capture_output=True, text=True,
    )


print("test-RABBIT-CAGE-BUG-97-natural-language-mapping.py")
print('Inv 95: pin "turn off / on human approval" → human-approval false / true')
print()

# t1: "turn off human approval" → human-approval false → marker WRITTEN
wd = tempfile.mkdtemp(prefix="bug97-off-")
try:
    marker = os.path.join(wd, MARKER)
    # Sanity: marker absent at start.
    if os.path.isfile(marker):
        os.remove(marker)
    res = run_cfg(["human-approval", "false"], wd)
    if res.returncode == 0 and os.path.isfile(marker):
        with open(marker) as f:
            content = f.read()
        if content == "session":
            ok(1, '"turn off human approval" → human-approval false → marker WRITTEN with "session" (Inv 95)')
        else:
            fail_t(1, f"marker written with wrong content: {content!r}")
    else:
        fail_t(
            1,
            f"human-approval false did NOT write marker: "
            f"rc={res.returncode} marker_exists={os.path.isfile(marker)} "
            f"stdout={res.stdout!r} stderr={res.stderr!r}",
        )
finally:
    shutil.rmtree(wd, ignore_errors=True)

# t2: "turn on human approval" / "re-enable approval" → human-approval true →
# marker REMOVED. Start with the marker present (post-"turn off" state) so
# the assertion is meaningful (an absent marker remaining absent would
# trivially satisfy the post-condition).
wd = tempfile.mkdtemp(prefix="bug97-on-")
try:
    marker = os.path.join(wd, MARKER)
    with open(marker, "w") as f:
        f.write("session")
    res = run_cfg(["human-approval", "true"], wd)
    if res.returncode == 0 and not os.path.isfile(marker):
        ok(2, '"turn on human approval" → human-approval true → marker REMOVED (Inv 95)')
    else:
        fail_t(
            2,
            f"human-approval true did NOT remove marker: "
            f"rc={res.returncode} marker_exists={os.path.isfile(marker)} "
            f"stdout={res.stdout!r} stderr={res.stderr!r}",
        )
finally:
    shutil.rmtree(wd, ignore_errors=True)

# t3: round-trip. "turn off" then "turn on" should leave marker absent.
wd = tempfile.mkdtemp(prefix="bug97-roundtrip-")
try:
    marker = os.path.join(wd, MARKER)
    res_off = run_cfg(["human-approval", "false"], wd)
    after_off = os.path.isfile(marker)
    res_on = run_cfg(["human-approval", "true"], wd)
    after_on = os.path.isfile(marker)
    if (res_off.returncode == 0 and after_off
            and res_on.returncode == 0 and not after_on):
        ok(3, "round-trip turn off then turn on returns to gate-active state (marker absent)")
    else:
        fail_t(
            3,
            f"round-trip wrong: after_off={after_off} (expect True), "
            f"after_on={after_on} (expect False), "
            f"rc_off={res_off.returncode} rc_on={res_on.returncode}",
        )
finally:
    shutil.rmtree(wd, ignore_errors=True)

# t4: state query reports the right boolean per the restored convention.
# (Inv 37: 'is human approval in effect?' — true iff marker ABSENT.)
wd = tempfile.mkdtemp(prefix="bug97-query-")
try:
    marker = os.path.join(wd, MARKER)
    # No marker → gate ACTIVE → expect 'true'
    res_none = run_cfg(["human-approval"], wd)
    # Marker present → bypass ACTIVE → expect 'false'
    with open(marker, "w") as f:
        f.write("session")
    res_present = run_cfg(["human-approval"], wd)
    if (res_none.returncode == 0 and res_none.stdout.strip() == "true"
            and res_present.returncode == 0 and res_present.stdout.strip() == "false"):
        ok(4, "state-query convention: 'true' when gate active (marker absent), 'false' when bypass active (marker present)")
    else:
        fail_t(
            4,
            f"state query wrong: marker_absent_stdout={res_none.stdout!r} "
            f"(expect 'true'), marker_present_stdout={res_present.stdout!r} "
            f"(expect 'false')",
        )
finally:
    shutil.rmtree(wd, ignore_errors=True)

print()
print(f"Results: {pass_n} passed, {fail_n} failed")
sys.exit(0 if fail_n == 0 else 1)
