#!/usr/bin/env python3
"""test-find-feature-plugin-mode.py — Inv 23 (amended for #300).

find-feature.py MUST dual-detect plugin mode from either root form:

  - Host-root form: repo=<host>, marker at <repo>/.rabbit/.runtime/mode
    rabbit_root = <repo>/.rabbit
  - Rabbit-root form: repo=<rabbit_root>, marker at <repo>/.runtime/mode
    rabbit_root = <repo>

In plugin mode (either detection path) it scans TWO canonical locations
under rabbit_root:
  (a) <rabbit_root>/.claude/features/<name>/feature.json
  (b) <rabbit_root>/rabbit-project/features/<name>/feature.json

Standalone mode (no marker file matched) MUST scan only
<repo>/.claude/features/<name>/feature.json (byte-identical to the
pre-amendment standalone form).

Order: rabbit-internal first then rabbit-project, alphabetical within each.
No dedup.
"""

import os
import sys
import json
import subprocess
import tempfile
import shutil

FEATURE_DIR = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
SCRIPT = os.path.join(FEATURE_DIR, "scripts/find-feature.py")

FAIL = 0


def _write_feature_json(path, name, summary):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump({
            "name": name,
            "version": "0.1.0",
            "owner": "t",
            "tdd_state": "spec",
            "summary": summary,
            "surface": {"hooks": [], "commands": [], "agents": [], "skills": []},
            "deprecation_criterion": "x",
        }, f)


def _setup_tmpdir(mode_content):
    """Create tmp repo fixtures for both standalone and plugin (host-root) scans.

    Layout written:
      <tmp>/.claude/features/rabbit-cage/feature.json
         — standalone scan target.
      <tmp>/.rabbit/.claude/features/rabbit-cage/feature.json
         — plugin scan rabbit-internal target (under rabbit_root).
      <tmp>/.rabbit/rabbit-project/features/my-feature/feature.json
         — plugin scan project target (under rabbit_root).
      <tmp>/.rabbit/.runtime/mode (with mode_content) — controls detection.

    mode_content is None (no marker file), 'plugin', or 'standalone'.
    """
    tmp = tempfile.mkdtemp()
    _write_feature_json(
        os.path.join(tmp, ".claude/features/rabbit-cage/feature.json"),
        "rabbit-cage",
        "cage",
    )
    _write_feature_json(
        os.path.join(tmp, ".rabbit/.claude/features/rabbit-cage/feature.json"),
        "rabbit-cage",
        "cage",
    )
    _write_feature_json(
        os.path.join(tmp, ".rabbit/rabbit-project/features/my-feature/feature.json"),
        "my-feature",
        "user feature",
    )
    if mode_content is not None:
        runtime_dir = os.path.join(tmp, ".rabbit/.runtime")
        os.makedirs(runtime_dir, exist_ok=True)
        with open(os.path.join(runtime_dir, "mode"), "w") as f:
            f.write(mode_content)
    return tmp


def _list_json(tmp):
    proc = subprocess.run(
        ["python3", SCRIPT, tmp, "list-json"],
        capture_output=True, text=True,
    )
    if proc.returncode != 0:
        print(f"FAIL: find-feature.py exited {proc.returncode}; stderr={proc.stderr}", file=sys.stderr)
        return None
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError as e:
        print(f"FAIL: invalid JSON from list-json: {e}; stdout={proc.stdout!r}", file=sys.stderr)
        return None


# t1: plugin mode — both features visible, .claude/features/ entry first.
tmp = _setup_tmpdir("plugin")
try:
    results = _list_json(tmp)
    if results is None:
        FAIL = 1
    else:
        names = [r["name"] for r in results]
        if "rabbit-cage" not in names:
            print(f"FAIL t1: rabbit-cage missing from plugin-mode list (got {names})", file=sys.stderr)
            FAIL = 1
        elif "my-feature" not in names:
            print(f"FAIL t1: my-feature missing from plugin-mode list (got {names})", file=sys.stderr)
            FAIL = 1
        elif names.index("rabbit-cage") > names.index("my-feature"):
            print(f"FAIL t1: rabbit-cage must precede my-feature; got order {names}", file=sys.stderr)
            FAIL = 1
        else:
            print("PASS t1: plugin mode surfaces both canonical scans in correct order")
finally:
    shutil.rmtree(tmp, ignore_errors=True)


# t2: standalone mode — plugin-side feature NOT scanned.
tmp = _setup_tmpdir("standalone")
try:
    results = _list_json(tmp)
    if results is None:
        FAIL = 1
    else:
        names = [r["name"] for r in results]
        if "rabbit-cage" not in names:
            print(f"FAIL t2: rabbit-cage missing in standalone mode (got {names})", file=sys.stderr)
            FAIL = 1
        elif "my-feature" in names:
            print(f"FAIL t2: my-feature leaked into standalone-mode list (got {names})", file=sys.stderr)
            FAIL = 1
        else:
            print("PASS t2: standalone mode scans only .claude/features/")
finally:
    shutil.rmtree(tmp, ignore_errors=True)


# t3: no mode file — same as standalone behavior.
tmp = _setup_tmpdir(None)
try:
    results = _list_json(tmp)
    if results is None:
        FAIL = 1
    else:
        names = [r["name"] for r in results]
        if "rabbit-cage" not in names:
            print(f"FAIL t3: rabbit-cage missing with no mode file (got {names})", file=sys.stderr)
            FAIL = 1
        elif "my-feature" in names:
            print(f"FAIL t3: my-feature leaked with no mode file (got {names})", file=sys.stderr)
            FAIL = 1
        else:
            print("PASS t3: missing mode file yields standalone behavior")
finally:
    shutil.rmtree(tmp, ignore_errors=True)


# Scenario C (NEW, #300): plugin mode detected via rabbit-root call —
# repo=<tmp>/.rabbit with mode marker at <repo>/.runtime/mode='plugin'.
# Expects same surface as Scenario B (rabbit-cage + my-feature, in order).
tmp = tempfile.mkdtemp()
try:
    rabbit_root = os.path.join(tmp, ".rabbit")
    # Rabbit-internal feature lives under <rabbit_root>/.claude/features/
    _write_feature_json(
        os.path.join(rabbit_root, ".claude/features/rabbit-cage/feature.json"),
        "rabbit-cage",
        "cage",
    )
    # Project plugin feature lives under <rabbit_root>/rabbit-project/features/
    _write_feature_json(
        os.path.join(rabbit_root, "rabbit-project/features/my-feature/feature.json"),
        "my-feature",
        "user feature",
    )
    runtime_dir = os.path.join(rabbit_root, ".runtime")
    os.makedirs(runtime_dir, exist_ok=True)
    with open(os.path.join(runtime_dir, "mode"), "w") as f:
        f.write("plugin")

    proc = subprocess.run(
        ["python3", SCRIPT, rabbit_root, "list-json"],
        capture_output=True, text=True,
    )
    if proc.returncode != 0:
        print(f"FAIL t4 (Scenario C): find-feature.py exited {proc.returncode}; stderr={proc.stderr}", file=sys.stderr)
        FAIL = 1
    else:
        try:
            results = json.loads(proc.stdout)
        except json.JSONDecodeError as e:
            print(f"FAIL t4 (Scenario C): invalid JSON; stdout={proc.stdout!r}", file=sys.stderr)
            FAIL = 1
            results = None
        if results is not None:
            names = [r["name"] for r in results]
            if "rabbit-cage" not in names:
                print(f"FAIL t4 (Scenario C): rabbit-cage missing when repo=rabbit_root in plugin mode (got {names})", file=sys.stderr)
                FAIL = 1
            elif "my-feature" not in names:
                print(f"FAIL t4 (Scenario C): my-feature missing when repo=rabbit_root in plugin mode (got {names})", file=sys.stderr)
                FAIL = 1
            elif names.index("rabbit-cage") > names.index("my-feature"):
                print(f"FAIL t4 (Scenario C): rabbit-cage must precede my-feature; got order {names}", file=sys.stderr)
                FAIL = 1
            else:
                print("PASS t4 (Scenario C): plugin mode detected via rabbit-root (<repo>/.runtime/mode)")
finally:
    shutil.rmtree(tmp, ignore_errors=True)


# Scenario D (NEW, #300 regression-pin): caller passes repo=rabbit_root
# and expects BOTH rabbit-internal and project features in list-json output.
# This exactly reproduces the failure mode in bug #300 where
# resolve-scope.py + dispatch-tdd-subagent.py passed rabbit_root and got
# only an empty/partial list.
tmp = tempfile.mkdtemp()
try:
    rabbit_root = os.path.join(tmp, ".rabbit")
    _write_feature_json(
        os.path.join(rabbit_root, ".claude/features/rabbit-cage/feature.json"),
        "rabbit-cage",
        "cage",
    )
    _write_feature_json(
        os.path.join(rabbit_root, "rabbit-project/features/my-feature/feature.json"),
        "my-feature",
        "user feature",
    )
    runtime_dir = os.path.join(rabbit_root, ".runtime")
    os.makedirs(runtime_dir, exist_ok=True)
    with open(os.path.join(runtime_dir, "mode"), "w") as f:
        f.write("plugin")

    proc = subprocess.run(
        ["python3", SCRIPT, rabbit_root, "list-json"],
        capture_output=True, text=True,
    )
    if proc.returncode != 0:
        print(f"FAIL t5 (Scenario D #300): list-json exited {proc.returncode}; stderr={proc.stderr}", file=sys.stderr)
        FAIL = 1
    else:
        try:
            results = json.loads(proc.stdout)
        except json.JSONDecodeError as e:
            print(f"FAIL t5 (Scenario D #300): invalid JSON; stdout={proc.stdout!r}", file=sys.stderr)
            FAIL = 1
            results = None
        if results is not None:
            names = sorted(r["name"] for r in results)
            if "rabbit-cage" not in names or "my-feature" not in names:
                print(f"FAIL t5 (Scenario D #300): expected BOTH rabbit-cage AND my-feature when repo=rabbit_root; got {names}", file=sys.stderr)
                FAIL = 1
            else:
                print("PASS t5 (Scenario D #300): rabbit-root list-json returns both rabbit-internal + project features")
finally:
    shutil.rmtree(tmp, ignore_errors=True)


# Scenario (v) (NEW, #311 regression): caller passes repo=rabbit_root and a
# rogue inner <rabbit_root>/.rabbit/.runtime/mode='plugin' exists with NO
# accompanying .claude/ directory (the failure mode observed when a skill
# wrote relative .rabbit/* paths from CWD=<rabbit_root>, accidentally
# creating <rabbit_root>/.rabbit/.runtime/mode). The function MUST prefer
# the outer <repo>/.runtime/mode (precedence) AND reject the bogus inner
# candidate via the validation step (<rabbit_root>/.claude/ must exist),
# returning the REAL outer rabbit_root — proven by rabbit-cage appearing
# in the list-json output. Pre-fix: greedy first-match returned the bogus
# inner <rabbit_root>/.rabbit and the list came back empty.
tmp = tempfile.mkdtemp()
try:
    rabbit_root = os.path.join(tmp, ".rabbit")
    # Real rabbit_root has .claude/features/rabbit-cage.
    _write_feature_json(
        os.path.join(rabbit_root, ".claude/features/rabbit-cage/feature.json"),
        "rabbit-cage",
        "cage",
    )
    # Outer mode marker (the correct one).
    outer_runtime = os.path.join(rabbit_root, ".runtime")
    os.makedirs(outer_runtime, exist_ok=True)
    with open(os.path.join(outer_runtime, "mode"), "w") as f:
        f.write("plugin")
    # Rogue inner .rabbit/.runtime/mode — bogus, no .claude/ sibling.
    rogue_runtime = os.path.join(rabbit_root, ".rabbit", ".runtime")
    os.makedirs(rogue_runtime, exist_ok=True)
    with open(os.path.join(rogue_runtime, "mode"), "w") as f:
        f.write("plugin")

    proc = subprocess.run(
        ["python3", SCRIPT, rabbit_root, "list-json"],
        capture_output=True, text=True,
    )
    if proc.returncode != 0:
        print(f"FAIL t6 (Scenario v #311): list-json exited {proc.returncode}; stderr={proc.stderr}", file=sys.stderr)
        FAIL = 1
    else:
        try:
            results = json.loads(proc.stdout)
        except json.JSONDecodeError as e:
            print(f"FAIL t6 (Scenario v #311): invalid JSON; stdout={proc.stdout!r}", file=sys.stderr)
            FAIL = 1
            results = None
        if results is not None:
            names = [r["name"] for r in results]
            if "rabbit-cage" not in names:
                print(f"FAIL t6 (Scenario v #311): rabbit-cage missing — rogue inner .rabbit/.runtime/mode won over outer (got {names})", file=sys.stderr)
                FAIL = 1
            else:
                print("PASS t6 (Scenario v #311): outer .runtime/mode wins + bogus inner .rabbit/ rejected by .claude/ validation")
finally:
    shutil.rmtree(tmp, ignore_errors=True)


if FAIL:
    print("test-find-feature-plugin-mode: FAIL", file=sys.stderr)
    sys.exit(1)

print("test-find-feature-plugin-mode: all checks passed.")
