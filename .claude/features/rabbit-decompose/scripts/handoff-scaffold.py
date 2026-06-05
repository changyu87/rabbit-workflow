#!/usr/bin/env python3
"""handoff-scaffold.py — rabbit-decompose mode/root resolver + Step 4 scaffold
hand-off orchestrator.

Makes Step 1 source-root resolution and Step 4 scaffold hand-off SCRIPT-tier
(spec-rules §4 Script-Backed Orchestration; spec Invariants 5 and 6). This is
the single canonical resolver: both Step 1 (WHERE the decomposition source
lives) and Step 4 (mode-correct scaffolder dispatch) read from it, so they
cannot disagree and the model never hand-resolves an ambiguous `<repo>`.

Responsibilities:

  1. Resolve the rabbit root (from --rabbit-root, else the cwd, which in a
     rabbit session IS the mode-correct rabbit root) and DETECT MODE
     deterministically by REUSING the canonical
     resolver `rabbit-meta.lib.mode_detection.detect_mode` (lazy-imported,
     mirroring contract.lib.runtime.write_mode_marker). NOT a single
     hard-coded `<repo>/.rabbit/.runtime/mode` path read.
  2. Resolve the DECOMPOSITION SOURCE ROOT — the directory the skill points
     Glob/Read at to analyze the project:
       - plugin     -> rabbit_root.parent (the user project; the rabbit-root
                       is the vendored `.rabbit/` install dir, so the project
                       to decompose is its PARENT — matching
                       scaffold-feature.py._detect_plugin_mode, where
                       project_root = rabbit_root.parent).
       - standalone -> the rabbit root itself (the repo root).
  3. Author the batch temp file with a SCRIPT-OWNED timestamp (no
     model-assembled `<ts>`): the script owns the path and content.
  4. Dispatch the scaffolder on the mode-correct branch:
       - plugin     -> scaffold-feature.py --batch <file> (one project-map
                       mutation)
       - standalone -> emit the per-feature rabbit-feature-scaffold plan
                       (batch form is plugin-only; the dispatcher then runs
                       one `Skill("rabbit-feature-scaffold", ...)` per feature)

The spec-create seeding (Step 4 part B) stays inline in the SKILL body as
sequential `Skill(...)` calls under the two-level-nesting constraint — that is
NOT this script's job.

CLI:
  handoff-scaffold.py --features <accepted.json> [--rabbit-root <path>]
                      [--plan-only]
  handoff-scaffold.py --source-root [--rabbit-root <path>]

  --features     path to a JSON array of accepted features:
                 [{"name": "<kebab>", "globs": ["..."]}, ...]
  --rabbit-root  the rabbit root used for mode detection. Default: the cwd,
                 which in a rabbit session IS the mode-correct rabbit root —
                 the vendored `.rabbit/` directory in plugin mode, the repo
                 root in standalone mode.
  --plan-only    resolve mode + author the batch file (plugin) but do NOT
                 invoke the scaffolder; print the decision as JSON and exit 0.
                 Used by the SKILL body's dry-run and by the test.
  --source-root  Step 1 mode: resolve mode + the decomposition source root
                 ONLY (no --features required); print JSON and exit 0.

Output (always JSON on stdout):
  Step 4 (--features):
    {
      "mode": "plugin" | "standalone",
      "branch": "batch" | "per-feature",
      "batch_file": "<abs path>" | null,
      "source_root": "<abs path>",
      "features": [ {"name": ..., "globs": [...]}, ... ],
      "dispatched": <bool>          # false under --plan-only
    }
  Step 1 (--source-root):
    {
      "mode": "plugin" | "standalone",
      "source_root": "<abs path>"
    }

Exit:
  0 success (plan computed; scaffolder dispatched unless --plan-only/--source-root)
  1 scaffolder dispatch failed
  2 invocation error (bad args, unreadable/invalid features file)

Version: 0.2.0
Owner: rabbit-workflow team
Deprecation criterion: when Step 4 scaffold hand-off is provided natively by
    the rabbit CLI, retiring this companion script.
"""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path


def _err(msg: str) -> None:
    sys.stderr.write(f"ERROR: {msg}\n")


def _resolve_rabbit_meta_mode_detection() -> "callable | None":
    """Lazy-load rabbit-meta.lib.mode_detection.detect_mode.

    Walk upward from this script's own location until a
    `.claude/features/rabbit-meta/lib/mode_detection.py` is found, then load
    detect_mode via importlib (mirrors contract.lib.runtime.write_mode_marker
    and tdd-step.py's repo-root-anchored resolution; works from any copy
    depth). Returns the callable, or None when rabbit-meta is unavailable.
    """
    here = Path(__file__).resolve()
    for parent in here.parents:
        cand = (parent / ".claude" / "features" / "rabbit-meta"
                / "lib" / "mode_detection.py")
        if cand.is_file():
            try:
                spec = importlib.util.spec_from_file_location(
                    "rabbit_meta_mode_detection", str(cand))
                if spec is None or spec.loader is None:
                    return None
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                return module.detect_mode
            except (ImportError, AttributeError, OSError):
                return None
    return None


def _resolve_scaffolder() -> "Path | None":
    """Resolve rabbit-feature/scripts/scaffold-feature.py by walking upward
    from this script's location (same anchoring as the rabbit-meta resolver)."""
    here = Path(__file__).resolve()
    for parent in here.parents:
        cand = (parent / ".claude" / "features" / "rabbit-feature"
                / "scripts" / "scaffold-feature.py")
        if cand.is_file():
            return cand
    return None


def _default_rabbit_root() -> str:
    """The current working directory (#906).

    In a rabbit session the cwd IS the mode-correct rabbit root: the vendored
    `.rabbit/` install dir in plugin mode and the repo root in standalone
    mode — exactly what `detect_mode` requires (it returns `plugin` only when
    the rabbit-root's basename is `.rabbit`). The git toplevel is WRONG for a
    plugin install: `.rabbit/` lives inside the user project's git repo, so
    `git rev-parse --show-toplevel` returns the user-project root (the PARENT
    of `.rabbit`), whose basename is not `.rabbit`, mis-classifying the plugin
    install as `standalone`."""
    return os.getcwd()


def _resolve_mode(rabbit_root: str) -> "str | None":
    """Detect plugin/standalone via the canonical rabbit-meta detector.

    Returns the mode string, or None when rabbit-meta's detect_mode is
    unavailable (the caller refuses to guess)."""
    detect_mode = _resolve_rabbit_meta_mode_detection()
    if detect_mode is None:
        return None
    # Mode is resolved by the canonical detector — NOT a hard-coded mode-path
    # read. detect_mode inspects the rabbit-root's structural plugin signature
    # (basename == '.rabbit' with a host sibling).
    return detect_mode(rabbit_root)


def _resolve_source_root(rabbit_root: str, mode: str) -> str:
    """The decomposition SOURCE ROOT — where the skill points Glob/Read.

    In plugin mode the rabbit_root is the vendored `.rabbit/` install dir, so
    the project to decompose is its PARENT (matching
    scaffold-feature.py._detect_plugin_mode, project_root = rabbit_root.parent).
    In standalone mode the source root is the repo root itself."""
    if mode == "plugin":
        return str(Path(rabbit_root).parent)
    return str(Path(rabbit_root))


def _parse_args(argv):
    features_file = None
    rabbit_root = None
    plan_only = False
    source_root_only = False
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == "--features":
            if i + 1 >= len(argv):
                _err("--features requires a path argument")
                return None
            features_file = argv[i + 1]
            i += 2
        elif a == "--rabbit-root":
            if i + 1 >= len(argv):
                _err("--rabbit-root requires a path argument")
                return None
            rabbit_root = argv[i + 1]
            i += 2
        elif a == "--plan-only":
            plan_only = True
            i += 1
        elif a == "--source-root":
            source_root_only = True
            i += 1
        elif a in ("-h", "--help"):
            sys.stdout.write(__doc__ or "")
            sys.exit(0)
        else:
            _err(f"unknown argument: {a}")
            return None
        continue
    if not source_root_only and not features_file:
        _err("--features <accepted.json> is required (or use --source-root)")
        return None
    return features_file, rabbit_root, plan_only, source_root_only


def _load_features(path: str):
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        _err(f"cannot read/parse features file {path}: {e}")
        return None
    if not isinstance(data, list) or not data:
        _err("features file must be a non-empty JSON array")
        return None
    for i, entry in enumerate(data):
        if not isinstance(entry, dict) or "name" not in entry:
            _err(f"features[{i}] must be an object with a 'name' field")
            return None
    return data


def _author_batch_file(features) -> str:
    """Write the accepted feature list to a batch temp file with a
    SCRIPT-OWNED timestamp. The script owns the path and the run id — no
    model-assembled `<ts>`."""
    ts = int(time.time())
    fd, path = tempfile.mkstemp(
        prefix=f"decompose-batch-{ts}-", suffix=".json")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(features, f)
    return path


def main(argv) -> int:
    parsed = _parse_args(argv)
    if parsed is None:
        return 2
    features_file, rabbit_root, plan_only, source_root_only = parsed

    if not source_root_only:
        features = _load_features(features_file)
        if features is None:
            return 2

    if rabbit_root is None:
        rabbit_root = _default_rabbit_root()

    mode = _resolve_mode(rabbit_root)
    if mode is None:
        _err("rabbit-meta mode_detection unavailable (cannot resolve "
             "detect_mode); refusing to guess mode")
        return 2

    source_root = _resolve_source_root(rabbit_root, mode)

    # Step 1 mode: resolve mode + the decomposition source root only.
    if source_root_only:
        print(json.dumps({"mode": mode, "source_root": source_root}))
        return 0

    if mode == "plugin":
        batch_file = _author_batch_file(features)
        result = {
            "mode": "plugin",
            "branch": "batch",
            "batch_file": batch_file,
            "source_root": source_root,
            "features": features,
            "dispatched": False,
        }
        if plan_only:
            print(json.dumps(result))
            return 0
        scaffolder = _resolve_scaffolder()
        if scaffolder is None:
            _err("scaffold-feature.py unavailable; cannot dispatch batch")
            return 1
        proc = subprocess.run(
            [sys.executable, str(scaffolder), "--batch", batch_file],
            cwd=source_root,
        )
        result["dispatched"] = proc.returncode == 0
        print(json.dumps(result))
        return 0 if proc.returncode == 0 else 1

    # standalone — batch form is plugin-only; emit the per-feature plan for
    # the dispatcher to run one Skill("rabbit-feature-scaffold", ...) per
    # accepted feature.
    result = {
        "mode": "standalone",
        "branch": "per-feature",
        "batch_file": None,
        "source_root": source_root,
        "features": features,
        "dispatched": False,
    }
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
