#!/usr/bin/env python3
"""Inv 48 / #1067 — `_tdd_report_path` anchors at the canonical single-`.rabbit`
runtime root resolved by rabbit-cage's `rabbit_runtime_root` (Inv 52), instead of
its bespoke mode-marker candidate probing.

`rabbit_runtime_root(repo_root)` returns `repo_root` when its basename is
`.rabbit` (vendored) else `<repo_root>/.rabbit` (standalone), idempotently. The
dispatcher's `_tdd_report_path` MUST place the report at
`<rabbit_runtime_root(repo_root)>/tdd-report-<feature>.json` so report/impl
artifacts agree on a single runtime root — no doubled `.rabbit/.rabbit/`, no
fall-through divergence between mode-marker probing and the canonical resolver.

Scenarios:
  A) Vendored: repo_root basename IS `.rabbit`. Report MUST be
     `<repo_root>/tdd-report-<feature>.json` (single segment, resolver returns
     repo_root unchanged).
  B) Standalone: repo_root basename is NOT `.rabbit`. Report MUST be
     `<repo_root>/.rabbit/tdd-report-<feature>.json`.
  C) Equivalence: `_tdd_report_path` for ANY repo_root MUST equal
     `<rabbit_runtime_root(repo_root)>/tdd-report-<feature>.json` — proving it
     delegates to the canonical resolver rather than mode-marker probing. Run
     against a vendored-basename repo_root that has NO mode marker on disk; the
     old bespoke probing would fall through to the standalone form here, while
     the resolver-anchored implementation returns the vendored form.
"""
import importlib.util
import os
import sys

from _helpers import FEATURE_DIR, REPO_ROOT, report

passed = failed = 0


def ok(msg):
    global passed
    passed += 1
    print(f"  ok   {msg}")


def ko(msg):
    global failed
    failed += 1
    print(f"  FAIL {msg}")


def _load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


dispatch = _load_module(
    "dispatch_tdd_subagent_under_test",
    os.path.join(FEATURE_DIR, "scripts", "dispatch-tdd-subagent.py"),
)
runtime_root_mod = _load_module(
    "rabbit_cage_runtime_root_under_test",
    os.path.join(REPO_ROOT, ".claude", "features", "rabbit-cage",
                 "lib", "runtime_root.py"),
)
rabbit_runtime_root = runtime_root_mod.rabbit_runtime_root

# ---------------------------------------------------------------------------
# Scenario A: vendored — repo_root basename IS `.rabbit`.
# ---------------------------------------------------------------------------
vendored_root = "/host/project/.rabbit"
got = dispatch._tdd_report_path(vendored_root, "run-ingest")
expected = os.path.join(vendored_root, "tdd-report-run-ingest.json")
if got == expected:
    ok(f"scenario A: vendored report path is {expected!r} (single .rabbit/)")
else:
    ko(f"scenario A: got {got!r}, expected {expected!r}")

# ---------------------------------------------------------------------------
# Scenario B: standalone — repo_root basename is NOT `.rabbit`.
# ---------------------------------------------------------------------------
standalone_root = "/home/user/rabbit-self"
got = dispatch._tdd_report_path(standalone_root, "run-ingest")
expected = os.path.join(standalone_root, ".rabbit", "tdd-report-run-ingest.json")
if got == expected:
    ok(f"scenario B: standalone report path is {expected!r}")
else:
    ko(f"scenario B: got {got!r}, expected {expected!r}")

# ---------------------------------------------------------------------------
# Scenario C: equivalence with the canonical resolver, no mode marker on disk.
#
# A vendored-basename repo_root with NO `.runtime/mode` file. The old bespoke
# probing keyed off the mode marker and would fall through to the standalone
# form (`<root>/.rabbit/...`). The resolver-anchored implementation keys off the
# basename and returns the vendored form (`<root>/tdd-report-...json`).
# ---------------------------------------------------------------------------
for root in ("/x/.rabbit", "/y/rabbit-self", "/z/proj/.rabbit"):
    got = dispatch._tdd_report_path(root, "feat")
    expected = os.path.join(rabbit_runtime_root(root), "tdd-report-feat.json")
    if got == expected:
        ok(f"scenario C: {root!r} report path equals resolver-anchored "
           f"{expected!r}")
    else:
        ko(f"scenario C: {root!r} got {got!r}, expected resolver-anchored "
           f"{expected!r}")

report(passed, failed)
