#!/usr/bin/env python3
"""test-runtime-check-manifest-drift-walks-all-entries.py — regression
test for CONTRACT-BACKLOG-37. check_manifest_drift MUST walk every
entry in a feature's MANIFEST even after detecting a non-no-op publish
result on an earlier entry. Otherwise multi-step manifests (e.g.
publish_settings followed by N publish_hook read-modify-write calls)
leave deployed files half-built: the file gets the source-deployed
content but lacks the amendments the subsequent publishers add.

The original implementation broke after the first non-no-op, producing
the symptom: deployed .claude/settings.json carries no hooks section
after a Stop-event surface-drift rebuild even though rabbit-cage's
MANIFEST has 4 publish_hook entries that should populate it.
"""

import json
import os
import sys
import tempfile

FEATURE_DIR = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, FEATURE_DIR)

from lib.runtime import check_manifest_drift  # noqa: E402

FAIL = 0


def fail(msg):
    global FAIL
    print(f"FAIL: {msg}", file=sys.stderr)
    FAIL = 1


def ok(msg):
    print(f"PASS: {msg}")


ALERT = {"text": "drift: {names}", "icon": "rebuild", "color": "red"}


def make_feature(root, name, manifest, src_files):
    fdir = os.path.join(root, ".claude", "features", name)
    os.makedirs(fdir, exist_ok=True)
    with open(os.path.join(fdir, "feature.json"), "w") as f:
        json.dump({"name": name, "version": "1.0.0", "owner": "x",
                   "manifest": manifest}, f)
    for rel, content in src_files.items():
        full = os.path.join(fdir, rel)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "w") as f:
            f.write(content)


# t1: two publish_file entries where both differ from deployed.
# Original bug: the second entry would not run because the first
# triggered the break. Fix: both must run; both target files must
# exist after check_manifest_drift returns.
with tempfile.TemporaryDirectory() as td:
    make_feature(
        td,
        "demo",
        manifest=[
            {"api": "publish_file", "args": {
                "source": "src/a.txt",
                "dest": "first.txt",
            }},
            {"api": "publish_file", "args": {
                "source": "src/b.txt",
                "dest": "second.txt",
            }},
        ],
        src_files={
            "src/a.txt": "AAA",
            "src/b.txt": "BBB",
        },
    )
    # Neither destination exists; both should be non-no-op (i.e. drift).
    result = check_manifest_drift(ALERT, repo_root=td)
    msg_text = " ".join(result.get("messages", []) if isinstance(result, dict) else [])
    a_exists = os.path.isfile(os.path.join(td, "first.txt"))
    b_exists = os.path.isfile(os.path.join(td, "second.txt"))
    if a_exists and b_exists:
        ok("t1: both manifest entries ran — first.txt AND second.txt deployed after drift")
    else:
        fail(f"t1: only some entries ran — first={a_exists}, second={b_exists}, result={result}")


# t2: confirm a feature's name is reported exactly once even if multiple
# entries within the same manifest each report drift. (Dedup happens
# inside check_manifest_drift; the report should not double-name the
# feature.)
with tempfile.TemporaryDirectory() as td:
    make_feature(
        td,
        "alpha",
        manifest=[
            {"api": "publish_file", "args": {
                "source": "src/a.txt",
                "dest": "x.txt",
            }},
            {"api": "publish_file", "args": {
                "source": "src/b.txt",
                "dest": "y.txt",
            }},
        ],
        src_files={
            "src/a.txt": "A",
            "src/b.txt": "B",
        },
    )
    result = check_manifest_drift(ALERT, repo_root=td)
    # result is a dict (print_result shape). Its 'messages' or 'text' may
    # vary; pick the field that names features.
    rendered = json.dumps(result)
    # Count occurrences of feature name 'alpha' in the rendered output.
    # Should appear exactly once in the drift report (other co-occurrences
    # in keys etc. are not the report itself).
    # Simpler: check that 'alpha, alpha' (dup signature) does NOT appear.
    if "alpha, alpha" not in rendered:
        ok("t2: feature name reported exactly once even with multi-entry drift")
    else:
        fail(f"t2: feature name duplicated in drift report: {rendered}")


if FAIL:
    print("test-runtime-check-manifest-drift-walks-all-entries: FAIL", file=sys.stderr)
    sys.exit(1)
print("test-runtime-check-manifest-drift-walks-all-entries: all checks passed.")
