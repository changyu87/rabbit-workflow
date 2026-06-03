#!/usr/bin/env python3
"""Inv 61 (issue #528) — large slot values must not blow the argv 128KB cap.

End-to-end regression: dispatch with a spec_content payload larger than
Linux's MAX_ARG_STRLEN (128 KB per single argv string). Before the fix the
dispatcher passed the whole spec via `--slot spec_content=<...>` argv, so the
subprocess call to build-prompt.py died with
`OSError: [Errno 7] Argument list too long`. After the fix the prompt
assembles cleanly and the large content is present verbatim in the output.
"""
import os
import tempfile

from _helpers import run_dispatch, report

passed = failed = 0


def ok(msg):
    global passed
    passed += 1
    print(f"  ok   {msg}")


def ko(msg):
    global failed
    failed += 1
    print(f"  FAIL {msg}")


# A unique, easily-greppable marker embedded in the oversized spec body so we
# can confirm the large content survives assembly without truncation.
MARKER = "ZZZ-LARGE-SLOT-MARKER-528-ZZZ"
# MAX_ARG_STRLEN is 128 KB. Build a spec comfortably over that as a single
# slot value (the full spec_content slot is one argv arg in the old code).
BIG_BODY = "Q" * (200 * 1024)
spec_text = (
    "# Oversized Spec (issue #528 regression)\n\n"
    f"{MARKER}\n\n"
    f"{BIG_BODY}\n\n"
    f"{MARKER}-END\n"
)

tmp = tempfile.NamedTemporaryFile(
    "w", suffix=".md", prefix="big-spec-", delete=False)
try:
    tmp.write(spec_text)
    tmp.close()
    res = run_dispatch(spec=tmp.name)

    # t-no-argv-error: the dispatch must NOT die with the argv-too-long OSError.
    if "Argument list too long" in (res.stderr or ""):
        ko("t-no-argv-error: dispatch hit 'Argument list too long' (argv cap)")
    else:
        ok("t-no-argv-error: no 'Argument list too long' in stderr")

    # t-rc-zero: dispatch succeeds.
    if res.returncode == 0:
        ok("t-rc-zero: dispatch returned 0 for >128KB spec_content")
    else:
        ko(f"t-rc-zero: dispatch returned {res.returncode}; "
           f"stderr tail: {(res.stderr or '')[-400:]!r}")

    prompt = res.stdout or ""

    # t-marker-present: the large content is present verbatim (not truncated).
    if MARKER in prompt and f"{MARKER}-END" in prompt:
        ok("t-marker-present: large spec markers present in assembled prompt")
    else:
        ko("t-marker-present: large spec markers missing from prompt "
           "(content lost or truncated)")

    # t-full-body-present: the bulk payload survives intact.
    if BIG_BODY in prompt:
        ok("t-full-body-present: full oversized body present verbatim")
    else:
        ko("t-full-body-present: oversized body not present verbatim")
finally:
    os.unlink(tmp.name)

report(passed, failed)
