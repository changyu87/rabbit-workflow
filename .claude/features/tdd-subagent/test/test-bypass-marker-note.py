#!/usr/bin/env python3
"""Inv 23, 24 — bypass-marker preamble note: dual-read marker-gated
(.rabbit-human-approval-bypass OR .rabbit-tdd-autonomous), emitted via
rabbit_print(text, icon, color), no inline ANSI/brand strings in the
dispatch script.

Issue #336 Phase 1: dispatch-tdd-subagent.py treats the bypass as active
when EITHER marker name exists at the repo root (dual-read coexistence
window). The note body names BOTH markers."""
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
from rabbit_print import rabbit_print  # noqa: E402

# Canonical preamble text — must match dispatch-tdd-subagent.py _BYPASS_NOTE_TEXT.
# The note now names BOTH dual-read markers (issue #336 Phase 1) and still
# references the DISPATCHER's Step 4 (not any subagent step) because the
# subagent's prompt no longer contains a HUMAN-APPROVAL step at all
# (TDD-SUBAGENT-BACKLOG-19).
_EXPECTED_TEXT = (
    "NOTE: human-approval bypass marker is active "
    "(.rabbit-human-approval-bypass or .rabbit-tdd-autonomous). The "
    "dispatcher's Step 4 HUMAN-APPROVAL gate was skipped for this "
    "dispatch. Revoke via `/rabbit-config human-approval true`."
)
expected_note = rabbit_print(_EXPECTED_TEXT, "📢", "yellow")

LEGACY_MARKER = os.path.join(REPO_ROOT, ".rabbit-human-approval-bypass")
AUTONOMOUS_MARKER = os.path.join(REPO_ROOT, ".rabbit-tdd-autonomous")


def _backup(path):
    """Return existing contents (or None) and remove the file so each case
    starts from a known-absent baseline. Never lose the user's live state."""
    if os.path.isfile(path):
        with open(path) as f:
            data = f.read()
        os.unlink(path)
        return data
    return None


def _restore(path, data):
    if os.path.isfile(path):
        os.unlink(path)
    if data is not None:
        with open(path, "w") as f:
            f.write(data)


legacy_backup = _backup(LEGACY_MARKER)
autonomous_backup = _backup(AUTONOMOUS_MARKER)


def _assert_note_in_preamble(res, label):
    """Assert the bypass note appears before STEP 1 — LOCK in the prompt."""
    if res.returncode != 0:
        ko(f"{label}: dispatch failed rc={res.returncode}: {res.stderr}")
        return
    if expected_note not in res.stdout:
        ko(f"{label}: bypass note missing when marker is present")
        return
    idx_note = res.stdout.find(expected_note)
    idx_step1 = res.stdout.find("STEP 1 — LOCK")
    if 0 <= idx_note < idx_step1:
        ok(f"{label}: bypass note in preamble (before STEP 1 — LOCK)")
    else:
        ko(f"{label}: bypass note present but not in preamble")


try:
    # Case 1 (Inv 23): neither marker → no note.
    res_absent = run_dispatch()
    if res_absent.returncode != 0:
        ko(f"dispatch failed (markers absent) rc={res_absent.returncode}: {res_absent.stderr}")
        report(passed, failed)
    if expected_note not in res_absent.stdout:
        ok("inv23: neither marker — bypass note absent from prompt")
    else:
        ko("inv23: bypass note appears even when neither marker is present")

    # Case 2 (Inv 23, live state): legacy .rabbit-human-approval-bypass
    # present → note appears in preamble.
    with open(LEGACY_MARKER, "w") as f:
        f.write("")
    _assert_note_in_preamble(
        run_dispatch(), "inv23: legacy .rabbit-human-approval-bypass present")
    os.unlink(LEGACY_MARKER)

    # Case 3 (Inv 23, future state): .rabbit-tdd-autonomous present (and
    # legacy absent) → note also appears in preamble (dual-read, #336 P1).
    with open(AUTONOMOUS_MARKER, "w") as f:
        f.write("")
    _assert_note_in_preamble(
        run_dispatch(), "inv23: .rabbit-tdd-autonomous present")
    os.unlink(AUTONOMOUS_MARKER)
finally:
    # Restore original state — never mutate the user's markers.
    _restore(LEGACY_MARKER, legacy_backup)
    _restore(AUTONOMOUS_MARKER, autonomous_backup)

# Inv 24: dispatch script has no inline ANSI escape codes or brand strings.
with open(DISPATCH_PY) as f:
    src = f.read()
# ANSI escape sequence \x1b or \033 anywhere in source code
if "\\x1b" not in src and "\\033" not in src:
    ok("inv24: dispatch script contains no inline ANSI escape literals")
else:
    ko("inv24: dispatch script contains inline ANSI escape literals")
# Brand string forms.
if "[🐇 rabbit 🐇]" not in src and "[rabbit]" not in src:
    ok("inv24: dispatch script contains no inline brand strings")
else:
    ko("inv24: dispatch script contains an inline brand string")

report(passed, failed)
