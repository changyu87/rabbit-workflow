#!/usr/bin/env python3
# bug-status.py -- read or transition bug status.
# The description field is NEVER modified after initial filing.
# Exit: 0=ok 1=denied 2=inv-err

import json
import os
import subprocess
import sys
from datetime import datetime, timezone


ALLOWED_STATUSES = ("open", "closed", "reopened", "refused")

ALLOWED_TRANSITIONS = {
    "open->closed",
    "closed->reopened",
    "reopened->closed",
    "open->refused",
    "reopened->refused",
    "refused->reopened",
}


def usage():
    print("usage: bug-status.py get DIR", file=sys.stderr)
    print(
        "  set DIR STATUS --note R [--actor A] [--skip-vet-reason R] "
        "[--fix-commits C] [--touched-files F]",
        file=sys.stderr
    )


def load_bug(path):
    with open(path) as f:
        return json.load(f)


def write_bug(path, data):
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(data, f, indent=2)
        f.write("\n")
    os.replace(tmp, path)


def git_commit(bug_dir, message):
    try:
        result = subprocess.run(
            ["git", "-C", bug_dir, "rev-parse", "--show-toplevel"],
            capture_output=True, text=True
        )
        git_root = result.stdout.strip() if result.returncode == 0 else ""
        if git_root:
            bug_json = os.path.join(bug_dir, "bug.json")
            subprocess.run(
                ["git", "-C", git_root, "add", bug_json],
                capture_output=True
            )
            subprocess.run(
                ["git", "-C", git_root, "commit", "-m", message],
                capture_output=True
            )
    except Exception:
        pass


def cmd_get(args):
    if not args:
        usage()
        sys.exit(2)
    dir_ = args[0]
    if not os.path.isdir(dir_):
        print(f"ERROR: not a directory: {dir_}", file=sys.stderr)
        sys.exit(2)
    bug_json = os.path.join(dir_, "bug.json")
    if not os.path.isfile(bug_json):
        print(f"ERROR: missing {bug_json}", file=sys.stderr)
        sys.exit(2)
    data = load_bug(bug_json)
    print(data.get("status", ""))


def cmd_set(args):
    if len(args) < 2:
        usage()
        sys.exit(2)
    dir_ = args[0]
    new_status = args[1]
    rest = args[2:]

    note = ""
    actor = os.environ.get("USER", "unknown")
    skip_vet_reason = ""
    fix_commits = ""
    touched_files = ""
    tdd_report_path = ""

    i = 0
    while i < len(rest):
        a = rest[i]
        if a == "--reason":
            if i + 1 >= len(rest):
                print(f"unknown arg: {a}", file=sys.stderr)
                sys.exit(2)
            note = rest[i + 1]; i += 2
        elif a == "--actor":
            if i + 1 >= len(rest):
                print(f"unknown arg: {a}", file=sys.stderr)
                sys.exit(2)
            actor = rest[i + 1]; i += 2
        elif a == "--skip-vet-reason":
            if i + 1 >= len(rest):
                print(f"unknown arg: {a}", file=sys.stderr)
                sys.exit(2)
            skip_vet_reason = rest[i + 1]; i += 2
        elif a == "--fix-commits":
            if i + 1 >= len(rest):
                print(f"unknown arg: {a}", file=sys.stderr)
                sys.exit(2)
            fix_commits = rest[i + 1]; i += 2
        elif a == "--touched-files":
            if i + 1 >= len(rest):
                print(f"unknown arg: {a}", file=sys.stderr)
                sys.exit(2)
            touched_files = rest[i + 1]; i += 2
        elif a == "--tdd-report":
            if i + 1 >= len(rest):
                print(f"unknown arg: {a}", file=sys.stderr)
                sys.exit(2)
            tdd_report_path = rest[i + 1]; i += 2
        else:
            print(f"unknown arg: {a}", file=sys.stderr)
            sys.exit(2)

    if not dir_ or not new_status:
        usage()
        sys.exit(2)
    if not note:
        print("ERROR: --reason is required", file=sys.stderr)
        sys.exit(1)
    if not os.path.isdir(dir_):
        print(f"ERROR: not a directory: {dir_}", file=sys.stderr)
        sys.exit(2)
    bug_json = os.path.join(dir_, "bug.json")
    if not os.path.isfile(bug_json):
        print(f"ERROR: missing {bug_json}", file=sys.stderr)
        sys.exit(2)

    if new_status not in ALLOWED_STATUSES:
        print("ERROR: invalid status (allowed: open|closed|reopened|refused)", file=sys.stderr)
        sys.exit(1)

    data = load_bug(bug_json)
    cur = data.get("status", "")

    if cur == new_status:
        print(f"no-op: already {cur}")
        sys.exit(0)

    transition = f"{cur}->{new_status}"
    if transition not in ALLOWED_TRANSITIONS:
        print("ERROR: transition not allowed", file=sys.stderr)
        sys.exit(1)

    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    effective_note = note

    if new_status == "closed":
        if skip_vet_reason:
            effective_note = f"[skip-vet: {skip_vet_reason}] {note}"
        else:
            vet_triage = os.path.join(dir_, "vet-triage.json")
            if not os.path.isfile(vet_triage):
                print(
                    "ERROR (R7): vet-triage.json missing — run rabbit-triage.sh first, "
                    "or use --skip-vet-reason",
                    file=sys.stderr
                )
                sys.exit(1)
            if not tdd_report_path:
                print("ERROR (R7): --tdd-report <path> required to close bug", file=sys.stderr)
                sys.exit(1)
            if not os.path.isfile(tdd_report_path):
                print(f"ERROR: tdd-report file not found: {tdd_report_path}", file=sys.stderr)
                sys.exit(1)
            if not fix_commits:
                print(
                    "ERROR: --fix-commits is required when closing a bug "
                    "(use --skip-vet-reason to bypass)",
                    file=sys.stderr
                )
                sys.exit(1)

    if new_status == "refused" and fix_commits:
        print(
            "ERROR: --fix-commits is not applicable for refused status",
            file=sys.stderr
        )
        sys.exit(1)

    # Read tdd_report JSON
    tdd_report_json = None
    if tdd_report_path and os.path.isfile(tdd_report_path):
        with open(tdd_report_path) as f:
            tdd_report_json = json.load(f)

    # Build history entry
    history_entry = {
        "ts": ts,
        "actor": actor,
        "action": new_status,
        "note": effective_note,
    }
    if fix_commits and touched_files:
        history_entry["fix_commits"] = fix_commits
        history_entry["touched_files"] = touched_files
    elif fix_commits:
        history_entry["fix_commits"] = fix_commits
    elif touched_files:
        history_entry["touched_files"] = touched_files

    if new_status == "closed":
        history_entry["tdd_report"] = tdd_report_json
        data["status"] = new_status
        data["closed"] = ts
        data["closed_by"] = actor
    elif new_status in ("reopened", "refused"):
        data["status"] = new_status
        data["closed"] = None
        data["closed_by"] = None
    elif new_status == "open":
        print("ERROR: cannot transition to open", file=sys.stderr)
        sys.exit(1)

    if "history" not in data or not isinstance(data["history"], list):
        data["history"] = []
    data["history"].append(history_entry)

    write_bug(bug_json, data)

    # Git commit
    reason_short = effective_note[:60]
    git_commit(dir_, f"bug: {cur} -> {new_status} ({reason_short})")

    print("transitioned")


def main():
    args = sys.argv[1:]

    if not args or args[0] in ("", "--help", "help", "-h"):
        usage()
        sys.exit(0 if args and args[0] in ("--help", "help", "-h") else 2)

    cmd = args[0]
    rest = args[1:]

    if cmd == "get":
        cmd_get(rest)
    elif cmd == "set":
        cmd_set(rest)
    else:
        print(f"ERROR: unknown subcommand: {cmd}", file=sys.stderr)
        usage()
        sys.exit(2)


if __name__ == "__main__":
    main()
