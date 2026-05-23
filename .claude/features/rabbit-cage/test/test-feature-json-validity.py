#!/usr/bin/env python3
"""test-feature-json-validity.py — Inv 8.

Asserts rabbit-cage's feature.json declares manifest/runtime/configuration
in the expected shape, and every API name listed in those sections is
exported by the corresponding contract.lib.* module.
"""

import importlib.util
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
CAGE_FJ = REPO / ".claude/features/rabbit-cage/feature.json"
CONTRACT = REPO / ".claude/features/contract"


def _load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(CONTRACT))
    spec.loader.exec_module(mod)
    return mod


def main() -> int:
    data = json.loads(CAGE_FJ.read_text())
    manifest = data.get("manifest")
    runtime = data.get("runtime")
    configuration = data.get("configuration")

    assert isinstance(manifest, list) and manifest, "manifest must be non-empty list"
    assert isinstance(runtime, dict), "runtime must be a dict"
    for key in ("Stop", "SessionStart", "UserPromptSubmit"):
        assert key in runtime, f"runtime missing event key {key!r}"
        assert isinstance(runtime[key], list), f"runtime[{key}] must be list"
    assert isinstance(configuration, list) and configuration, "configuration must be non-empty list"

    pub_mod = _load_module("c_publish", CONTRACT / "lib/publish.py")
    rt_mod = _load_module("c_runtime", CONTRACT / "lib/runtime.py")
    mut_mod = _load_module("c_mutation", CONTRACT / "lib/mutation.py")

    # Manifest API names exist in lib.publish
    for entry in manifest:
        api = entry.get("api")
        assert getattr(pub_mod, api, None) is not None, (
            f"manifest declares unknown publish API: {api!r}")

    # Runtime API names exist in lib.runtime
    for event, entries in runtime.items():
        for entry in entries:
            api = entry.get("api")
            assert getattr(rt_mod, api, None) is not None, (
                f"runtime[{event}] declares unknown runtime API: {api!r}")

    # Configuration mutation API names exist in lib.mutation
    for cfg in configuration:
        for mutators in (cfg.get("values") or {}, cfg.get("actions") or {}):
            for verb, spec in mutators.items():
                api = spec.get("api")
                assert getattr(mut_mod, api, None) is not None, (
                    f"configuration {cfg.get('id')!r} declares unknown "
                    f"mutation API: {api!r}")

    print(f"PASS feature.json validity (manifest:{len(manifest)} "
          f"runtime:{sum(len(v) for v in runtime.values())} "
          f"configuration:{len(configuration)})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
