#!/usr/bin/env python3
"""test-dual-accept-vendored-mode.py — dual-accept vendored/plugin mode (#988).

End-to-end guard for spec Invariant 10 (#988): a gate-safe prep step for the
#980 rename of the vendored-mode value `"plugin"` -> `"vendored"`.
`scripts/handoff-scaffold.py` has 5 `mode == "plugin"` comparison sites (the
source-root resolver, the project-map path resolver, the decompose-marker path
resolver, and the two main-dispatch branch sites) that would SILENTLY take the
standalone path if the value flips to `"vendored"` before this script is
updated. Each MUST dual-accept `mode in ("vendored", "plugin")` so BOTH values
take the vendored path. This stays gate-green now (value still `"plugin"`) and
after the #980 flip.

The test loads the real `handoff-scaffold.py` module and drives each
comparison site directly with BOTH `"vendored"` and `"plugin"`, asserting they
resolve to the SAME (vendored) result and that the standalone value diverges.
It also drives the main dispatch branch end-to-end by monkeypatching the
module's `_resolve_mode` to return each value, confirming a `"vendored"`-mode
run takes the plugin/batch branch exactly as a `"plugin"`-mode run does.

Run non-interactively. Exits non-zero on failure.

Version: 0.1.0
Owner: rabbit-workflow team
Deprecation criterion: removed when the #980 migration completes and the
    legacy `"plugin"` value is fully retired, leaving only `"vendored"`.
"""
import contextlib
import importlib.util
import io
import json
import os
import sys
import tempfile

FEATURE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SCRIPT = os.path.join(FEATURE_DIR, "scripts", "handoff-scaffold.py")

VENDORED_VALUES = ("vendored", "plugin")
STANDALONE_VALUE = "standalone"


def fail(msg):
    print(f"FAIL: {msg}", file=sys.stderr)
    sys.exit(1)


if not os.path.isfile(SCRIPT):
    fail(f"missing handoff-scaffold.py: {SCRIPT}")


def _load_module():
    spec = importlib.util.spec_from_file_location("handoff_scaffold", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


mod = _load_module()

RABBIT_ROOT = "/tmp/some/host-project/.rabbit"

# --- Sites 1-3: the three mode-aware path resolvers --------------------------
# Each must dual-accept: "vendored" and "plugin" yield the SAME vendored-path
# result, and that result must DIFFER from the standalone-value result (so the
# dual-accept actually selects the vendored branch, not a no-op).
RESOLVERS = [
    ("_resolve_source_root", mod._resolve_source_root),
    ("_resolve_project_map_path", mod._resolve_project_map_path),
    ("_resolve_decompose_marker_path", mod._resolve_decompose_marker_path),
]

for name, fn in RESOLVERS:
    results = {v: fn(RABBIT_ROOT, v) for v in VENDORED_VALUES}
    if results["vendored"] != results["plugin"]:
        fail(f"{name}: 'vendored' and 'plugin' must resolve to the SAME "
             f"vendored path; got vendored={results['vendored']!r} "
             f"plugin={results['plugin']!r}")
    standalone_result = fn(RABBIT_ROOT, STANDALONE_VALUE)
    if results["vendored"] == standalone_result:
        fail(f"{name}: the vendored path must DIFFER from the standalone path "
             f"(otherwise the comparison is a no-op); both were "
             f"{standalone_result!r}")

# --- Sites 4-5: the main dispatch branch ------------------------------------
# main() with --plan-only chooses the plugin/batch branch (sites at the two
# `mode == "plugin"` checks in the dispatch tail). Drive it with each value by
# monkeypatching _resolve_mode, and assert "vendored" takes the SAME
# (batch/plugin) branch as "plugin".
orig_resolve_mode = mod._resolve_mode

with tempfile.TemporaryDirectory() as td:
    feats_path = os.path.join(td, "accepted.json")
    with open(feats_path, "w", encoding="utf-8") as f:
        json.dump([{"name": "feature-one", "globs": ["src/one/**/*"]}], f)

    plans = {}
    for v in VENDORED_VALUES:
        mod._resolve_mode = (lambda value: (lambda root: value))(v)
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = mod.main(["--features", feats_path,
                           "--rabbit-root", RABBIT_ROOT, "--plan-only"])
        if rc != 0:
            fail(f"main(--plan-only) with mode {v!r} exited {rc}")
        plans[v] = json.loads(buf.getvalue())

    mod._resolve_mode = orig_resolve_mode

    # Both must take the plugin/batch branch (the vendored path).
    for v in VENDORED_VALUES:
        if plans[v].get("branch") != "batch":
            fail(f"main dispatch with mode {v!r} did NOT take the batch "
                 f"(vendored) branch; got branch={plans[v].get('branch')!r}")
        if not plans[v].get("batch_file"):
            fail(f"main dispatch with mode {v!r} did not author a batch_file "
                 "(the vendored branch); it silently took the standalone path")

    # And the standalone value must take the per-feature branch (proving the
    # branch dual-accept actually gates on the value, not a constant).
    mod._resolve_mode = lambda root: STANDALONE_VALUE
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = mod.main(["--features", feats_path,
                       "--rabbit-root", RABBIT_ROOT, "--plan-only"])
    mod._resolve_mode = orig_resolve_mode
    if rc != 0:
        fail(f"main(--plan-only) with standalone exited {rc}")
    plan_s = json.loads(buf.getvalue())
    if plan_s.get("branch") != "per-feature":
        fail("main dispatch with standalone did not take the per-feature "
             f"branch; got branch={plan_s.get('branch')!r}")

print("All checks passed.")
