#!/usr/bin/env python3
"""rabbit-cage Inv 21 — FEATURE_INCLUDES MANIFEST-source closure.

For every feature shipped by install.py via FEATURE_INCLUDES, this test
parses that feature's feature.json manifest and asserts every source path
referenced by the manifest (the `source` arg of publish_hook /
publish_file / publish_command / publish_settings, and any path-valued
publish_generated arg whose value resolves to a path under the feature
directory, e.g. header_source) is present in that feature's
FEATURE_INCLUDES list.

Failures name the (feature, missing-source) pair so the fix is mechanical:
extend FEATURE_INCLUDES for that feature.
"""
from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = subprocess.run(
    ["git", "-C", SCRIPT_DIR, "rev-parse", "--show-toplevel"],
    capture_output=True, text=True, check=True,
).stdout.strip()
CAGE_DIR = os.path.join(REPO_ROOT, ".claude/features/rabbit-cage")
INSTALL_PY = os.path.join(CAGE_DIR, "install.py")

pass_n = 0
fail_n = 0


def ok(t, msg):
    global pass_n
    print(f"  PASS t{t}: {msg}")
    pass_n += 1


def fail_t(t, msg):
    global fail_n
    print(f"  FAIL t{t}: {msg}")
    fail_n += 1


print("test-feature-includes-manifest-closure.py")


def load_install_module():
    spec = importlib.util.spec_from_file_location("install_under_test", INSTALL_PY)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def extract_manifest_sources(feature_name: str, feature_dir: str) -> list[str]:
    """Return all source paths declared by the feature's manifest that
    resolve to files inside the feature directory (feature-dir-relative)."""
    fj = os.path.join(feature_dir, "feature.json")
    if not os.path.isfile(fj):
        return []
    with open(fj) as f:
        data = json.load(f)
    manifest = data.get("manifest") or []
    sources: list[str] = []
    for entry in manifest:
        api = entry.get("api", "")
        args = entry.get("args") or {}
        if api in ("publish_hook", "publish_file", "publish_command",
                   "publish_settings", "publish_skill"):
            src = args.get("source")
            if isinstance(src, str) and src:
                sources.append(src)
        elif api == "publish_generated":
            # Inspect nested args for path-valued entries that resolve to
            # a file under the feature directory.
            inner = args.get("args") or {}
            if not isinstance(inner, dict):
                continue
            for _k, v in inner.items():
                if not isinstance(v, str) or not v:
                    continue
                # Skip values that are clearly NOT feature-dir-relative
                # (absolute paths and paths starting with .claude/).
                if v.startswith("/") or v.startswith(".claude/"):
                    continue
                candidate = os.path.join(feature_dir, v)
                if os.path.isfile(candidate):
                    sources.append(v)
    return sources


mod = load_install_module()
includes: dict[str, list[str]] = getattr(mod, "FEATURE_INCLUDES", {})

if not includes:
    fail_t(1, "FEATURE_INCLUDES is empty or missing")
else:
    ok(1, f"FEATURE_INCLUDES loaded ({len(includes)} features)")

t = 2
for feature_name in sorted(includes):
    included_paths = set(includes[feature_name])
    feature_dir = os.path.join(REPO_ROOT, ".claude/features", feature_name)
    sources = extract_manifest_sources(feature_name, feature_dir)
    missing = [s for s in sources if s not in included_paths]
    if missing:
        for src in missing:
            fail_t(t, f"feature {feature_name!r}: manifest source {src!r} not in FEATURE_INCLUDES[{feature_name!r}]")
            t += 1
    else:
        ok(t, f"feature {feature_name!r}: all {len(sources)} manifest sources present in FEATURE_INCLUDES")
        t += 1

print()
print(f"Results: {pass_n} passed, {fail_n} failed")
sys.exit(0 if fail_n == 0 else 1)
