#!/usr/bin/env python3
# file-bug.py -- file a new bug under centralized .claude/bugs/ storage.
# Usage: file-bug.py --title T --severity S --description D [--related-feature F] [--filed-by A]
# Exit: 0=ok 1=val-err 2=inv-err

import argparse
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


def get_repo_root():
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, check=True
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError:
        print("ERROR: cannot determine repo root", file=sys.stderr)
        sys.exit(2)


def main():
    parser = argparse.ArgumentParser(
        usage="file-bug.py --title T --severity {low|medium|high|critical} "
              "--description D [--related-feature F] [--filed-by A]",
        add_help=False
    )
    parser.add_argument("--title")
    parser.add_argument("--severity")
    parser.add_argument("--description")
    parser.add_argument("--related-feature", dest="feat")
    parser.add_argument("--filed-by", dest="filer")
    parser.add_argument("-h", "--help", action="store_true")

    # Unknown args → exit 2
    try:
        args, unknown = parser.parse_known_args()
    except SystemExit:
        sys.exit(2)

    if args.help:
        print(
            "usage: file-bug.py --title T --severity {low|medium|high|critical} "
            "--description D [--related-feature F] [--filed-by A]",
            file=sys.stderr
        )
        sys.exit(0)

    if unknown:
        print(f"unknown arg: {unknown[0]}", file=sys.stderr)
        print(
            "usage: file-bug.py --title T --severity {low|medium|high|critical} "
            "--description D [--related-feature F] [--filed-by A]",
            file=sys.stderr
        )
        sys.exit(2)

    if not args.title:
        print("ERROR: --title required", file=sys.stderr)
        sys.exit(1)
    if not args.severity:
        print("ERROR: --severity required", file=sys.stderr)
        sys.exit(1)
    if not args.description:
        print("ERROR: --description required", file=sys.stderr)
        sys.exit(1)

    if args.severity not in ("low", "medium", "high", "critical"):
        print("ERROR: invalid severity (allowed: low|medium|high|critical)", file=sys.stderr)
        sys.exit(1)

    feat = args.feat or ""
    if feat:
        if not re.match(r'^[a-z][a-z0-9-]{0,49}$', feat):
            print(
                "ERROR: --related-feature must match [a-z][a-z0-9-]* (max 50 chars)",
                file=sys.stderr
            )
            sys.exit(1)

    repo_root = get_repo_root()
    find_feature = os.path.join(repo_root, ".claude/features/contract/scripts/find-feature.py")
    bug_prefix = os.environ.get("BUG_PREFIX", "RBT")

    if feat:
        result = subprocess.run(
            ["python3", find_feature, repo_root, "lookup", feat],
            capture_output=True
        )
        if result.returncode != 0:
            print(
                f"ERROR: related-feature '{feat}' not found in feature index",
                file=sys.stderr
            )
            sys.exit(1)
        feature_name = feat
        prefix = feat.upper()
        bugs_base = os.path.join(repo_root, ".claude/bugs")
        bug_root = os.path.join(bugs_base, feature_name)
    else:
        bugs_base = os.path.join(repo_root, ".claude/bugs")
        bug_root = os.path.join(bugs_base, "unassigned")
        prefix = bug_prefix

    # Compute next bug number
    max_n = 0
    bug_root_path = Path(bug_root)
    if bug_root_path.is_dir():
        for f in bug_root_path.glob("*/bug.json"):
            try:
                data = json.loads(f.read_text())
                existing_name = data.get("name", "")
                m = re.match(rf'^{re.escape(prefix)}-([1-9][0-9]*)$', existing_name)
                if m:
                    n = int(m.group(1))
                    if n > max_n:
                        max_n = n
            except Exception:
                pass
        for d in bug_root_path.iterdir():
            if d.is_dir():
                m = re.match(rf'^{re.escape(prefix)}-([1-9][0-9]*)$', d.name)
                if m:
                    n = int(m.group(1))
                    if n > max_n:
                        max_n = n

    n = max_n + 1
    name = f"{prefix}-{n}"

    bug_dir = os.path.join(bug_root, name)
    if os.path.exists(bug_dir):
        print(f"ERROR: bug already exists at {bug_dir}", file=sys.stderr)
        sys.exit(1)

    filer = args.filer or os.environ.get("USER", "unknown")

    # Main-branch guard
    try:
        branch_result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True, text=True
        )
        current_branch = branch_result.stdout.strip() if branch_result.returncode == 0 else ""
    except Exception:
        current_branch = ""

    if current_branch != "main":
        branch_display = current_branch or "unknown"
        print(
            f"WARNING: current git branch is '{branch_display}', not 'main'.",
            file=sys.stderr
        )
        print(
            "Bugs filed on non-main branches may not be tracked in the main bug index.",
            file=sys.stderr
        )
        # Check if stdin is a tty and /dev/tty is available
        if sys.stdin.isatty() and os.path.exists("/dev/tty"):
            try:
                with open("/dev/tty") as tty:
                    sys.stderr.write(f"File bug on branch '{branch_display}'? [y/N] ")
                    sys.stderr.flush()
                    confirm = tty.readline().strip()
                if confirm.lower() in ("y", "yes"):
                    pass
                else:
                    print("Aborted.", file=sys.stderr)
                    sys.exit(1)
            except Exception:
                print(
                    "No tty available — aborting. Run on main branch or confirm interactively.",
                    file=sys.stderr
                )
                sys.exit(1)
        else:
            print(
                "No tty available — aborting. Run on main branch or confirm interactively.",
                file=sys.stderr
            )
            sys.exit(1)

    os.makedirs(bug_dir, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    bug_data = {
        "name": name,
        "title": args.title,
        "status": "open",
        "severity": args.severity,
        "description": args.description,
        "related_feature": feat if feat else None,
        "filed": ts,
        "filed_by": filer,
        "closed": None,
        "closed_by": None,
        "history": [
            {
                "ts": ts,
                "actor": filer,
                "action": "opened",
                "note": "initial filing"
            }
        ]
    }

    bug_json_path = os.path.join(bug_dir, "bug.json")
    with open(bug_json_path, "w") as f:
        json.dump(bug_data, f, indent=2)
        f.write("\n")

    # Git commit
    try:
        git_root_result = subprocess.run(
            ["git", "-C", bug_dir, "rev-parse", "--show-toplevel"],
            capture_output=True, text=True
        )
        git_root = git_root_result.stdout.strip() if git_root_result.returncode == 0 else ""
        if git_root:
            subprocess.run(
                ["git", "-C", git_root, "add", bug_json_path],
                capture_output=True
            )
            subprocess.run(
                ["git", "-C", git_root, "commit", "-m", f"bug: file {name} ({args.title})"],
                capture_output=True
            )
    except Exception:
        pass

    print(f"filed: {bug_json_path}  [{name}]")
    sys.exit(0)


if __name__ == "__main__":
    main()
