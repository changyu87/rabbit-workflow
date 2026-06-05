#!/usr/bin/env python3
"""handoff-scaffold.py — rabbit-decompose Step 4 scaffold hand-off orchestrator.

Makes Step 4 SCRIPT-tier (spec-rules §4 Script-Backed Orchestration; spec
Invariant 5). The SKILL.md body invokes this script with the accepted feature
list instead of detecting mode, authoring a batch temp file, and branching the
scaffolder inline in prose.

Responsibilities:

  1. Resolve the rabbit root (from --rabbit-root, else the cwd-based git
     toplevel) and DETECT MODE deterministically by REUSING the canonical
     resolver `rabbit-meta.lib.mode_detection.detect_mode` (lazy-imported,
     mirroring contract.lib.runtime.write_mode_marker). NOT a single
     hard-coded `<repo>/.rabbit/.runtime/mode` path read.
  2. Author the batch temp file with a SCRIPT-OWNED timestamp (no
     model-assembled `<ts>`): the script owns the path and content.
  3. Dispatch the scaffolder on the mode-correct branch:
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

  --features    path to a JSON array of accepted features:
                [{"name": "<kebab>", "globs": ["..."]}, ...]
  --rabbit-root the rabbit root used for mode detection. Default: the
                cwd-based git toplevel. In plugin mode this is the vendored
                `.rabbit/` directory; in standalone mode the repo root.
  --plan-only   resolve mode + author the batch file (plugin) but do NOT
                invoke the scaffolder; print the decision as JSON and exit 0.
                Used by the SKILL body's dry-run and by the test.

Output (always JSON on stdout):
  {
    "mode": "plugin" | "standalone",
    "branch": "batch" | "per-feature",
    "batch_file": "<abs path>" | null,
    "features": [ {"name": ..., "globs": [...]}, ... ],
    "dispatched": <bool>            # false under --plan-only
  }

Exit:
  0 success (plan computed; scaffolder dispatched unless --plan-only)
  1 scaffolder dispatch failed
  2 invocation error (bad args, unreadable/invalid features file)

Version: 0.1.0
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
    """The cwd-based git toplevel; falls back to cwd when git is unavailable."""
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, check=False,
        )
        if out.returncode == 0 and out.stdout.strip():
            return out.stdout.strip()
    except Exception:
        pass
    return os.getcwd()


def _parse_args(argv):
    features_file = None
    rabbit_root = None
    plan_only = False
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
        elif a in ("-h", "--help"):
            sys.stdout.write(__doc__ or "")
            sys.exit(0)
        else:
            _err(f"unknown argument: {a}")
            return None
        continue
    if not features_file:
        _err("--features <accepted.json> is required")
        return None
    return features_file, rabbit_root, plan_only


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
    features_file, rabbit_root, plan_only = parsed

    features = _load_features(features_file)
    if features is None:
        return 2

    if rabbit_root is None:
        rabbit_root = _default_rabbit_root()

    detect_mode = _resolve_rabbit_meta_mode_detection()
    if detect_mode is None:
        _err("rabbit-meta mode_detection unavailable (cannot resolve "
             "detect_mode); refusing to guess mode")
        return 2

    # Mode is resolved by the canonical detector — NOT a hard-coded mode-path
    # read. detect_mode inspects the rabbit-root's structural plugin
    # signature (basename == '.rabbit' with a host sibling).
    mode = detect_mode(rabbit_root)

    if mode == "plugin":
        batch_file = _author_batch_file(features)
        result = {
            "mode": "plugin",
            "branch": "batch",
            "batch_file": batch_file,
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
        project_root = str(Path(rabbit_root).parent)
        proc = subprocess.run(
            [sys.executable, str(scaffolder), "--batch", batch_file],
            cwd=project_root,
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
        "features": features,
        "dispatched": False,
    }
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
