#!/usr/bin/env python3
"""log-tick.py — full per-tick observability logger (Inv 37, issue #404).

This is the BROAD per-tick EXECUTION-trace logger. It is DISTINCT from the
minimal Inv 36 `tick-log.py` (which logs heartbeat/guard/schedule DECISIONS
to `.rabbit/tick.log`). The two logs COEXIST: different files, different
purposes. #404 does NOT modify `tick-log.py` or Inv 36.

`log-tick.py` owns ALL writes to `<state_dir>/auto-evolve.log` (state dir via
`RABBIT_AUTO_EVOLVE_STATE_DIR`, else `<cwd>/.rabbit`, matching
`update-state.py` / `tick-log.py`). One invocation emits AT MOST ONE JSON
line.

Subcommands:
  emit    --record-kind <tick-start|tick-end|phase|phase-transition> [fields]
          Append one JSON line IF the record-kind is included at the active
          verbosity level (strictly-additive: quiet ⊂ normal ⊂ debug) AND the
          enable flag is on. The line is capped at 2 KB hard.
  rotate  At tick start, rotate `auto-evolve.log` → `.log.1` → `.log.2` →
          `.log.3` (dropping the oldest) when it exceeds 5 MB. At most 3
          rotated files are kept (≤ 4 total).
  config  on | off | level <quiet|normal|debug>
          Mutate rabbit-auto-evolve's OWN log config
          (`<state_dir>/auto-evolve-log-config.json`). NOT rabbit-cage's
          configuration array.

Verbosity levels (Inv 37 b):
  quiet  = tick start/end only            -> {tick-start, tick-end}
  normal = quiet + phase results/blockers -> + {phase}        (DEFAULT)
  debug  = normal + every phase transition-> + {phase-transition}

A record below the active level is DROPPED (no file growth). When the enable
flag is off, NOTHING is written (zero file growth) — a hard requirement.

Version: 1.0.0
Owner: rabbit-workflow team (rabbit-auto-evolve)
Deprecation criterion: when Claude Code or rabbit gains a native always-on
autonomous-agent mode that supersedes this skill.
"""

import argparse
import datetime
import json
import os
import sys

LOG_NAME = "auto-evolve.log"
CONFIG_NAME = "auto-evolve-log-config.json"

MAX_LINE_BYTES = 2048
MAX_LOG_BYTES = 5 * 1024 * 1024
MAX_ROTATED = 3

LEVELS = ("quiet", "normal", "debug")
DEFAULT_LEVEL = "normal"

# Which record-kinds each level admits. Strictly additive.
LEVEL_KINDS = {
    "quiet": {"tick-start", "tick-end"},
    "normal": {"tick-start", "tick-end", "phase"},
    "debug": {"tick-start", "tick-end", "phase", "phase-transition"},
}
RECORD_KINDS = ("tick-start", "tick-end", "phase", "phase-transition")

# Truncatable array fields, longest first, so the 2 KB cap elides bulk first.
ARRAY_FIELDS = ("queue_head", "in_flight", "merged_this_tick", "blockers")


def _state_dir():
    override = os.environ.get("RABBIT_AUTO_EVOLVE_STATE_DIR")
    if override:
        return override
    return os.path.join(os.getcwd(), ".rabbit")


def _log_path():
    return os.path.join(_state_dir(), LOG_NAME)


def _config_path():
    return os.path.join(_state_dir(), CONFIG_NAME)


def _now_iso():
    return datetime.datetime.now(datetime.timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )


def _read_config():
    path = _config_path()
    cfg = {"enabled": True, "level": DEFAULT_LEVEL}
    try:
        with open(path) as f:
            data = json.load(f)
        if isinstance(data, dict):
            if isinstance(data.get("enabled"), bool):
                cfg["enabled"] = data["enabled"]
            if data.get("level") in LEVELS:
                cfg["level"] = data["level"]
    except (OSError, json.JSONDecodeError):
        pass
    return cfg


def _write_config(cfg):
    state_dir = _state_dir()
    os.makedirs(state_dir, exist_ok=True)
    with open(_config_path(), "w") as f:
        json.dump(cfg, f)


def _split_list(raw):
    if raw is None or raw == "":
        return []
    return [item for item in raw.split(",") if item != ""]


def _build_record(args):
    return {
        "ts": _now_iso(),
        "tick": args.tick,
        "session_id": args.session_id,
        "phase_reached": args.phase_reached,
        "phase_result": args.phase_result,
        "in_flight": _split_list(args.in_flight),
        "queue_head": _split_list(args.queue_head),
        "queue_len": args.queue_len,
        "merged_this_tick": _split_list(args.merged_this_tick),
        "blockers": _split_list(args.blockers),
        "next_action": args.next_action,
        "record_kind": args.record_kind,
    }


def _serialize_capped(record):
    """json.dumps the record; if the line exceeds the 2 KB hard cap, elide the
    longest array fields (longest-first) until it fits, marking truncation."""
    line = json.dumps(record, separators=(",", ":"))
    if len(line.encode("utf-8")) < MAX_LINE_BYTES:
        return line
    rec = dict(record)
    rec["truncated"] = True
    for field in ARRAY_FIELDS:
        if field in rec and isinstance(rec[field], list) and rec[field]:
            kept = len(rec[field])
            rec[field] = [f"...{kept} items elided..."]
            line = json.dumps(rec, separators=(",", ":"))
            if len(line.encode("utf-8")) < MAX_LINE_BYTES:
                return line
    # Last resort: hard-trim the encoded line to stay under the cap.
    encoded = line.encode("utf-8")[: MAX_LINE_BYTES - 1]
    return encoded.decode("utf-8", "ignore")


def cmd_emit(args):
    cfg = _read_config()
    if not cfg["enabled"]:
        return 0
    if args.record_kind not in LEVEL_KINDS[cfg["level"]]:
        return 0  # below active level — drop, no file growth
    state_dir = _state_dir()
    os.makedirs(state_dir, exist_ok=True)
    line = _serialize_capped(_build_record(args))
    with open(_log_path(), "a") as f:
        f.write(line + "\n")
    return 0


def cmd_rotate(args):
    log_path = _log_path()
    try:
        size = os.path.getsize(log_path)
    except OSError:
        return 0  # no log yet — nothing to rotate
    if size <= MAX_LOG_BYTES:
        return 0
    # Drop the oldest, then shift .log.N -> .log.N+1, then .log -> .log.1.
    oldest = f"{log_path}.{MAX_ROTATED}"
    if os.path.exists(oldest):
        os.remove(oldest)
    for n in range(MAX_ROTATED - 1, 0, -1):
        src = f"{log_path}.{n}"
        if os.path.exists(src):
            os.replace(src, f"{log_path}.{n + 1}")
    os.replace(log_path, f"{log_path}.1")
    return 0


def cmd_config(args):
    cfg = _read_config()
    if args.action == "on":
        cfg["enabled"] = True
    elif args.action == "off":
        cfg["enabled"] = False
    elif args.action == "level":
        cfg["level"] = args.value
    _write_config(cfg)
    return 0


def build_parser():
    parser = argparse.ArgumentParser(
        description="Full per-tick observability logger for "
                    ".rabbit/auto-evolve.log (Inv 37 / #404). Honors "
                    "RABBIT_AUTO_EVOLVE_STATE_DIR. Distinct from the minimal "
                    "tick-log.py (Inv 36)."
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_emit = sub.add_parser("emit", help="append one per-tick JSON line")
    p_emit.add_argument("--record-kind", required=True, choices=RECORD_KINDS,
                        dest="record_kind")
    p_emit.add_argument("--tick", type=int, default=0)
    p_emit.add_argument("--session-id", dest="session_id", default="")
    p_emit.add_argument("--phase-reached", dest="phase_reached", default="")
    p_emit.add_argument("--phase-result", dest="phase_result", default="")
    p_emit.add_argument("--in-flight", dest="in_flight", default="")
    p_emit.add_argument("--queue-head", dest="queue_head", default="")
    p_emit.add_argument("--queue-len", dest="queue_len", type=int, default=0)
    p_emit.add_argument("--merged-this-tick", dest="merged_this_tick",
                        default="")
    p_emit.add_argument("--blockers", default="")
    p_emit.add_argument("--next-action", dest="next_action", default="")
    p_emit.set_defaults(func=cmd_emit)

    p_rot = sub.add_parser("rotate", help="rotate the log at tick start (>5MB)")
    p_rot.set_defaults(func=cmd_rotate)

    p_cfg = sub.add_parser("config", help="mutate the OWN log config")
    cfg_sub = p_cfg.add_subparsers(dest="action", required=True)
    cfg_sub.add_parser("on", help="enable logging")
    cfg_sub.add_parser("off", help="disable logging (zero file growth)")
    p_level = cfg_sub.add_parser("level", help="set verbosity level")
    p_level.add_argument("value", choices=LEVELS)
    p_cfg.set_defaults(func=cmd_config)

    return parser


def main():
    args = build_parser().parse_args()
    try:
        return args.func(args)
    except OSError as e:
        sys.stderr.write(f"log-tick: {e}\n")
        return 1


if __name__ == "__main__":
    sys.exit(main())
