#!/usr/bin/env python3
"""test-find-feature-plugin-mode.py — Inv 23 (amended).

find-feature.py MUST scan two canonical locations:
  (a) <repo>/.claude/features/<name>/feature.json — always
  (b) <repo>/.rabbit/rabbit-project/features/<name>/feature.json — ONLY
      when <repo>/.rabbit/.runtime/mode exists with content "plugin".

Standalone mode (no marker file, or content != "plugin") MUST be
byte-identical to the pre-amendment scan: only (a) is yielded.

Order: results from (a) first then (b), each alphabetical. No dedup.
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
    """Create tmp repo with one .claude/features/ feature and one plugin-side feature.

    mode_content is None (no marker file), 'plugin', or 'standalone'.
    """
    tmp = tempfile.mkdtemp()
    _write_feature_json(
        os.path.join(tmp, ".claude/features/rabbit-cage/feature.json"),
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


if FAIL:
    print("test-find-feature-plugin-mode: FAIL", file=sys.stderr)
    sys.exit(1)

print("test-find-feature-plugin-mode: all checks passed.")
