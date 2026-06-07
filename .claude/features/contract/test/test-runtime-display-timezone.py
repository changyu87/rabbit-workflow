#!/usr/bin/env python3
"""test-runtime-display-timezone.py — exercises the display-timezone
resolver and zone-labelled human-facing rendering per contract Inv 67.

resolve_display_tz(repo_root) reads the `display-timezone` configurable
via the generic per-feature config path and returns a datetime.tzinfo:
  - no configurable declared / empty value -> the system local zone;
  - "UTC" -> datetime.timezone.utc;
  - any other value -> the named IANA zone via zoneinfo.ZoneInfo ONLY when
    zoneinfo is importable, else GRACEFUL fallback to local (never raises;
    the runtime is Python 3.7 with no stdlib zoneinfo).

emit_stop_timestamp (Inv 57) and the next-tick ETA renderers
_auto_evolve_next_tick_eta / emit_auto_evolve_stop_line (Inv 55) render
HH:MM[:SS] %Z converted into the resolved display zone — the ETA is no
longer a bare HH:MM.

Machine artifacts (state JSON, JSON-lines logs) stay UTC and are NOT a
concern of this test; this is a DISPLAY-layer check only.
"""

import datetime
import importlib.util
import json
import os
import re
import sys
import tempfile

FEATURE_DIR = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, FEATURE_DIR)

from lib.runtime import (  # noqa: E402
    resolve_display_tz,
    emit_stop_timestamp,
    emit_auto_evolve_stop_line,
    _auto_evolve_next_tick_eta,
)

FAIL = 0


def fail(msg):
    global FAIL
    print(f"FAIL: {msg}", file=sys.stderr)
    FAIL = 1


def ok(msg):
    print(f"PASS: {msg}")


# A non-empty tz label suffix: "… EDT", "… UTC", "… +05" etc.
ZONE_LABEL_RE = re.compile(r" [A-Za-z0-9+\-]+$")

LOCAL_TZ = datetime.datetime.now().astimezone().tzinfo
ZONEINFO_AVAILABLE = importlib.util.find_spec("zoneinfo") is not None


def write_display_tz_feature(repo_root, value):
    """Scaffold a feature declaring a `display-timezone` json-key configurable
    whose current stored value is `value`, so resolve_display_tz reads it via
    the generic per-feature config path."""
    feat_dir = os.path.join(repo_root, ".claude", "features", "rabbit-cage")
    os.makedirs(feat_dir, exist_ok=True)
    cfg = {
        "id": "display-timezone",
        "subcommand": "display-timezone",
        "default": "local",
        "storage": {
            "type": "json-key",
            "file": ".rabbit/display-config.json",
            "key": "display_timezone",
        },
        "values": {},
    }
    with open(os.path.join(feat_dir, "feature.json"), "w") as f:
        json.dump({"name": "rabbit-cage", "configuration": [cfg]}, f)
    rabbit_dir = os.path.join(repo_root, ".rabbit")
    os.makedirs(rabbit_dir, exist_ok=True)
    with open(os.path.join(rabbit_dir, "display-config.json"), "w") as f:
        json.dump({"display_timezone": value}, f)


# (i) no display-timezone configurable declared -> local zone
with tempfile.TemporaryDirectory() as td:
    os.makedirs(os.path.join(td, ".claude", "features"))
    tz = resolve_display_tz(td)
    now = datetime.datetime(2026, 6, 4, 14, 32, 7, tzinfo=datetime.timezone.utc)
    local_label = now.astimezone(LOCAL_TZ).strftime("%Z")
    got_label = now.astimezone(tz).strftime("%Z")
    if got_label == local_label:
        ok(f"i: no configurable -> local zone (label {got_label!r})")
    else:
        fail(f"i: expected local zone label {local_label!r}, got {got_label!r}")

# (ii) value UTC -> datetime.timezone.utc
with tempfile.TemporaryDirectory() as td:
    write_display_tz_feature(td, "UTC")
    tz = resolve_display_tz(td)
    if tz == datetime.timezone.utc:
        ok("ii: value 'UTC' -> datetime.timezone.utc")
    else:
        fail(f"ii: expected datetime.timezone.utc, got {tz!r}")

# (iii) named-zone value -> that zone when zoneinfo importable, else local
#       WITHOUT raising.
with tempfile.TemporaryDirectory() as td:
    write_display_tz_feature(td, "America/Los_Angeles")
    try:
        tz = resolve_display_tz(td)
    except Exception as e:  # noqa: BLE001
        fail(f"iii: resolver raised on named zone: {e!r}")
        tz = None
    if tz is not None:
        if ZONEINFO_AVAILABLE:
            import zoneinfo  # noqa: PLC0415
            if tz == zoneinfo.ZoneInfo("America/Los_Angeles"):
                ok("iii: named zone resolved via zoneinfo")
            else:
                fail(f"iii: expected ZoneInfo('America/Los_Angeles'), got {tz!r}")
        else:
            # py3.7 — no zoneinfo: must degrade to local, never raise.
            now = datetime.datetime(2026, 6, 4, 14, 0, tzinfo=datetime.timezone.utc)
            if now.astimezone(tz).strftime("%Z") == now.astimezone(LOCAL_TZ).strftime("%Z"):
                ok("iii: named zone degrades to local (no zoneinfo) without raising")
            else:
                fail(f"iii: named zone should degrade to local; got {tz!r}")

# (iii-b) an invalid named zone never raises (graceful fallback to local).
with tempfile.TemporaryDirectory() as td:
    write_display_tz_feature(td, "Not/A_Real_Zone_Xyz")
    try:
        tz = resolve_display_tz(td)
        ok("iii-b: invalid named zone resolves without raising")
    except Exception as e:  # noqa: BLE001
        fail(f"iii-b: invalid named zone raised: {e!r}")

# (iv) injected fixed aware now + display zone UTC: emit_stop_timestamp and
#      _auto_evolve_next_tick_eta render the time CONVERTED to UTC and SUFFIXED
#      with a non-empty zone label.
with tempfile.TemporaryDirectory() as td:
    write_display_tz_feature(td, "UTC")
    # heartbeat cadence for the ETA
    os.makedirs(os.path.join(td, ".claude"), exist_ok=True)
    with open(os.path.join(td, ".claude", "scheduled_tasks.json"), "w") as f:
        json.dump(
            {"tasks": [{"prompt": "/rabbit-auto-evolve tick", "cron": "13,43 * * * *"}]},
            f,
        )
    # aware now in a +05:00 zone whose UTC wall-clock differs from local.
    tz5 = datetime.timezone(datetime.timedelta(hours=5), name="TZ5")
    now = datetime.datetime(2026, 6, 4, 14, 32, 7, tzinfo=tz5)  # UTC 09:32:07

    ts = emit_stop_timestamp(repo_root=td, now=now)
    ts_text = ts[0]["text"] if ts else ""
    # converted to UTC -> 09:32:07, label populated
    if not ts_text.startswith("09:32:07 "):
        fail(f"iv: emit_stop_timestamp must render UTC-converted 09:32:07; got {ts_text!r}")
    elif not ZONE_LABEL_RE.search(ts_text):
        fail(f"iv: emit_stop_timestamp must carry a zone label; got {ts_text!r}")
    elif "UTC" not in ts_text:
        fail(f"iv: emit_stop_timestamp label must be UTC; got {ts_text!r}")
    else:
        ok(f"iv: emit_stop_timestamp converts to UTC + labels ({ts_text!r})")

    eta = _auto_evolve_next_tick_eta(td, now)
    # now UTC 09:32 -> next boundary 09:43 (+ cold-start +3) = 09:46, labelled.
    if eta is None:
        fail("iv: _auto_evolve_next_tick_eta returned None unexpectedly")
    elif not ZONE_LABEL_RE.search(eta):
        fail(f"iv: ETA must carry a zone label; got {eta!r}")
    elif "UTC" not in eta:
        fail(f"iv: ETA label must be UTC; got {eta!r}")
    elif not eta.startswith("09:"):
        fail(f"iv: ETA must be computed in UTC (09:xx); got {eta!r}")
    else:
        ok(f"iv: _auto_evolve_next_tick_eta converts to UTC + labels ({eta!r})")

# (v) the next-tick ETA string carries a zone label (no longer a bare HH:MM),
#     end-to-end through emit_auto_evolve_stop_line with display zone UTC.
with tempfile.TemporaryDirectory() as td:
    write_display_tz_feature(td, "UTC")
    os.makedirs(os.path.join(td, ".claude"), exist_ok=True)
    with open(os.path.join(td, ".claude", "scheduled_tasks.json"), "w") as f:
        json.dump(
            {"tasks": [{"prompt": "/rabbit-auto-evolve tick", "cron": "13,43 * * * *"}]},
            f,
        )
    open(os.path.join(td, ".rabbit-auto-evolve-active"), "w").close()
    os.makedirs(os.path.join(td, ".rabbit"), exist_ok=True)
    with open(os.path.join(td, ".rabbit", "auto-evolve-state.json"), "w") as f:
        json.dump({"started": True}, f)
    now = datetime.datetime(2026, 6, 4, 9, 5, 0, tzinfo=datetime.timezone.utc)
    r = emit_auto_evolve_stop_line(repo_root=td, now=now)
    text = r[0]["text"] if r else ""
    m = re.search(r"next tick (\d{2}:\d{2})( [A-Za-z0-9+\-]+)", text)
    if "next tick" not in text:
        fail(f"v: idle line missing 'next tick' ETA; got {text!r}")
    elif m is None:
        fail(f"v: ETA must be 'HH:MM <zone>' (zone-labelled, not bare); got {text!r}")
    elif "UTC" not in m.group(2):
        fail(f"v: ETA zone label must be UTC; got {text!r}")
    else:
        ok(f"v: next-tick ETA carries a zone label ({m.group(0)!r})")

if FAIL:
    print("test-runtime-display-timezone: FAIL", file=sys.stderr)
    sys.exit(1)
print("test-runtime-display-timezone: all checks passed.")
