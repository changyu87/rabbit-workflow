#!/usr/bin/env python3
"""test-runtime-emit-stop-timestamp.py — exercises emit_stop_timestamp per
Inv 67. Always returns a list of length 1 with a print_result entry whose
text is the current UTC HH:MM:SS, icon is ⏱, color is green. NEVER short-
circuits to [].
"""

import os
import re
import sys
import tempfile

FEATURE_DIR = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, FEATURE_DIR)

from lib.runtime import emit_stop_timestamp  # noqa: E402

FAIL = 0


def fail(msg):
    global FAIL
    print(f"FAIL: {msg}", file=sys.stderr)
    FAIL = 1


def ok(msg):
    print(f"PASS: {msg}")


HHMMSS_RE = re.compile(r"^[0-2][0-9]:[0-5][0-9]:[0-5][0-9]$")


# (i) function exists and is callable with repo_root=<any>
with tempfile.TemporaryDirectory() as td:
    try:
        r = emit_stop_timestamp(repo_root=td)
        ok("i: emit_stop_timestamp callable with repo_root kwarg")
    except Exception as e:  # noqa: BLE001
        fail(f"i: emit_stop_timestamp raised: {e!r}")
        r = None

# (ii) returns a list of length 1
if not isinstance(r, list):
    fail(f"ii: expected list, got {type(r).__name__}")
elif len(r) != 1:
    fail(f"ii: expected length 1, got {len(r)}: {r!r}")
else:
    ok("ii: returns list of length 1")

entry = r[0] if isinstance(r, list) and len(r) == 1 else None

# (iii) the single entry's type == "print"
if entry is None:
    fail("iii: no entry to inspect")
elif entry.get("type") != "print":
    fail(f"iii: type must be 'print', got {entry.get('type')!r}")
else:
    ok("iii: entry type is 'print'")

# (iv) icon == "⏱"
if entry is None:
    fail("iv: no entry to inspect")
elif entry.get("icon") != "⏱":
    fail(f"iv: icon must be '⏱', got {entry.get('icon')!r}")
else:
    ok("iv: icon is ⏱")

# (v) color == "green"
if entry is None:
    fail("v: no entry to inspect")
elif entry.get("color") != "green":
    fail(f"v: color must be 'green', got {entry.get('color')!r}")
else:
    ok("v: color is green")

# (vi) text matches HH:MM:SS regex
if entry is None:
    fail("vi: no entry to inspect")
else:
    text = entry.get("text", "")
    if not HHMMSS_RE.match(text):
        fail(f"vi: text must match ^[0-2][0-9]:[0-5][0-9]:[0-5][0-9]$, got {text!r}")
    else:
        ok(f"vi: text matches HH:MM:SS pattern ({text!r})")

# (vii) two successive calls produce two valid HH:MM:SS strings (proves
# time is read each call, not cached at import).
with tempfile.TemporaryDirectory() as td:
    r1 = emit_stop_timestamp(repo_root=td)
    r2 = emit_stop_timestamp(repo_root=td)
    t1 = r1[0]["text"] if isinstance(r1, list) and r1 else None
    t2 = r2[0]["text"] if isinstance(r2, list) and r2 else None
    if not t1 or not HHMMSS_RE.match(t1):
        fail(f"vii: first call text invalid: {t1!r}")
    elif not t2 or not HHMMSS_RE.match(t2):
        fail(f"vii: second call text invalid: {t2!r}")
    else:
        ok(f"vii: two successive calls both valid HH:MM:SS ({t1!r}, {t2!r})")

# (viii) the single entry carries order == "footer" (footer-ordering marker
# per issue #413 / Inv 67).
if entry is None:
    fail("viii: no entry to inspect")
elif entry.get("order") != "footer":
    fail(f"viii: order must be 'footer', got {entry.get('order')!r}")
else:
    ok("viii: entry order is 'footer'")

if FAIL:
    print("test-runtime-emit-stop-timestamp: FAIL", file=sys.stderr)
    sys.exit(1)
print("test-runtime-emit-stop-timestamp: all checks passed.")
