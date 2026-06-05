#!/usr/bin/env python3
"""show-mode.py — deterministic "what mode am I in?" reporter (issue #888).

ONE invocation, ZERO AI reasoning: prints whether rabbit is running in
`plugin` or `standalone` mode plus the key evidence, so the model never has to
infer this from env/dir/settings across multiple tool calls.

Machine First: emits a machine-readable JSON object on stdout followed by a
single human-readable summary line, e.g.

    {"mode":"plugin","rabbit_root":"...","project_root":"...",
     "feature_dir":"...","evidence":{...}}
    Mode: plugin (RABBIT_ROOT=… project=…)

Detection is delegated to the canonical resolver
`rabbit-meta.lib.mode_detection.detect_mode` (a cross-feature INVOKE, not an
edit) so this command always agrees with the rest of the system. The resolver
is lazy-imported relative to THIS script's own location
(`../../rabbit-meta/lib/mode_detection.py`), which is robust regardless of the
process cwd.

Rabbit root resolution: `RABBIT_ROOT` if set, else the install root inferred
from this script's location (`<root>/.claude/features/rabbit-cage/scripts/`).
In plugin mode RABBIT_ROOT is the vendored `.rabbit/` install dir and the
project root is its parent; in standalone mode the install root IS the repo
root and the project root coincides with it.

Version: 1.0.0
Owner: rabbit-workflow team (rabbit-cage)
Deprecation criterion: when Claude Code exposes a native mode/contract
    introspection mechanism that subsumes this reporter.
"""
import importlib.util
import json
import os
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
# <root>/.claude/features/rabbit-cage/scripts/show-mode.py -> <root>
_INSTALL_ROOT = _HERE.parents[3]
_META_LIB = _INSTALL_ROOT / ".claude" / "features" / "rabbit-meta" / "lib" / "mode_detection.py"


def _load_detect_mode():
    """Lazy-import the canonical detect_mode resolver from rabbit-meta.

    Returns the callable, or None when rabbit-meta is unavailable (degenerate
    self-build / partial install)."""
    try:
        spec = importlib.util.spec_from_file_location(
            "rabbit_meta_mode_detection", str(_META_LIB))
        if spec is None or spec.loader is None:
            return None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module.detect_mode
    except (FileNotFoundError, ImportError, AttributeError):
        return None


def _resolve_rabbit_root() -> str:
    env = os.environ.get("RABBIT_ROOT")
    if env:
        return str(Path(env))
    return str(_INSTALL_ROOT)


def main() -> int:
    rabbit_root = _resolve_rabbit_root()
    rabbit_root_env = os.environ.get("RABBIT_ROOT")

    detect_mode = _load_detect_mode()
    if detect_mode is None:
        result = {
            "mode": "unknown",
            "rabbit_root": rabbit_root,
            "project_root": rabbit_root,
            "feature_dir": str(Path(rabbit_root) / ".claude" / "features"),
            "evidence": {
                "rabbit_root_env": rabbit_root_env,
                "error": "rabbit-meta resolver unavailable",
            },
        }
        print(json.dumps(result))
        print(f"Mode: unknown (rabbit-meta resolver unavailable; "
              f"RABBIT_ROOT={rabbit_root_env})")
        return 0

    mode = detect_mode(rabbit_root)

    # Plugin: rabbit_root is the vendored `.rabbit/` dir; project root is its
    # parent. Standalone: install root IS the repo root; they coincide.
    rabbit_root_path = Path(rabbit_root)
    if mode == "plugin":
        project_root = str(rabbit_root_path.parent)
    else:
        project_root = rabbit_root
    feature_dir = str(rabbit_root_path / ".claude" / "features")

    result = {
        "mode": mode,
        "rabbit_root": rabbit_root,
        "project_root": project_root,
        "feature_dir": feature_dir,
        "evidence": {
            "rabbit_root_env": rabbit_root_env,
            "rabbit_root_basename": rabbit_root_path.name,
            "resolved_via": "RABBIT_ROOT" if rabbit_root_env else "script-location",
        },
    }
    print(json.dumps(result))
    print(f"Mode: {mode} (RABBIT_ROOT={rabbit_root_env} project={project_root})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
