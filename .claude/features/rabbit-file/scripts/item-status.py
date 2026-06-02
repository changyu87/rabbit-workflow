#!/usr/bin/env python3
"""item-status.py — read, transition, or update fields on a bug/backlog item.

Version: 0.3.0
Owner: rabbit-workflow team
Deprecation criterion: when a unified tracking system replaces file-based bug and backlog management
"""
import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import branch_ops

VALID_STATUSES = {"open", "close"}
VALID_TYPES = {"bug", "backlog"}
MUTABLE_FIELDS = {"priority", "title", "description"}
VALID_PRIORITIES = {"low", "medium", "high", "critical"}
# BACKLOG-7: per-field length limits and the sanitize/validate helpers live
# in branch_ops so file-item.py and item-status.py share a single source of
# truth (the pre-BACKLOG-7 shared 500-char cap is removed).


def _git_user():
    r = subprocess.run(["git", "config", "user.name"], capture_output=True, text=True)
    return r.stdout.strip() or "unknown"


def _now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def cmd_get(args):
    try:
        item = branch_ops.fetch_item(args.feature, args.type_, args.id)
    except RuntimeError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)
    if item is None:
        print(f"ERROR: item {args.id} not found", file=sys.stderr)
        sys.exit(1)
    print(item["status"])


def cmd_show(args):
    """BACKLOG-8: print the full item.json (pretty) for inspection."""
    try:
        item = branch_ops.fetch_item(args.feature, args.type_, args.id)
    except RuntimeError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)
    if item is None:
        print(f"ERROR: item {args.id} not found", file=sys.stderr)
        sys.exit(1)
    print(json.dumps(item, indent=2, sort_keys=False))


def cmd_set(args):
    if not args.reason or not args.reason.strip():
        print("ERROR: --reason is required and must be non-empty", file=sys.stderr)
        sys.exit(1)

    try:
        item = branch_ops.fetch_item(args.feature, args.type_, args.id)
    except RuntimeError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)
    if item is None:
        print(f"ERROR: item {args.id} not found", file=sys.stderr)
        sys.exit(1)

    # No-op short-circuit: a `set` to the current status must not append a
    # misleading "opened"/"closed" history entry or create a commit on
    # bug-backlog-files. Exit 0 with a clear message naming the current status.
    if item.get("status") == args.status:
        print(
            f"No-op: {args.id} already in status {args.status!r}; "
            f"no transition recorded."
        )
        sys.exit(0)

    now = _now()
    actor = _git_user()
    action = "closed" if args.status == "close" else "opened"

    item["status"] = args.status
    item["closed"] = now if args.status == "close" else None

    history_entry = {"ts": now, "actor": actor, "action": action, "note": args.reason.strip()}
    if args.fix_commits:
        history_entry["fix_commits"] = args.fix_commits
    item.setdefault("history", []).append(history_entry)

    try:
        branch_ops.commit_item(args.feature, args.type_, args.id, item)
    except RuntimeError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)

    print(f"Status set: {args.id} -> {args.status}")


def cmd_update(args):
    if not args.reason or not args.reason.strip():
        print("ERROR: --reason is required and must be non-empty", file=sys.stderr)
        sys.exit(1)
    if args.field not in MUTABLE_FIELDS:
        print(
            f"ERROR: field {args.field!r} is not mutable "
            f"(allowed: {sorted(MUTABLE_FIELDS)})",
            file=sys.stderr,
        )
        sys.exit(1)
    if args.value == "" or args.value is None:
        print("ERROR: --value is required and must be non-empty", file=sys.stderr)
        sys.exit(1)
    # BACKLOG-7: sanitize title/description first (strip ASCII control chars
    # except \t \n \r), then apply per-field length validation. The
    # sanitized value is what gets persisted to item.json.
    if args.field in ("title", "description"):
        args.value = branch_ops.sanitize_text(args.value)
        limit = (
            branch_ops.MAX_TITLE_LEN if args.field == "title"
            else branch_ops.MAX_DESCRIPTION_LEN
        )
        try:
            branch_ops.validate_field_length(args.field, args.value, limit)
        except ValueError as e:
            print(f"ERROR: {e}", file=sys.stderr)
            sys.exit(1)
    if args.field == "priority" and args.value not in VALID_PRIORITIES:
        print(
            f"ERROR: priority must be one of {sorted(VALID_PRIORITIES)}, "
            f"got {args.value!r}",
            file=sys.stderr,
        )
        sys.exit(1)

    try:
        item = branch_ops.fetch_item(args.feature, args.type_, args.id)
    except RuntimeError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)
    if item is None:
        print(f"ERROR: item {args.id} not found", file=sys.stderr)
        sys.exit(1)

    if item.get("status") != "open":
        print(
            f"ERROR: item {args.id} is closed; reopen via "
            f"`set --status open --reason ...` before updating fields",
            file=sys.stderr,
        )
        sys.exit(1)

    old_value = item.get(args.field)
    if old_value == args.value:
        print(f"No change: {args.field} already {args.value!r}")
        sys.exit(0)

    item[args.field] = args.value
    history_entry = {
        "ts": _now(),
        "actor": _git_user(),
        "action": "updated",
        "field": args.field,
        "old_value": old_value,
        "new_value": args.value,
        "note": args.reason.strip(),
    }
    item.setdefault("history", []).append(history_entry)

    try:
        branch_ops.commit_item(args.feature, args.type_, args.id, item)
    except RuntimeError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)

    print(f"Updated {args.id}: {args.field} = {args.value!r}")


def main():
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)

    g = sub.add_parser("get")
    g.add_argument("--feature", required=True)
    g.add_argument("--type", dest="type_", required=True, choices=sorted(VALID_TYPES))
    g.add_argument("--id", required=True)

    sh = sub.add_parser("show")
    sh.add_argument("--feature", required=True)
    sh.add_argument("--type", dest="type_", required=True, choices=sorted(VALID_TYPES))
    sh.add_argument("--id", required=True)

    s = sub.add_parser("set")
    s.add_argument("--feature", required=True)
    s.add_argument("--type", dest="type_", required=True, choices=sorted(VALID_TYPES))
    s.add_argument("--id", required=True)
    s.add_argument("--status", required=True, choices=sorted(VALID_STATUSES))
    s.add_argument("--reason", required=True)
    s.add_argument("--fix-commits", dest="fix_commits")

    u = sub.add_parser("update")
    u.add_argument("--feature", required=True)
    u.add_argument("--type", dest="type_", required=True, choices=sorted(VALID_TYPES))
    u.add_argument("--id", required=True)
    u.add_argument("--field", required=True)
    u.add_argument("--value", required=True)
    u.add_argument("--reason", required=True)

    args = p.parse_args()
    if args.cmd == "get":
        cmd_get(args)
    elif args.cmd == "show":
        cmd_show(args)
    elif args.cmd == "set":
        cmd_set(args)
    else:
        cmd_update(args)


if __name__ == "__main__":
    main()
