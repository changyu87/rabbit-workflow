#!/usr/bin/env python3
# install.py — copy rabbit-workflow into a target workspace.
#
# Usage:
#   install.py [TARGET] [--all]
#
#   TARGET   directory to install into (default: $PWD)
#   --all    also copy archive material (archive/, test/) — useful for fans
#            / contributors who want a closer look at how rabbit is built.
#            Without --all, dev-only docs under .claude/docs/specs/ and
#            .claude/docs/plans/ are stripped from the installed tree;
#            default install is .claude/ + CLAUDE.md only.
#
# The runtime work model is identical regardless of --all. The flag only
# affects which files come along for inspection; rabbit's behavior in the
# installed workspace is unchanged.

import glob
import os
import shutil
import subprocess
import sys
import tempfile
import urllib.request


def usage():
    lines = []
    in_header = False
    with open(__file__) as f:
        for i, line in enumerate(f):
            if i == 0:
                continue  # skip shebang
            if line.startswith("# "):
                lines.append(line[2:].rstrip())
                in_header = True
            elif in_header:
                break
    print("\n".join(lines), file=sys.stderr)


def main():
    target = ""
    install_all = False

    i = 1
    while i < len(sys.argv):
        arg = sys.argv[i]
        if arg == "--all":
            install_all = True
        elif arg in ("-h", "--help"):
            usage()
            sys.exit(0)
        elif arg.startswith("-"):
            print(f"Error: unknown option '{arg}'", file=sys.stderr)
            sys.exit(2)
        else:
            if target:
                print("Error: multiple TARGET values given", file=sys.stderr)
                sys.exit(2)
            target = arg
        i += 1

    if not target:
        target = os.getcwd()

    if os.path.isdir(os.path.join(target, ".claude")):
        print(f"Error: {target}/.claude already exists.", file=sys.stderr)
        print(
            "If developing rabbit-workflow, no install needed — open this directory in Claude Code.",
            file=sys.stderr,
        )
        sys.exit(1)

    script_dir = os.path.dirname(os.path.abspath(__file__))
    tmp_dir = None

    if os.path.isdir(os.path.join(script_dir, ".claude")):
        src = script_dir
    else:
        tmp_dir = tempfile.mkdtemp()
        url = "https://github.com/changyu87/rabbit-workflow/archive/refs/heads/main.tar.gz"
        tar_path = os.path.join(tmp_dir, "rabbit.tar.gz")
        try:
            urllib.request.urlretrieve(url, tar_path)
            subprocess.check_call(
                ["tar", "-xz", "-C", tmp_dir, "--strip-components=1", "-f", tar_path]
            )
        except Exception as e:
            print(f"Error downloading rabbit-workflow: {e}", file=sys.stderr)
            shutil.rmtree(tmp_dir, ignore_errors=True)
            sys.exit(1)
        src = tmp_dir

    # BUG-61: track files we created so we can roll back on failure.
    target_claude = os.path.join(target, ".claude")
    try:
        shutil.copytree(os.path.join(src, ".claude"), target_claude)
        try:
            subprocess.check_call(
                ["python3", os.path.join(target, ".claude/features/rabbit-cage/scripts/build.py"), target]
            )
        except Exception:
            # Build failed after copytree succeeded — roll back the partial
            # .claude/ tree so the operator can retry on a clean target.
            shutil.rmtree(target_claude, ignore_errors=True)
            raise

        # Always strip runtime-only and OS-level artifacts.
        settings_local = os.path.join(target, ".claude", "settings.local.json")
        if os.path.isfile(settings_local):
            os.remove(settings_local)
        for nfs in glob.glob(os.path.join(target, ".claude", ".nfs*")):
            os.remove(nfs)

        if install_all:
            for subdir in ("archive", "test"):
                src_sub = os.path.join(src, subdir)
                if os.path.isdir(src_sub):
                    shutil.copytree(src_sub, os.path.join(target, subdir))
            print(f"rabbit-workflow installed to {target} (with --all: archive/ + test/ included; .claude/docs/ kept)")
        else:
            # Default install: strip dev-only docs the user doesn't need.
            for pattern in ("specs/*.md", "plans/*.md"):
                for f in glob.glob(os.path.join(target, ".claude", "docs", pattern)):
                    os.remove(f)
            print(f"rabbit-workflow installed to {target} (minimal: .claude/ + CLAUDE.md only)")
    finally:
        if tmp_dir:
            shutil.rmtree(tmp_dir, ignore_errors=True)


if __name__ == "__main__":
    main()
