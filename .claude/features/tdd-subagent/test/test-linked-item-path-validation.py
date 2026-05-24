#!/usr/bin/env python3
"""Inv 30 — --linked-item path-layout validation.

When --linked-item is provided, dispatch-tdd-subagent.py MUST validate
the resolved path matches `.../rabbit/features/<feature>/<bugs|backlogs>/<id>/`
(segments[-4]=='features' AND segments[-2] in {'bugs','backlogs'}).
On failure: exit 2 with stderr diagnostic naming the expected layout and the
observed tail, with no stdout emitted. On success: the validated feature name
(segments[-3]) is wired through Inv 19's close-call block.
"""
import os
import re

from _helpers import run_dispatch, report, REPO_ROOT

passed = failed = 0


def ok(msg):
    global passed
    passed += 1
    print(f"  ok   {msg}")


def ko(msg):
    global failed
    failed += 1
    print(f"  FAIL {msg}")


# --- (a) malformed path layout: historical bug-trigger shape ---
# .rabbit/items/RABBIT-FEATURE-BACKLOG-8 does not match
# .../rabbit/features/<feature>/<bugs|backlogs>/<id>/
bad_path = ".rabbit/items/RABBIT-FEATURE-BACKLOG-8"
res = run_dispatch("--linked-item", bad_path, "--item-type", "backlog")
if res.returncode == 2:
    ok("inv30: malformed --linked-item path exits 2")
else:
    ko(f"inv30: malformed --linked-item exit was {res.returncode}, expected 2")

if res.stdout == "":
    ok("inv30: malformed --linked-item emits no stdout")
else:
    ko(f"inv30: malformed --linked-item leaked stdout ({len(res.stdout)} bytes)")

# Diagnostic must name the expected layout and the observed tail.
err = res.stderr
if "features" in err and ("bugs" in err or "backlogs" in err):
    ok("inv30: stderr diagnostic names expected layout (features/<feature>/<bugs|backlogs>)")
else:
    ko(f"inv30: stderr diagnostic missing expected-layout phrasing: {err!r}")

if "RABBIT-FEATURE-BACKLOG-8" in err or bad_path in err or "items" in err:
    ok("inv30: stderr diagnostic surfaces the observed path tail")
else:
    ko(f"inv30: stderr diagnostic missing observed path tail: {err!r}")


# --- (b) well-formed path: validated feature/id wire through to close-call block ---
# Use the locally materialized bug item (real path that resolves correctly).
good_path = os.path.join(
    REPO_ROOT, ".rabbit", "rabbit", "features", "tdd-subagent",
    "bugs", "TDD-SUBAGENT-BUG-60",
)
res = run_dispatch("--linked-item", good_path, "--item-type", "bug")
if res.returncode == 0:
    ok("inv30: well-formed --linked-item exits 0")
else:
    ko(f"inv30: well-formed --linked-item exit was {res.returncode}, expected 0; stderr={res.stderr!r}")

expected_close = re.search(
    r"item-status\.py set \\\n"
    r"\s*--feature tdd-subagent --type bug --id TDD-SUBAGENT-BUG-60 \\\n"
    r"\s*--status close \\\n"
    r"\s*--reason 'TDD cycle complete' \\\n"
    r"\s*--fix-commits \$IMPL_SHA",
    res.stdout,
)
if expected_close:
    ok("inv30: close-call block uses validated feature/id from resolved path")
else:
    ko("inv30: close-call block missing or did not use validated feature/id")


# --- (c) well-formed but using `.rabbit` prefix (matches the typical caller shape) ---
# Same canonical layout under .rabbit/rabbit/features/<feature>/<bugs|backlogs>/<id>/
# using a synthesised feature name confirms feature extraction (segments[-3]).
synth_path = os.path.join(
    REPO_ROOT, ".rabbit", "rabbit", "features", "rabbit-cage",
    "backlogs", "RABBIT-CAGE-BACKLOG-99",
)
res = run_dispatch("--linked-item", synth_path, "--item-type", "backlog")
if res.returncode == 0:
    ok("inv30: well-formed backlogs path exits 0 (path need not exist on disk)")
else:
    ko(f"inv30: well-formed backlogs path exit was {res.returncode}; stderr={res.stderr!r}")

expected_close_b = re.search(
    r"item-status\.py set \\\n"
    r"\s*--feature rabbit-cage --type backlog --id RABBIT-CAGE-BACKLOG-99 \\\n"
    r"\s*--status close \\\n",
    res.stdout,
)
if expected_close_b:
    ok("inv30: validated feature name comes from segments[-3], not unvalidated slicing")
else:
    ko("inv30: backlogs close-call did not derive feature/id from validated path")


report(passed, failed)
