#!/usr/bin/env bash
# workspace-tree.sh — print annotated workspace hierarchy
# Usage:
#   workspace-tree.sh          # structural view (dirs + key files only)
#   workspace-tree.sh --full   # all files (excl .swp, .git/*, .rbt-prompt-counter)
set -u

REPO_ROOT="${RABBIT_ROOT:-$(git rev-parse --show-toplevel 2>/dev/null)}"
FULL=0
[ "${1:-}" = "--full" ] && FULL=1

python3 - "$REPO_ROOT" "$FULL" <<'PYEOF'
import sys
import os

repo_root = sys.argv[1]
full_mode = sys.argv[2] == "1"

# Annotations for known structural nodes (matched against basename or relative path)
ANNOTATIONS = {
    "CLAUDE.md":              "session policy anchor (@-imports policy files)",
    "README.md":              "project overview",
    "install.sh":             "wires symlinks from features/ to .claude/",
    ".claude":                "Claude Code surface (mostly symlinks to features/)",
    ".claude/":               "Claude Code surface (mostly symlinks to features/)",
    "settings.json":          "hooks and env — symlinked from rabbit-cage",
    "hooks":                  "SessionStart, UserPromptSubmit, PreToolUse hooks",
    "hooks/":                 "SessionStart, UserPromptSubmit, PreToolUse hooks",
    "commands":               "slash commands (/rabbit-*)",
    "commands/":              "slash commands (/rabbit-*)",
    "skills":                 "skill library",
    "skills/":                "skill library",
    "features":               "all feature source directories (rabbit-cage, contract, policy, tdd-state-machine, ...)",
    "features/":              "all feature source directories (rabbit-cage, contract, policy, tdd-state-machine, ...)",
    "rabbit-cage":            "owns the Claude Code surface: skills, hooks, commands, scope-guard",
    "rabbit-cage/":           "owns the Claude Code surface: skills, hooks, commands, scope-guard",
    "contract":               "dispatch scripts, enforcement, templates",
    "contract/":              "dispatch scripts, enforcement, templates",
    "policy":                 "philosophy, spec-rules, coding-rules, workflow-rules",
    "policy/":                "philosophy, spec-rules, coding-rules, workflow-rules",
    "tdd-state-machine":      "tdd-step.sh forward-only state machine",
    "tdd-state-machine/":     "tdd-step.sh forward-only state machine",
    "feature.json":           "feature manifest: owner, tdd_state, surface, deprecation_criterion",
    "docs/spec":              "spec and contract for this feature",
    "docs/spec/":             "spec and contract for this feature",
    "registry.json":          "feature registry (name → path map)",
    "SKILL.md":               "skill definition",
    "backlog-contract.md":    "backlog item contract",
    "bugs":                   "centralized bug tracker (.claude/bugs, subdirs by feature name)",
    "backlogs":               "centralized backlog tracker (.claude/backlogs, subdirs by feature name)",
    "rabbit-bug":             "bug filing, tracking, and lifecycle (file-bug.sh, bug-status.sh, list-bugs.sh)",
    "rabbit-bug/":            "bug filing, tracking, and lifecycle (file-bug.sh, bug-status.sh, list-bugs.sh)",
    "rabbit-backlog":         "backlog item filing and lifecycle (file-backlog-item.sh, backlog-item-status.sh)",
    "rabbit-backlog/":        "backlog item filing and lifecycle (file-backlog-item.sh, backlog-item-status.sh)",
}

# Structural directory names to always include in default mode
STRUCTURAL_DIRS = {
    "features", "docs", "bugs", "spec", "backlog", "backlogs",
    "commands", "hooks", "skills", "agents", "scripts",
    "test", "enforcement", ".claude",
    # feature-named dirs
    "rabbit-cage", "contract", "policy", "tdd-state-machine",
    "rabbit-bug", "rabbit-backlog",
}

# Key filenames always included in default mode
KEY_FILES = {
    "CLAUDE.md", "README.md", "install.sh", "feature.json",
    "registry.json", "settings.json", "project-map.json",
    "bug.json", "item.json", "SKILL.md", "backlog-contract.md",
}


def is_structural_dir(name):
    return name in STRUCTURAL_DIRS


def is_key_file(name, relpath):
    if name in KEY_FILES:
        return True
    # *.md files in docs/spec/
    if name.endswith(".md") and "/docs/spec" in ("/" + relpath):
        return True
    if name.endswith(".md") and "docs/spec" in relpath:
        return True
    # *.sh scripts
    if name.endswith(".sh"):
        return True
    # bug.json anywhere (already covered), item.json (already covered)
    # RABBIT-CAGE-* dirs are structural — handled in dir check
    return False


def is_bug_dir(name):
    # Matches RABBIT-CAGE-12, RABBIT-CAGE-BACKLOG-1, etc.
    import re
    return bool(re.match(r'^[A-Z][A-Z-]+-\d+$', name))


def annotation_for(name, relpath):
    # Try relpath-based match first
    for key, ann in ANNOTATIONS.items():
        if relpath == key or relpath == key.rstrip("/") or relpath == key.rstrip("/") + "/":
            return ann
    # Try basename match
    basename = os.path.basename(relpath.rstrip("/"))
    for key, ann in ANNOTATIONS.items():
        if basename == key.rstrip("/"):
            return ann
    return None


def should_skip_full(name, dirpath):
    if name.endswith(".swp"):
        return True
    if name == ".rbt-prompt-counter":
        return True
    return False


def should_skip_path_full(relpath):
    parts = relpath.replace("\\", "/").split("/")
    if ".git" in parts:
        return True
    return False


def build_tree(root):
    """
    Returns list of (indent_level, is_last, name, relpath, is_dir) tuples,
    depth-first, representing the tree to display.
    """
    entries = []

    def walk(dirpath, relbase, depth, parent_name=""):
        try:
            items = sorted(os.listdir(dirpath))
        except PermissionError:
            return

        # Separate dirs and files, apply filtering
        dirs = []
        files = []
        for item in items:
            item_path = os.path.join(dirpath, item)
            item_rel = os.path.join(relbase, item).lstrip("./").lstrip("/")
            if relbase == "":
                item_rel = item

            is_dir = os.path.isdir(item_path)

            if full_mode:
                if should_skip_full(item, dirpath):
                    continue
                if should_skip_path_full(item_rel):
                    continue
                if is_dir:
                    dirs.append((item, item_path, item_rel))
                else:
                    files.append((item, item_path, item_rel))
            else:
                # Default mode: structural filter
                if item == ".rbt-prompt-counter":
                    continue
                if is_dir:
                    # Skip .git
                    if item == ".git":
                        continue
                    # Include all child dirs when parent is a structural dir
                    # (e.g. skills/ → rabbit-feature-touch/, rabbit-workspace/)
                    if is_structural_dir(parent_name) or is_structural_dir(item) or is_bug_dir(item):
                        dirs.append((item, item_path, item_rel))
                else:
                    if is_key_file(item, item_rel):
                        files.append((item, item_path, item_rel))

        all_items = [(n, p, r, True) for n, p, r in dirs] + \
                    [(n, p, r, False) for n, p, r in files]

        for i, (name, item_path, item_rel, is_dir) in enumerate(all_items):
            is_last = (i == len(all_items) - 1)
            entries.append((depth, is_last, name, item_rel, is_dir))
            if is_dir:
                walk(item_path, item_rel, depth + 1, parent_name=name)

    walk(root, "", 0)
    return entries


def render_tree(root, entries):
    # Track whether each level's parent is the last child (to decide │ vs space)
    # We need to track for each depth whether the last entry at that depth has been passed
    # Use a stack of booleans: last_flags[depth] = True means the current ancestor at that depth is the last child
    last_flags = []

    # Print root
    root_name = os.path.basename(root.rstrip("/"))
    ann = annotation_for(root_name, "")
    suffix = f"  # {ann}" if ann else ""
    print(f"{root_name}/{suffix}")

    # We need to know for each depth what the last-child status is
    # as we traverse. Build prefix based on last_flags up to depth-1.
    depth_last = {}  # depth -> is_last for the most recent entry at that depth

    for depth, is_last, name, relpath, is_dir in entries:
        # Update depth_last
        depth_last[depth] = is_last
        # Clean up deeper levels (no longer relevant)
        for d in list(depth_last.keys()):
            if d > depth:
                del depth_last[d]

        # Build prefix: for each level 0..depth-1, check if that level's entry was last
        prefix = ""
        for d in range(depth):
            if depth_last.get(d, False):
                prefix += "    "
            else:
                prefix += "│   "

        connector = "└── " if is_last else "├── "

        display_name = name + "/" if is_dir else name
        ann = annotation_for(name, relpath)
        suffix = f"  # {ann}" if ann else ""

        print(f"{prefix}{connector}{display_name}{suffix}")


entries = build_tree(repo_root)
render_tree(repo_root, entries)
PYEOF
