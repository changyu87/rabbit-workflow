#!/usr/bin/env python3
# backlog-item-status.py — read or transition the status of a backlog item.
#
# Usage:
#   backlog-item-status.py get <item-dir>
#   backlog-item-status.py set <item-dir> <new-status> --reason <text> [--fix-commits <sha>] [--actor <name>]
#
# Valid status values: open | in-progress | implemented | refused | reopened
#
# Allowed transitions:
#   open        -> in-progress  (--reason required)
#   open        -> refused      (--reason required)
#   in-progress -> implemented  (--reason required, --fix-commits required)
#   in-progress -> refused      (--reason required)
#   implemented -> reopened     (--reason required)
#   refused     -> reopened     (--reason required)
#   reopened    -> in-progress  (--reason required)
#   reopened    -> refused      (--reason required)
#
# Invalid statuses: done, cancelled — rejected with exit 1
#
# Exit: 0=ok  1=error  2=usage

import sys
import os
import json
import subprocess
from datetime import datetime, timezone


USAGE = """\
usage:
  backlog-item-status.py get <item-dir>
  backlog-item-status.py set <item-dir> <new-status> --reason <text> [--fix-commits <sha>] [--actor <name>]
"""

VALID_STATUSES = {"open", "in-progress", "implemented", "refused", "reopened"}
INVALID_STATUSES = {"done", "cancelled"}

ALLOWED_TRANSITIONS = {
    ("open", "in-progress"),
    ("open", "refused"),
    ("in-progress", "implemented"),
    ("in-progress", "refused"),
    ("implemented", "reopened"),
    ("refused", "reopened"),
    ("reopened", "in-progress"),
    ("reopened", "refused"),
}


def usage_exit(code=2):
    print(USAGE, file=sys.stderr, end="")
    sys.exit(code)


def git_commit_silent(item_dir, message):
    try:
        result = subprocess.run(
            ["git", "-C", item_dir, "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            return
        top = result.stdout.strip()
        item_json = os.path.join(item_dir, "item.json")
        subprocess.run(["git", "-C", top, "add", item_json], capture_output=True)
        subprocess.run(
            ["git", "-C", top, "commit", "-m", message], capture_output=True
        )
    except Exception:
        pass


def cmd_get(args):
    if not args:
        usage_exit(2)
    item_dir = args[0]
    if not os.path.isdir(item_dir):
        print(f"ERROR: not a directory: {item_dir}", file=sys.stderr)
        sys.exit(1)
    item_json = os.path.join(item_dir, "item.json")
    if not os.path.isfile(item_json):
        print(f"ERROR: missing {item_json}", file=sys.stderr)
        sys.exit(1)
    with open(item_json) as f:
        data = json.load(f)
    print(data.get("status", ""))
    sys.exit(0)


def cmd_set(args):
    if len(args) < 2:
        usage_exit(2)
    item_dir = args[0]
    new_status = args[1]
    rest = args[2:]

    # Parse optional flags
    reason = ""
    fix_commits = ""
    tdd_report_path = ""
    actor = os.environ.get("USER", "unknown")

    i = 0
    while i < len(rest):
        if rest[i] == "--reason":
            if i + 1 >= len(rest):
                print("ERROR: --reason requires a value", file=sys.stderr)
                sys.exit(2)
            reason = rest[i + 1]
            i += 2
        elif rest[i] == "--fix-commits":
            if i + 1 >= len(rest):
                print("ERROR: --fix-commits requires a value", file=sys.stderr)
                sys.exit(2)
            fix_commits = rest[i + 1]
            i += 2
        elif rest[i] == "--tdd-report":
            if i + 1 >= len(rest):
                print("ERROR: --tdd-report requires a path", file=sys.stderr)
                sys.exit(2)
            tdd_report_path = rest[i + 1]
            i += 2
        elif rest[i] == "--actor":
            if i + 1 >= len(rest):
                print("ERROR: --actor requires a value", file=sys.stderr)
                sys.exit(2)
            actor = rest[i + 1]
            i += 2
        else:
            print(f"ERROR: unknown arg: {rest[i]}", file=sys.stderr)
            usage_exit(2)

    if not item_dir or not new_status:
        usage_exit(2)

    if not os.path.isdir(item_dir):
        print(f"ERROR: not a directory: {item_dir}", file=sys.stderr)
        sys.exit(1)

    item_json = os.path.join(item_dir, "item.json")
    if not os.path.isfile(item_json):
        print(f"ERROR: missing {item_json}", file=sys.stderr)
        sys.exit(1)

    if not reason:
        print("ERROR: --reason is required", file=sys.stderr)
        sys.exit(1)

    # Validate new status
    if new_status in INVALID_STATUSES:
        print(
            f"ERROR: invalid status '{new_status}' — 'done' and 'cancelled' are no longer valid; "
            "use 'implemented' or 'refused'",
            file=sys.stderr,
        )
        sys.exit(1)
    if new_status not in VALID_STATUSES:
        print(
            f"ERROR: invalid status '{new_status}' (allowed: open|in-progress|implemented|refused|reopened)",
            file=sys.stderr,
        )
        sys.exit(1)

    # Reject --fix-commits on non-implemented transitions
    if fix_commits and new_status != "implemented":
        print(
            "ERROR: --fix-commits is only valid when transitioning to 'implemented'",
            file=sys.stderr,
        )
        sys.exit(1)

    # Require --fix-commits when transitioning to implemented
    if new_status == "implemented" and not fix_commits:
        print(
            "ERROR: --fix-commits is required when transitioning to 'implemented'",
            file=sys.stderr,
        )
        sys.exit(1)

    with open(item_json) as f:
        data = json.load(f)

    cur_status = data.get("status", "")

    # Same status: no-op
    if cur_status == new_status:
        print(f"no-op: already {cur_status}")
        sys.exit(0)

    # Validate allowed transitions
    if (cur_status, new_status) not in ALLOWED_TRANSITIONS:
        print(
            f"ERROR: transition '{cur_status}' -> '{new_status}' is not allowed",
            file=sys.stderr,
        )
        sys.exit(1)

    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    # Build history entry
    if new_status == "implemented":
        tdd_report = None
        if tdd_report_path and os.path.isfile(tdd_report_path):
            with open(tdd_report_path) as f:
                tdd_report = json.load(f)
        history_entry = {
            "ts": ts,
            "actor": actor,
            "action": new_status,
            "note": reason,
            "fix_commits": fix_commits,
            "tdd_report": tdd_report,
        }
        data["status"] = new_status
        data["closed"] = ts
    elif new_status == "reopened":
        history_entry = {
            "ts": ts,
            "actor": actor,
            "action": new_status,
            "note": reason,
        }
        data["status"] = new_status
        data["closed"] = None
    else:
        history_entry = {
            "ts": ts,
            "actor": actor,
            "action": new_status,
            "note": reason,
        }
        data["status"] = new_status

    data.setdefault("history", []).append(history_entry)

    # Write atomically via tmp file
    tmp_path = item_json + ".tmp"
    with open(tmp_path, "w") as f:
        json.dump(data, f, indent=2)
        f.write("\n")
    os.replace(tmp_path, item_json)

    # Git commit after successful transition — silent on failure
    reason_summary = reason[:60]
    name = data.get("name", "unknown")
    git_commit_silent(item_dir, f"backlog: {name} {cur_status} -> {new_status} ({reason_summary})")

    print(f"{cur_status} -> {new_status}")
    sys.exit(0)


def main():
    args = sys.argv[1:]

    if not args:
        usage_exit(2)

    cmd = args[0]
    rest = args[1:]

    if cmd in ("-h", "--help", "help"):
        print(USAGE, end="")
        sys.exit(0)
    elif cmd == "get":
        cmd_get(rest)
    elif cmd == "set":
        cmd_set(rest)
    else:
        print(f"ERROR: unknown subcommand '{cmd}'", file=sys.stderr)
        usage_exit(2)


if __name__ == "__main__":
    main()
