#!/usr/bin/env python3
# workspace-tree.py — print annotated workspace hierarchy
# Usage:
#   workspace-tree.py [REPO_ROOT]            # structural view (dirs + key files only)
#   workspace-tree.py [REPO_ROOT] --full     # all files (excl .swp, .git/*, .rabbit-prompt-counter)

import json
import os
import subprocess
import sys


def _resolve_args():
    args = sys.argv[1:]
    full = False
    repo = None
    for a in args:
        if a == "--full":
            full = True
        elif not a.startswith("--") and repo is None:
            repo = a
        else:
            sys.stderr.write(f"workspace-tree: unknown arg '{a}'\n")
            sys.exit(2)
    if not repo:
        repo = os.environ.get("RABBIT_ROOT")
    if not repo:
        try:
            repo = subprocess.check_output(
                ["git", "rev-parse", "--show-toplevel"],
                stderr=subprocess.DEVNULL,
            ).decode().strip()
        except Exception:
            repo = ""
    return repo, full


repo_root, full_mode = _resolve_args()

ANNOTATIONS = {
    "CLAUDE.md":              "session policy anchor (@-imports policy files)",
    "README.md":              "project overview",
    "install.py":             "bootstrap installer — copies rabbit-workflow into a target workspace",
    ".claude":                "Claude Code surface (mostly symlinks to features/)",
    ".claude/":               "Claude Code surface (mostly symlinks to features/)",
    "settings.json":          "hooks and env — symlinked from rabbit-cage",
    "hooks":                  "SessionStart, UserPromptSubmit, PreToolUse hooks",
    "hooks/":                 "SessionStart, UserPromptSubmit, PreToolUse hooks",
    "commands":               "slash commands (/rabbit-*)",
    "commands/":              "slash commands (/rabbit-*)",
    "skills":                 "skill library",
    "skills/":                "skill library",
    "features":               "all feature source directories (rabbit-cage, contract, policy, tdd-subagent, ...)",
    "features/":              "all feature source directories (rabbit-cage, contract, policy, tdd-subagent, ...)",
    "rabbit-cage":            "owns the Claude Code surface: skills, hooks, commands, scope-guard",
    "rabbit-cage/":           "owns the Claude Code surface: skills, hooks, commands, scope-guard",
    "contract":               "dispatch scripts, enforcement, templates",
    "contract/":              "dispatch scripts, enforcement, templates",
    "policy":                 "philosophy, spec-rules, coding-rules",
    "policy/":                "philosophy, spec-rules, coding-rules",
    "tdd-subagent":           "TDD subagent dispatch protocol (dispatch-tdd-subagent.py) + tdd-step.py forward-only state machine",
    "tdd-subagent/":          "TDD subagent dispatch protocol (dispatch-tdd-subagent.py) + tdd-step.py forward-only state machine",
    "feature.json":           "feature manifest: owner, tdd_state, surface, deprecation_criterion",
    "docs/spec":              "spec and contract for this feature",
    "docs/spec/":             "spec and contract for this feature",
    "registry.json":          "feature registry (name -> path map)",
    "SKILL.md":               "skill definition",
    "backlog-contract.md":    "backlog item contract",
    "bugs":                   "centralized bug tracker (.claude/bugs, subdirs by feature name)",
    "backlogs":               "centralized backlog tracker (.claude/backlogs, subdirs by feature name)",
    "rabbit-file":            "bug/backlog item filing and lifecycle (file-item.py, item-status.py, list-items.py)",
    "rabbit-file/":           "bug/backlog item filing and lifecycle (file-item.py, item-status.py, list-items.py)",
    "rabbit-feature":         "feature lifecycle orchestration (new, touch, scope resolution, spec authoring)",
    "rabbit-feature/":        "feature lifecycle orchestration (new, touch, scope resolution, spec authoring)",
}

STRUCTURAL_DIRS = {
    "features", "docs", "bugs", "spec", "backlog", "backlogs",
    "commands", "hooks", "skills", "agents", "scripts",
    "test", "enforcement", ".claude",
    "rabbit-cage", "contract", "policy",
    "tdd-subagent",
    "rabbit-file", "rabbit-feature",
}

KEY_FILES = {
    "CLAUDE.md", "README.md", "install.py", "feature.json",
    "registry.json", "settings.json", "project-map.json",
    "bug.json", "item.json", "SKILL.md", "backlog-contract.md",
}


def is_structural_dir(name):
    return name in STRUCTURAL_DIRS


def is_key_file(name, relpath):
    if name in KEY_FILES:
        return True
    if name.endswith(".md") and "/docs/spec" in ("/" + relpath):
        return True
    if name.endswith(".md") and "docs/spec" in relpath:
        return True
    return False


def is_bug_dir(name):
    import re
    return bool(re.match(r'^[A-Z][A-Z-]+-\d+$', name))


def retired_tag_for(item_path, is_dir):
    """Return ' [RETIRED]' if item_path is a feature dir whose feature.json
    declares status == 'retired'; otherwise ''. RABBIT-CAGE-BACKLOG-23.
    """
    if not is_dir:
        return ""
    fj = os.path.join(item_path, "feature.json")
    if not os.path.isfile(fj):
        return ""
    try:
        with open(fj) as f:
            data = json.load(f)
    except (OSError, ValueError):
        return ""
    if data.get("status") == "retired":
        return "  [RETIRED]"
    return ""


def annotation_for(name, relpath):
    for key, ann in ANNOTATIONS.items():
        if relpath == key or relpath == key.rstrip("/") or relpath == key.rstrip("/") + "/":
            return ann
    basename = os.path.basename(relpath.rstrip("/"))
    for key, ann in ANNOTATIONS.items():
        if basename == key.rstrip("/"):
            return ann
    return None


def should_skip_full(name, dirpath):
    if name.endswith(".swp"):
        return True
    if name == ".rabbit-prompt-counter":
        return True
    return False


def should_skip_path_full(relpath):
    parts = relpath.replace("\\", "/").split("/")
    if ".git" in parts:
        return True
    return False


def build_tree(root):
    entries = []

    def walk(dirpath, relbase, depth, parent_name=""):
        try:
            items = sorted(os.listdir(dirpath))
        except PermissionError:
            return

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
                if item == ".rabbit-prompt-counter":
                    continue
                if is_dir:
                    if item == ".git":
                        continue
                    if is_structural_dir(parent_name) or is_structural_dir(item) or is_bug_dir(item):
                        dirs.append((item, item_path, item_rel))
                else:
                    if is_key_file(item, item_rel):
                        files.append((item, item_path, item_rel))

        all_items = [(n, p, r, True) for n, p, r in dirs] + \
                    [(n, p, r, False) for n, p, r in files]

        for i, (name, item_path, item_rel, is_dir) in enumerate(all_items):
            is_last = (i == len(all_items) - 1)
            entries.append((depth, is_last, name, item_rel, is_dir, item_path))
            if is_dir:
                walk(item_path, item_rel, depth + 1, parent_name=name)

    walk(root, "", 0)
    return entries


def render_tree(root, entries):
    depth_last = {}

    root_name = os.path.basename(root.rstrip("/"))
    ann = annotation_for(root_name, "")
    suffix = f"  # {ann}" if ann else ""
    print(f"{root_name}/{suffix}")

    for depth, is_last, name, relpath, is_dir, item_path in entries:
        depth_last[depth] = is_last
        for d in list(depth_last.keys()):
            if d > depth:
                del depth_last[d]

        prefix = ""
        for d in range(depth):
            if depth_last.get(d, False):
                prefix += "    "
            else:
                prefix += "│   "

        connector = "└── " if is_last else "├── "

        display_name = name + "/" if is_dir else name
        retired = retired_tag_for(item_path, is_dir)
        ann = annotation_for(name, relpath)
        suffix = f"  # {ann}" if ann else ""

        print(f"{prefix}{connector}{display_name}{retired}{suffix}")


entries = build_tree(repo_root)
render_tree(repo_root, entries)
