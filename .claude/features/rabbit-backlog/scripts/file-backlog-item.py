#!/usr/bin/env python3
# file-backlog-item.py — file a new backlog item in centralized storage.
#
# Usage:
#   file-backlog-item.py --related-feature <name> --title <title> \
#                        [--priority low|medium|high|critical] \
#                        [--owner <name>]
#
# Options:
#   --related-feature  feature name (must exist in feature index)
#   --title            short human-readable title
#   --priority         low | medium | high | critical (default: medium)
#   --owner            owner name (default: $USER or "unknown")
#
# Creates: .claude/backlogs/<feature-name>/<PREFIX>-BACKLOG-<N>/item.json
# Prints:  the created item directory path to stdout
# Exit:    0=created  1=error  2=usage

import sys
import os
import json
import subprocess
import argparse
from datetime import datetime, timezone


def usage():
    print(
        "usage: file-backlog-item.py --related-feature <name> --title <title> \\\n"
        "                             [--priority low|medium|high|critical] \\\n"
        "                             [--owner <name>]",
        file=sys.stderr,
    )


def git_toplevel(path):
    try:
        result = subprocess.run(
            ["git", "-C", path, "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:
        pass
    return None


def main():
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--related-feature", dest="feature_name", default="")
    parser.add_argument("--title", default="")
    parser.add_argument("--priority", default="medium")
    parser.add_argument("--owner", default=os.environ.get("USER", "unknown"))
    parser.add_argument("-h", "--help", action="store_true")

    # Parse known args; unknown args => usage error
    try:
        args, unknown = parser.parse_known_args()
    except SystemExit:
        usage()
        sys.exit(2)

    if args.help:
        usage()
        sys.exit(0)

    if unknown:
        print(f"ERROR: unknown arg: {unknown[0]}", file=sys.stderr)
        usage()
        sys.exit(2)

    if not args.feature_name or not args.title:
        print("ERROR: --related-feature and --title are required", file=sys.stderr)
        usage()
        sys.exit(2)

    valid_priorities = {"low", "medium", "high", "critical"}
    if args.priority not in valid_priorities:
        print(
            f"ERROR: invalid priority '{args.priority}' (allowed: low|medium|high|critical)",
            file=sys.stderr,
        )
        sys.exit(1)

    # Resolve REPO_ROOT
    rabbit_root = os.environ.get("RABBIT_ROOT", "")
    if rabbit_root:
        repo_root = rabbit_root
    else:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        repo_root = git_toplevel(script_dir)
        if not repo_root:
            print("ERROR: cannot determine repo root", file=sys.stderr)
            sys.exit(1)

    # Branch guard: warn and prompt if not on main branch
    try:
        branch_result = subprocess.run(
            ["git", "-C", repo_root, "branch", "--show-current"],
            capture_output=True,
            text=True,
        )
        current_branch = branch_result.stdout.strip() if branch_result.returncode == 0 else ""
    except Exception:
        current_branch = ""

    if current_branch and current_branch != "main":
        print(
            f"WARNING: current branch is '{current_branch}', not 'main'.",
            file=sys.stderr,
        )
        print("Backlog items are normally filed on the main branch.", file=sys.stderr)
        if sys.stdin.isatty() and os.path.exists("/dev/tty"):
            try:
                with open("/dev/tty") as tty:
                    sys.stderr.write("Proceed anyway? [y/N] ")
                    sys.stderr.flush()
                    confirm = tty.readline().strip()
            except Exception:
                confirm = ""
            if confirm.lower() not in ("y", "yes"):
                print("Aborted.", file=sys.stderr)
                sys.exit(1)
        else:
            print(
                f"WARNING: current branch is '{current_branch}', not 'main'. Proceeding (no tty).",
                file=sys.stderr,
            )
            sys.exit(1)

    # Validate feature exists via find-feature.py
    find_feature = os.path.join(
        repo_root, ".claude", "features", "contract", "scripts", "find-feature.py"
    )
    try:
        result = subprocess.run(
            ["python3", find_feature, repo_root, "lookup", args.feature_name],
            capture_output=True,
        )
        if result.returncode != 0:
            print(
                f"ERROR: feature '{args.feature_name}' not found in feature index",
                file=sys.stderr,
            )
            sys.exit(1)
    except Exception:
        print(
            f"ERROR: feature '{args.feature_name}' not found in feature index",
            file=sys.stderr,
        )
        sys.exit(1)

    # Build prefix: rabbit-cage → RABBIT-CAGE
    prefix = args.feature_name.upper()

    # Resolve canonical backlog storage path via workspace-map.py (contract)
    env = os.environ.copy()
    env["RABBIT_ROOT"] = repo_root

    # Try PATH first, then fall back to canonical contract path
    workspace_map_from_path = None
    try:
        wm_check = subprocess.run(
            ["which", "workspace-map.py"], capture_output=True, text=True
        )
        if wm_check.returncode == 0:
            workspace_map_from_path = wm_check.stdout.strip()
    except Exception:
        pass

    workspace_map = workspace_map_from_path or os.path.join(
        repo_root, ".claude", "features", "contract", "scripts", "workspace-map.py"
    )

    if not os.path.isfile(workspace_map):
        print(f"ERROR: workspace-map.py not found: {workspace_map}", file=sys.stderr)
        sys.exit(1)

    try:
        wm_result = subprocess.run(
            ["python3", workspace_map, "backlog", args.feature_name],
            capture_output=True,
            text=True,
            env=env,
        )
        if wm_result.returncode != 0:
            print(
                f"ERROR: workspace-map.py failed to resolve path for feature '{args.feature_name}'",
                file=sys.stderr,
            )
            sys.exit(1)
        backlog_root = wm_result.stdout.strip()
    except Exception as e:
        print(
            f"ERROR: workspace-map.py failed to resolve path for feature '{args.feature_name}'",
            file=sys.stderr,
        )
        sys.exit(1)

    os.makedirs(backlog_root, exist_ok=True)

    # Scan for existing items matching PREFIX-BACKLOG-<N>, find max N
    max_n = 0
    if os.path.isdir(backlog_root):
        for entry in os.listdir(backlog_root):
            if not os.path.isdir(os.path.join(backlog_root, entry)):
                continue
            # Match PREFIX-BACKLOG-<N>
            parts = entry.rsplit("-", 1)
            if len(parts) == 2 and parts[1].isdigit():
                candidate_n = int(parts[1])
                if candidate_n > max_n:
                    max_n = candidate_n

    item_num = max_n + 1
    item_id = f"{prefix}-BACKLOG-{item_num}"
    item_dir = os.path.join(backlog_root, item_id)
    item_json_path = os.path.join(item_dir, "item.json")

    if os.path.exists(item_json_path):
        print(f"ERROR: item.json already exists at {item_dir}", file=sys.stderr)
        sys.exit(1)

    try:
        os.makedirs(item_dir, exist_ok=True)
    except Exception as e:
        print(f"ERROR: failed to create {item_dir}: {e}", file=sys.stderr)
        sys.exit(1)

    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    owner = args.owner

    item = {
        "name": item_id,
        "title": args.title,
        "status": "open",
        "priority": args.priority,
        "description": "",
        "owner": owner,
        "filed": ts,
        "filed_by": owner,
        "closed": None,
        "history": [
            {
                "ts": ts,
                "actor": owner,
                "action": "opened",
                "note": "initial filing",
            }
        ],
    }

    try:
        with open(item_json_path, "w") as f:
            json.dump(item, f, indent=2)
            f.write("\n")
    except Exception as e:
        print(f"ERROR: failed to write item.json: {e}", file=sys.stderr)
        sys.exit(1)

    # Git commit after filing — silent on failure
    try:
        top = git_toplevel(item_dir)
        if top:
            subprocess.run(
                ["git", "-C", top, "add", item_json_path],
                capture_output=True,
            )
            subprocess.run(
                [
                    "git",
                    "-C",
                    top,
                    "commit",
                    "-m",
                    f"backlog: file {item_id} ({args.title})",
                ],
                capture_output=True,
            )
    except Exception:
        pass

    print(item_dir)
    sys.exit(0)


if __name__ == "__main__":
    main()
