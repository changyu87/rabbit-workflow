#!/usr/bin/env python3
"""test-publish-file-deployed-copies-match-source.py — Inv 52.

For every entry across every feature's `feature.json` `manifest` where
`api in {"publish_file", "publish_hook"}`, the COMMITTED bytes at the
deployed destination MUST match the COMMITTED bytes at the feature-local
source.

  - publish_file: dest = args["dest"] (resolved relative to repo root)
  - publish_hook: dest = ".claude/hooks/" + os.path.basename(args["source"])

EXCLUDED: publish_skill (covered by Inv 51 /
test-deployed-skills-match-source.py), publish_settings (JSON merge, not a
byte copy), publish_generated (content produced by a producer, with its own
drift-regen story via check_drift_regenerate).

Catches the drift class observed in PRs #257, #263, #265 where a TDD cycle
updated the feature-local source but left the committed deployed copy stale
on `dev`. Non-interactive. Exits non-zero on failure.
"""

import glob
import json
import os
import sys

FEATURE_DIR = os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
)
REPO_ROOT = os.path.normpath(os.path.join(FEATURE_DIR, "..", "..", ".."))
FEATURES_ROOT = os.path.join(REPO_ROOT, ".claude", "features")

BYTE_COPY_APIS = {"publish_file", "publish_hook"}

PASS = 0
FAIL = 0


def ok(name, msg):
    global PASS
    print(f"  PASS {name}: {msg}")
    PASS += 1


def fail(name, msg):
    global FAIL
    print(f"  FAIL {name}: {msg}", file=sys.stderr)
    FAIL += 1


def resolve_pair(feature_dir, entry):
    """Return (source_abs, dest_abs) for a publish_file / publish_hook entry,
    or None if the entry is malformed (missing args)."""
    args = entry.get("args") or {}
    src_rel = args.get("source")
    if not src_rel:
        return None
    source_abs = os.path.normpath(os.path.join(feature_dir, src_rel))
    api = entry.get("api")
    if api == "publish_file":
        dest_rel = args.get("dest")
        if not dest_rel:
            return None
        dest_abs = os.path.normpath(os.path.join(REPO_ROOT, dest_rel))
    elif api == "publish_hook":
        dest_abs = os.path.normpath(
            os.path.join(
                REPO_ROOT, ".claude", "hooks", os.path.basename(src_rel)
            )
        )
    else:
        return None
    return source_abs, dest_abs


feature_jsons = sorted(
    glob.glob(os.path.join(FEATURES_ROOT, "*", "feature.json"))
)

if not feature_jsons:
    ok("t0", "no feature.json files found — vacuous pass")
    print()
    print(f"Results: {PASS} passed, {FAIL} failed")
    sys.exit(0)

ok("t0", f"discovered {len(feature_jsons)} feature.json file(s)")

checked = 0
for fj in feature_jsons:
    feature_dir = os.path.dirname(fj)
    feature_name = os.path.basename(feature_dir)
    try:
        with open(fj, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        fail(f"t-{feature_name}-load", f"could not load {fj}: {e}")
        continue

    manifest = data.get("manifest") or []
    if not isinstance(manifest, list):
        continue

    for idx, entry in enumerate(manifest):
        if not isinstance(entry, dict):
            continue
        api = entry.get("api")
        if api not in BYTE_COPY_APIS:
            continue
        pair = resolve_pair(feature_dir, entry)
        if pair is None:
            continue
        source_abs, dest_abs = pair

        # Skip pairs where either side is absent; existence is a separate
        # concern enforced elsewhere. Parity only applies when both exist.
        if not os.path.isfile(source_abs):
            continue
        if not os.path.isfile(dest_abs):
            fail(
                f"t-{feature_name}-{idx}-{api}",
                f"feature={feature_name} source={source_abs} "
                f"dest={dest_abs} drifted (dest missing)",
            )
            continue

        with open(source_abs, "rb") as f:
            src_bytes = f.read()
        with open(dest_abs, "rb") as f:
            dst_bytes = f.read()

        if src_bytes != dst_bytes:
            fail(
                f"t-{feature_name}-{idx}-{api}",
                f"feature={feature_name} source={source_abs} "
                f"dest={dest_abs} drifted",
            )
        else:
            ok(
                f"t-{feature_name}-{idx}-{api}",
                f"deployed copy byte-identical to source ({source_abs})",
            )
            checked += 1

ok("t-summary", f"checked {checked} byte-copy publish entries across all features")

print()
print(f"Results: {PASS} passed, {FAIL} failed")
sys.exit(0 if FAIL == 0 else 1)
