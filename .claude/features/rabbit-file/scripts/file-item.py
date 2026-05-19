#!/usr/bin/env python3
import argparse
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

    # BACKLOG-7: sanitize then per-field length-validate BEFORE consuming an
    # ID slot. The sanitized value is what gets persisted.
    args.title = branch_ops.sanitize_text(args.title)
    args.description = branch_ops.sanitize_text(args.description)
    try:
        branch_ops.validate_field_length(
            "title", args.title, branch_ops.MAX_TITLE_LEN)
        branch_ops.validate_field_length(
            "description", args.description, branch_ops.MAX_DESCRIPTION_LEN)
    except ValueError as e:
        sys.stderr.write(f"ERROR: {e}\n")
        sys.exit(1)

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
    except Exception as e:
        # BUG-10: roll back the ID slot so it is not burned. release_id is
        # best-effort: it only decrements the counter if no other allocation
        # has happened above us. We always surface the original commit error
        # to the user; rollback outcome goes to stderr for auditability.
        try:
            released = branch_ops.release_id(args.feature, args.type_, id_str)
            if released:
                print(
                    f"NOTE: rolled back unused ID slot {id_str} "
                    f"after commit_item failed.",
                    file=sys.stderr,
                )
            else:
                print(
                    f"NOTE: did not roll back {id_str} (slot already "
                    f"consumed by another allocation).",
                    file=sys.stderr,
                )
        except Exception as rb_err:  # pragma: no cover - best-effort
            print(
                f"WARNING: release_id raised during rollback of {id_str}: "
                f"{type(rb_err).__name__}: {rb_err}",
                file=sys.stderr,
            )
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)

    print(f"Filed: {id_str}  sha: {sha}")


if __name__ == "__main__":
    main()
