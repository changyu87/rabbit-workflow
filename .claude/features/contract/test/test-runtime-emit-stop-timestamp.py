#!/usr/bin/env python3
"""test-runtime-emit-stop-timestamp.py — exercises emit_stop_timestamp per
Inv 57. Always returns a list of length 1 with a print_result entry whose
text is the current LOCAL HH:MM:SS plus a tz label, icon is ⏱, color is
green. NEVER short-circuits to []. Issue #847: the ⏱ clock must render in
LOCAL wall-clock (not UTC) so it agrees with the idle Stop-line next-tick
ETA and the SessionStart banner ETA (both local) and the local-time
heartbeat cron.
"""

import datetime
import json
import os
import re
import sys
import tempfile

FEATURE_DIR = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, FEATURE_DIR)

from lib.runtime import emit_auto_evolve_stop_line, emit_stop_timestamp  # noqa: E402

FAIL = 0


def fail(msg):
    global FAIL
    print(f"FAIL: {msg}", file=sys.stderr)
    FAIL = 1


def ok(msg):
    print(f"PASS: {msg}")


# HH:MM:SS followed by a space and a non-empty tz label (e.g. "03:32:07 EDT").
HHMMSS_TZ_RE = re.compile(r"^[0-2][0-9]:[0-5][0-9]:[0-5][0-9] [A-Za-z0-9+\-]+$")


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

# (vi) text matches HH:MM:SS + tz-label regex
if entry is None:
    fail("vi: no entry to inspect")
else:
    text = entry.get("text", "")
    if not HHMMSS_TZ_RE.match(text):
        fail(f"vi: text must match '^HH:MM:SS TZ$', got {text!r}")
    else:
        ok(f"vi: text matches 'HH:MM:SS TZ' pattern ({text!r})")

# (vii) two successive calls produce two valid timestamp strings (proves
# time is read each call, not cached at import).
with tempfile.TemporaryDirectory() as td:
    r1 = emit_stop_timestamp(repo_root=td)
    r2 = emit_stop_timestamp(repo_root=td)
    t1 = r1[0]["text"] if isinstance(r1, list) and r1 else None
    t2 = r2[0]["text"] if isinstance(r2, list) and r2 else None
    if not t1 or not HHMMSS_TZ_RE.match(t1):
        fail(f"vii: first call text invalid: {t1!r}")
    elif not t2 or not HHMMSS_TZ_RE.match(t2):
        fail(f"vii: second call text invalid: {t2!r}")
    else:
        ok(f"vii: two successive calls both valid 'HH:MM:SS TZ' ({t1!r}, {t2!r})")

# (viii) the single entry carries order == "footer" (footer-ordering marker
# per Inv 57).
if entry is None:
    fail("viii: no entry to inspect")
elif entry.get("order") != "footer":
    fail(f"viii: order must be 'footer', got {entry.get('order')!r}")
else:
    ok("viii: entry order is 'footer'")

# (ix) with an INJECTED fixed aware `now`, the rendered HH:MM:SS reflects the
# injected LOCAL wall-clock, not its UTC equivalent — proving the clock is
# local (issue #847). Pin an aware `now` in a +05:00 zone whose local
# HH:MM:SS differs from its UTC HH:MM:SS, and assert the LOCAL form renders.
with tempfile.TemporaryDirectory() as td:
    tz = datetime.timezone(datetime.timedelta(hours=5), name="TZ5")
    now = datetime.datetime(2026, 6, 4, 14, 32, 7, tzinfo=tz)  # local 14:32:07, UTC 09:32:07
    r = emit_stop_timestamp(repo_root=td, now=now)
    text = r[0]["text"] if isinstance(r, list) and r else ""
    if not HHMMSS_TZ_RE.match(text):
        fail(f"ix: injected-now text must match 'HH:MM:SS TZ', got {text!r}")
    elif not text.startswith("14:32:07 "):
        fail(
            "ix: injected-now must render LOCAL 14:32:07 (not UTC 09:32:07); "
            f"got {text!r}"
        )
    elif "09:32:07" in text:
        fail(f"ix: rendered the UTC clock instead of local; got {text!r}")
    else:
        ok(f"ix: injected aware now renders LOCAL wall-clock ({text!r})")

# (x) END-TO-END composite-consistency check (issue #847 core). With a single
# fixed aware `now` and a written heartbeat cadence, the idle Stop-line ETA
# (emit_auto_evolve_stop_line) and the ⏱ clock (emit_stop_timestamp) must
# both derive from the SAME injected LOCAL now — the ⏱ HH:MM equals now's
# local HH:MM, and the ETA ~HH:MM is at/after now's local HH:MM. Before the
# fix the clock was UTC and the two lines disagreed by the tz offset.
with tempfile.TemporaryDirectory() as td:
    os.makedirs(os.path.join(td, ".claude"))
    with open(os.path.join(td, ".claude", "scheduled_tasks.json"), "w") as f:
        json.dump(
            {"tasks": [{"prompt": "rabbit-auto-evolve tick", "cron": "13,43 * * * *"}]},
            f,
        )
    # auto-evolve active + state file present + no short-lived markers => idle line.
    open(os.path.join(td, ".rabbit-auto-evolve-active"), "w").close()
    os.makedirs(os.path.join(td, ".rabbit"))
    with open(os.path.join(td, ".rabbit", "auto-evolve-state.json"), "w") as f:
        json.dump({"started": True}, f)

    tz = datetime.timezone(datetime.timedelta(hours=-4), name="EDT")
    now = datetime.datetime(2026, 6, 4, 3, 13, 5, tzinfo=tz)  # local 03:13, next fire 03:13

    stop_lines = emit_auto_evolve_stop_line(repo_root=td, now=now)
    ts_lines = emit_stop_timestamp(repo_root=td, now=now)
    idle_text = stop_lines[0]["text"] if stop_lines else ""
    clock_text = ts_lines[0]["text"] if ts_lines else ""

    m_eta = re.search(r"~(\d{2}):(\d{2})", idle_text)
    m_clk = re.match(r"^(\d{2}):(\d{2}):\d{2} ", clock_text)
    if "next tick" not in idle_text or m_eta is None:
        fail(f"x: idle line missing a ~HH:MM ETA; got {idle_text!r}")
    elif m_clk is None:
        fail(f"x: clock line not 'HH:MM:SS TZ'; got {clock_text!r}")
    else:
        eta_min = int(m_eta.group(1)) * 60 + int(m_eta.group(2))
        clk_min = int(m_clk.group(1)) * 60 + int(m_clk.group(2))
        now_min = now.hour * 60 + now.minute
        if clk_min != now_min:
            fail(
                "x: ⏱ clock must equal injected LOCAL now HH:MM "
                f"({now.strftime('%H:%M')}); got clock {clock_text!r}"
            )
        # ETA must be at/after now (same hour here: 03:13 fire >= 03:13 now).
        elif eta_min < now_min:
            fail(
                "x: ETA must be at/after injected LOCAL now; "
                f"eta={idle_text!r} now={now.strftime('%H:%M')} — UTC/local mismatch?"
            )
        else:
            ok(
                "x: idle ETA and ⏱ clock both derive from the same injected "
                f"LOCAL now (eta {m_eta.group(0)}, clock {m_clk.group(1)}:{m_clk.group(2)})"
            )

if FAIL:
    print("test-runtime-emit-stop-timestamp: FAIL", file=sys.stderr)
    sys.exit(1)
print("test-runtime-emit-stop-timestamp: all checks passed.")
