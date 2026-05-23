#!/usr/bin/env python3
"""Inv 23, 24 — bypass-marker preamble note: marker-gated, emitted via
dispatch_bypass_note() wrapper, no inline ANSI/brand strings in the
dispatch script."""
import os
import sys

from _helpers import (
    CONTRACT_SCRIPTS,
    DISPATCH_PY,
    REPO_ROOT,
    run_dispatch,
    report,
)

passed = failed = 0


def ok(msg):
    global passed
    passed += 1
    print(f"  ok   {msg}")


def ko(msg):
    global failed
    failed += 1
    print(f"  FAIL {msg}")


sys.path.insert(0, CONTRACT_SCRIPTS)
from rabbit_print import dispatch_bypass_note  # noqa: E402

expected_note = dispatch_bypass_note()

MARKER = os.path.join(REPO_ROOT, ".rabbit-human-approval-bypass")
marker_existed = os.path.isfile(MARKER)
marker_backup = None
if marker_existed:
    with open(MARKER) as f:
        marker_backup = f.read()
    os.unlink(MARKER)

try:
    # Inv 23: marker absent → no note.
    res_absent = run_dispatch()
    if res_absent.returncode != 0:
        ko(f"dispatch failed (marker absent) rc={res_absent.returncode}: {res_absent.stderr}")
        report(passed, failed)
    if expected_note not in res_absent.stdout:
        ok("inv23: marker absent — bypass note absent from prompt")
    else:
        ko("inv23: bypass note appears even when marker is absent")

    # Inv 23: marker present → note appears in preamble.
    with open(MARKER, "w") as f:
        f.write("")
    res_present = run_dispatch()
    if res_present.returncode != 0:
        ko(f"dispatch failed (marker present) rc={res_present.returncode}: {res_present.stderr}")
    elif expected_note in res_present.stdout:
        idx_note = res_present.stdout.find(expected_note)
        idx_step1 = res_present.stdout.find("STEP 1 — SPEC-READ")
        if 0 <= idx_note < idx_step1:
            ok("inv23: marker present — bypass note in preamble (before STEP 1)")
        else:
            ko("inv23: bypass note present but not in preamble")
    else:
        ko("inv23: bypass note missing when marker is present")
finally:
    # Restore original state — never mutate the user's marker.
    if os.path.isfile(MARKER):
        os.unlink(MARKER)
    if marker_existed:
        with open(MARKER, "w") as f:
            f.write(marker_backup or "")

# Inv 24: dispatch script has no inline ANSI escape codes or brand strings.
with open(DISPATCH_PY) as f:
    src = f.read()
# ANSI escape sequence \x1b or \033 anywhere in source code
if "\\x1b" not in src and "\\033" not in src:
    ok("inv24: dispatch script contains no inline ANSI escape literals")
else:
    ko("inv24: dispatch script contains inline ANSI escape literals")
# Brand string forms.
if "[🐇 rabbit 🐇]" not in src and "[rabbit]" not in src.replace("dispatch-bypass-note", ""):
    ok("inv24: dispatch script contains no inline brand strings")
else:
    ko("inv24: dispatch script contains an inline brand string")

report(passed, failed)
