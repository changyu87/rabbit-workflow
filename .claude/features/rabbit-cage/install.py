#!/usr/bin/env python3
"""install.py — copy rabbit-workflow into a target workspace.

Usage:
  install.py [TARGET] [--all]

  TARGET   directory to install into (default: $PWD)
  --all    also copy archive material (archive/, test/) for inspection.
           Without --all, dev-only docs under .claude/docs/specs/ and
           .claude/docs/plans/ are stripped; default install is .claude/
           + CLAUDE.md only.

After copying, install.py enumerates every <target>/.claude/features/*/
feature.json and invokes each declared MANIFEST API via
contract.lib.publish. Failures are reported to stderr; the install
exits non-zero if any publish call failed.

Version: 5.0.0
Owner: rabbit-workflow team (rabbit-cage)
Deprecation criterion: when Claude Code exposes native workspace
    bootstrap that subsumes this script.
"""

import glob
import json
import os
import shutil
import subprocess
import sys
import tempfile
import urllib.request


def usage():
    print(__doc__, file=sys.stderr)


def run_publish_loop(target_root: str) -> int:
    """Enumerate every <target_root>/.claude/features/*/feature.json and
    invoke each MANIFEST API via contract.lib.publish. Continues past
    failures; returns the count of failed calls (0 == success).

    Skips features with status == 'retired' and features with no manifest.
    Writes one stderr line per failure naming the feature + API.
    """
    contract_dir = os.path.join(target_root, ".claude/features/contract")
    if contract_dir not in sys.path:
        sys.path.insert(0, contract_dir)
    try:
        from lib import publish  # noqa: PLC0415
    except ImportError as e:
        sys.stderr.write(f"install: cannot import contract.lib.publish: {e}\n")
        return 1

    features_root = os.path.join(target_root, ".claude/features")
    if not os.path.isdir(features_root):
        return 0

    failures = 0
    for name in sorted(os.listdir(features_root)):
        fdir = os.path.join(features_root, name)
        fj = os.path.join(fdir, "feature.json")
        if not os.path.isfile(fj):
            continue
        try:
            with open(fj) as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError) as e:
            sys.stderr.write(f"install: {name}: malformed feature.json: {e}\n")
            failures += 1
            continue
        if not isinstance(data, dict) or data.get("status") == "retired":
            continue
        manifest = data.get("manifest") or []
        for entry in manifest:
            api_name = entry.get("api", "")
            args = entry.get("args") or {}
            fn = getattr(publish, api_name, None)
            if fn is None:
                sys.stderr.write(
                    f"install: {name}: unknown publish API {api_name!r}\n")
                failures += 1
                continue
            try:
                result = fn(**args, feature_dir=fdir, repo_root=target_root)
            except Exception as e:  # noqa: BLE001
                sys.stderr.write(
                    f"install: {name}::{api_name} raised: {e}\n")
                failures += 1
                continue
            if not getattr(result, "passed", False):
                for msg in getattr(result, "messages", []) or []:
                    sys.stderr.write(f"install: {name}::{api_name}: {msg}\n")
                failures += 1
    return failures


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
            "If developing rabbit-workflow, no install needed - open this directory in Claude Code.",
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

    target_claude = os.path.join(target, ".claude")
    try:
        shutil.copytree(os.path.join(src, ".claude"), target_claude)
        try:
            failures = run_publish_loop(target)
            if failures:
                raise RuntimeError(
                    f"{failures} manifest publish call(s) failed; see stderr")
        except Exception:
            shutil.rmtree(target_claude, ignore_errors=True)
            raise

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
            for pattern in ("specs/*.md", "plans/*.md"):
                for f in glob.glob(os.path.join(target, ".claude", "docs", pattern)):
                    os.remove(f)
            print(f"rabbit-workflow installed to {target} (minimal: .claude/ + CLAUDE.md only)")
    finally:
        if tmp_dir:
            shutil.rmtree(tmp_dir, ignore_errors=True)


if __name__ == "__main__":
    main()
