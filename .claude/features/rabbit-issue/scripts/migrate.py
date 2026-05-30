#!/usr/bin/env python3
"""rabbit-issue: ONE-SHOT migration from origin/bug-backlog-files to GH Issues + archive/.

Walks every `rabbit/features/<feature>/{bugs,backlogs}/<ID>/item.json` on
the dedicated `origin/bug-backlog-files` branch (never checked out — read
via `git ls-tree` + `git show`). For each item:

  - open  → file a new GH Issue via `gh issue create` with the rabbit
            label set; record old_id → new_number in the manifest.
  - close → copy item.json verbatim to
            `archive/bug-backlog/<feature>/<old-id>.json`; record in
            manifest.

Idempotent: a second run consults `archive/migration-manifest.json` and
skips items already migrated.

`--dry-run` performs ZERO writes (no GH calls, no archive files, no
manifest write) — it just reports the counts that would be migrated.

The script prints a `READY TO DELETE BRANCH` footer with the exact
`git push origin --delete bug-backlog-files` command but DOES NOT
execute it — branch deletion stays user-gated.

Version: 1.0.0
Owner: cyxu
Deprecation criterion: deleted immediately after cutover commit lands on main
"""
import argparse
import datetime
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _gh import ensure_labels, repo_slug, require_auth  # noqa: E402

BRANCH = "origin/bug-backlog-files"
ARCHIVE_DIR = Path("archive/bug-backlog")
MANIFEST = Path("archive/migration-manifest.json")


def walk_items():
    """Yield (feature, type_old, item_id, body_dict) for each item.json on the branch.

    Only paths matching `rabbit/features/<feature>/<bugs|backlogs>/<ID>/item.json`
    are yielded; any other entries on the branch are silently ignored.
    """
    out = subprocess.check_output(
        ["git", "ls-tree", "-r", "--name-only", BRANCH], text=True,
    )
    for path in out.strip().split("\n"):
        if not path.endswith("/item.json"):
            continue
        parts = path.split("/")
        # rabbit / features / <feature> / <types> / <ID> / item.json -> 6 parts
        if len(parts) != 6 or parts[0] != "rabbit" or parts[1] != "features":
            continue
        feature, types_dir, item_id = parts[2], parts[3], parts[4]
        if types_dir == "bugs":
            type_old = "bug"
        elif types_dir == "backlogs":
            type_old = "backlog"
        else:
            continue
        body = subprocess.check_output(
            ["git", "show", "{}:{}".format(BRANCH, path)], text=True,
        )
        yield feature, type_old, item_id, json.loads(body)


def map_type(type_old):
    """Map old rabbit type → new GH-default label."""
    return "bug" if type_old == "bug" else "enhancement"


def load_manifest():
    if MANIFEST.exists():
        return json.loads(MANIFEST.read_text())
    return {"open_items": [], "closed_items": []}


def already_migrated(manifest, key, old_id):
    return any(entry["old_id"] == old_id for entry in manifest[key])


def dry_run():
    open_n = closed_n = 0
    for _feature, _t_old, _item_id, body in walk_items():
        status = body.get("status")
        if status == "open":
            open_n += 1
        elif status == "close":
            closed_n += 1
    print("DRY RUN")
    print("  open items:   {}".format(open_n))
    print("  closed items: {}".format(closed_n))
    print("  archive root: {}".format(ARCHIVE_DIR))
    print("  branch:       {}".format(BRANCH))


def real_migrate():
    require_auth()
    manifest = load_manifest()
    open_log = list(manifest["open_items"])
    closed_log = list(manifest["closed_items"])
    slug = repo_slug()
    for feature, type_old, item_id, body in walk_items():
        status = body.get("status")
        if status == "open":
            if already_migrated(manifest, "open_items", item_id):
                continue
            type_new = map_type(type_old)
            priority = body.get("priority", "medium")
            labels = [
                type_new, "rabbit-managed",
                "feature:{}".format(feature),
                "priority:{}".format(priority),
            ]
            ensure_labels(labels)
            url = subprocess.check_output(
                ["gh", "issue", "create", "-R", slug,
                 "--title", body["title"],
                 "--body", body.get("description", ""),
                 "--label", ",".join(labels)],
                text=True,
            ).strip()
            number = int(url.rsplit("/", 1)[-1])
            open_log.append(
                {"old_id": item_id, "new_number": number, "url": url}
            )
            print("  open  {} -> #{}".format(item_id, number))
        elif status == "close":
            if already_migrated(manifest, "closed_items", item_id):
                continue
            dest = ARCHIVE_DIR / feature / "{}.json".format(item_id)
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(json.dumps(body, indent=2))
            closed_log.append(
                {"old_id": item_id, "archive_path": str(dest)}
            )
            print("  close {} -> {}".format(item_id, dest))

    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST.write_text(json.dumps({
        "migrated_at": datetime.datetime.utcnow().isoformat() + "Z",
        "rabbit_workflow_repo": slug,
        "old_branch": "bug-backlog-files",
        "open_items": open_log,
        "closed_items": closed_log,
    }, indent=2))
    print("\nManifest: {}".format(MANIFEST))
    print("\n*** READY TO DELETE BRANCH (gated on user approval):")
    print("    git push origin --delete bug-backlog-files")


def main():
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("--dry-run", action="store_true",
                   help="Report counts only; perform zero writes.")
    args = p.parse_args()
    if args.dry_run:
        dry_run()
    else:
        real_migrate()


if __name__ == "__main__":
    main()
