#!/usr/bin/env python3
"""dispatch-spec-creator.py — assemble the rabbit-spec-creator subagent prompt.

The INPUT ASSEMBLER for the rabbit-spec-creator subagent: an orchestrator
(rabbit-decompose's downstream pipeline, rabbit-feature) runs this script to
build the subagent's prompt, then dispatches `rabbit-spec-creator` directly.
The subagent itself reads the matched code and WRITES the feature's
docs/spec.md, returning only a {path_written, summary} handoff. This script
resolves the declared path globs, caps the resolved file list at 50 entries,
and invokes contract/scripts/build-prompt.py to assemble the prompt.

When the resolved file count exceeds the cap, the truncation is NOT silent
(#472): a structured NOTE naming the inspected and dropped counts is written
to stderr so the orchestrator can surface "and M dropped" to the user instead
of silently building a prompt over an incomplete file list. stdout stays a
single prompt-file path the orchestrator parses.

The assembled prompt is pinned to the CANONICAL single-`.rabbit` runtime root
(#1066) via rabbit-cage's `rabbit_runtime_root` resolver (Inv 52). In a
vendored install the session exports `RABBIT_ROOT=<host>/.rabbit`, and
contract/scripts/build-prompt.py unconditionally joins `<repo_root>/.rabbit/
prompts/...` — so left alone it writes to the DOUBLED
`<host>/.rabbit/.rabbit/prompts/...` tree, splitting prompts off the runtime
root every other writer/reader uses. After build-prompt.py returns, this
script relocates the prompt under `<rabbit_runtime_root(repo_root)>/prompts/`
when build-prompt wrote it elsewhere, and prints that canonical path. The
relocation is idempotent: in standalone mode build-prompt already writes the
canonical path and no move occurs.

Both modes are supported:
  - Plugin mode: --paths populated with code globs the agent reads from.
  - Standalone mode: --paths empty (or omitted) — agent produces a skeleton.

Usage:
    dispatch-spec-creator.py --feature-name <name> [--paths <glob1>,<glob2>,...]

Prints the absolute path of the assembled prompt file to stdout on success.

Exit codes:
    0 = success
    1 = invocation error (missing args, glob resolution failure)
    2 = build-prompt.py subprocess failure

Version: 2.1.0
Owner: rabbit-workflow team
Deprecation criterion: when Claude Code exposes native spec-lifecycle skills that supersede this feature
"""

import argparse
import glob
import os
import shutil
import subprocess
import sys
from pathlib import Path

MAX_FILES = 50


def _rabbit_runtime_root(repo_root):
    """Resolve the canonical single-`.rabbit` runtime root for `repo_root`
    via rabbit-cage's `rabbit_runtime_root` resolver (Inv 52), lazy-imported
    from the install's feature lib using the same importlib.util pattern
    rabbit-cage's session-start dispatcher uses (#1046).

    Falls back to the inline basename rule when the resolver cannot be
    imported (degenerate / partial install) so the prompt still lands on a
    single-`.rabbit` path.
    """
    resolver_path = (
        Path(repo_root) / ".claude" / "features" / "rabbit-cage"
        / "lib" / "runtime_root.py"
    )
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "rabbit_cage_runtime_root", str(resolver_path))
        if spec is not None and spec.loader is not None:
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            return module.rabbit_runtime_root(str(repo_root))
    except (FileNotFoundError, ImportError, AttributeError, OSError):
        pass
    rp = os.path.normpath(str(repo_root))
    return rp if os.path.basename(rp) == ".rabbit" else os.path.join(rp, ".rabbit")


def main():
    parser = argparse.ArgumentParser(description="Assemble the rabbit-spec-creator subagent prompt")
    parser.add_argument("--feature-name", required=True, help="Feature name (kebab-case)")
    parser.add_argument("--paths", default="", help="Comma-separated path globs (empty in standalone mode)")
    args = parser.parse_args()

    globs = [g.strip() for g in args.paths.split(",") if g.strip()]

    resolved = []
    for g in globs:
        resolved.extend(glob.glob(g, recursive=True))
    resolved = sorted(set(resolved))
    total = len(resolved)
    if total > MAX_FILES:
        # The cap is kept (it bounds the prompt's slot budget), but the loss
        # is reported loudly — never a silent alphabetical truncation (#472).
        dropped = total - MAX_FILES
        resolved = resolved[:MAX_FILES]
        print(
            f"NOTE: resolved {total} files; capped at {MAX_FILES}, "
            f"{dropped} dropped",
            file=sys.stderr,
        )

    # Resolve repo_root via __file__ — mode-agnostic. See spec Inv 3(e):
    # parents[0]=scripts, [1]=rabbit-spec, [2]=features, [3]=.claude, [4]=repo_root.
    # `git rev-parse` and `os.getcwd()` are forbidden here because in plugin
    # mode they resolve to the user-project root, not the rabbit root.
    repo_root = str(Path(__file__).resolve().parents[4])

    build_prompt = os.path.join(repo_root, ".claude/features/contract/scripts/build-prompt.py")

    cmd = [
        "python3", build_prompt,
        "--callable-id", "spec-create",
        "--slot", f"feature_name={args.feature_name}",
        "--slot", f"paths_globs={','.join(globs)}",
        "--slot", f"paths_resolved={chr(10).join(resolved)}",
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"error: build-prompt.py failed (exit {result.returncode}):", file=sys.stderr)
        print(result.stderr, file=sys.stderr)
        return 2

    built_path = result.stdout.strip()

    # Pin the prompt to the canonical single-`.rabbit` runtime root (#1066).
    # build-prompt.py joins `<its repo_root>/.rabbit/prompts/...`; in a vendored
    # install where RABBIT_ROOT is already `<host>/.rabbit` that doubles to
    # `<host>/.rabbit/.rabbit/prompts/...`. Relocate to the canonical dir when
    # build-prompt wrote elsewhere; in standalone mode the two paths coincide
    # and no move occurs.
    canonical_dir = os.path.join(_rabbit_runtime_root(repo_root), "prompts")
    if os.path.normpath(os.path.dirname(built_path)) != os.path.normpath(canonical_dir):
        os.makedirs(canonical_dir, exist_ok=True)
        canonical_path = os.path.join(canonical_dir, os.path.basename(built_path))
        shutil.move(built_path, canonical_path)
        built_path = canonical_path

    print(built_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
