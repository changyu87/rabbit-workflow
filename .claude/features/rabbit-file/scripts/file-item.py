#!/usr/bin/env python3
import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import branch_ops

VALID_PRIORITIES = {"low", "medium", "high", "critical"}
VALID_TYPES = {"bug", "backlog"}


def _git_user():
    r = subprocess.run(["git", "config", "user.name"], capture_output=True, text=True)
    return r.stdout.strip() or "unknown"


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--type", dest="type_", required=True, choices=list(VALID_TYPES))
    p.add_argument("--feature", required=True)
    p.add_argument("--title", required=True)
    p.add_argument("--priority", required=True, choices=sorted(VALID_PRIORITIES))
    p.add_argument("--description", required=True)
    p.add_argument("--filed-by")
    args = p.parse_args()

    filed_by = args.filed_by or _git_user()
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    try:
        id_str = branch_ops.allocate_id(args.feature, args.type_)
    except RuntimeError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)

    item = {
        "name": id_str,
        "type": args.type_,
        "title": args.title,
        "status": "open",
        "priority": args.priority,
        "description": args.description,
        "related_feature": args.feature,
        "filed": now,
        "filed_by": filed_by,
        "closed": None,
        "history": [{"ts": now, "actor": filed_by, "action": "opened", "note": "initial filing"}],
    }

    try:
        sha = branch_ops.commit_item(args.feature, args.type_, id_str, item)
    except RuntimeError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)
    print(f"Filed: {id_str}  sha: {sha}")


if __name__ == "__main__":
    main()
