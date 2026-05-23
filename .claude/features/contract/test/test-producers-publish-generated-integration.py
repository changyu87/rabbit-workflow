#!/usr/bin/env python3
"""test-producers-publish-generated-integration.py — end-to-end test that
publish_generated (lib.publish) invokes each of the three real producers
in lib.producers without a sys.modules stub, and writes the expected
output to the target file. Validates the late-import wiring in
publish_generated against the actual registry.
"""

import json
import os
import sys
import tempfile

FEATURE_DIR = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, FEATURE_DIR)

# Deliberately do NOT stub lib.producers — exercise the real module.
from lib.publish import publish_generated  # noqa: E402

FAIL = 0


def fail(msg):
    global FAIL
    print(f"FAIL: {msg}", file=sys.stderr)
    FAIL = 1


def ok(msg):
    print(f"PASS: {msg}")


def _write(path, content):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write(content)


# t1: publish_generated with read-file writes the source contents to target
with tempfile.TemporaryDirectory() as td:
    feat = os.path.join(td, "feature")
    root = os.path.join(td, "repo")
    os.makedirs(feat)
    os.makedirs(root)
    _write(os.path.join(feat, "src.txt"), "raw\n")
    r = publish_generated(
        "out.txt", "read-file", {"path": "src.txt"},
        feature_dir=feat, repo_root=root,
    )
    if not r.passed:
        fail(f"t1: publish_generated read-file failed: {r.messages}")
    elif open(os.path.join(root, "out.txt")).read() != "raw\n":
        fail("t1: read-file output did not match source")
    else:
        ok("t1: publish_generated routes through real read-file producer")

# t2: publish_generated with expand-at-imports expands one-level imports
with tempfile.TemporaryDirectory() as td:
    feat = os.path.join(td, "feature")
    root = os.path.join(td, "repo")
    os.makedirs(feat)
    os.makedirs(root)
    _write(os.path.join(feat, "leaf.md"), "LEAF\n")
    _write(os.path.join(feat, "top.md"), "preface\n@leaf.md\n")
    r = publish_generated(
        "OUT.md", "expand-at-imports", {"file": "top.md"},
        feature_dir=feat, repo_root=root,
    )
    expected = "preface\nLEAF\n"
    if not r.passed:
        fail(f"t2: publish_generated expand-at-imports failed: {r.messages}")
    elif open(os.path.join(root, "OUT.md")).read() != expected:
        fail(f"t2: expansion output mismatch: {open(os.path.join(root, 'OUT.md')).read()!r}")
    else:
        ok("t2: publish_generated routes through real expand-at-imports producer")

# t3: publish_generated with generate-claude-md composes header + @-imports
with tempfile.TemporaryDirectory() as td:
    feat = os.path.join(td, "feature")
    root = os.path.join(td, "repo")
    os.makedirs(feat)
    os.makedirs(root)
    _write(os.path.join(feat, "policy-header.json"),
           json.dumps({"header": "# H"}))
    policy_dir = os.path.join(root, ".claude/features/policy")
    _write(os.path.join(policy_dir, "a.md"), "")
    _write(os.path.join(policy_dir, "b.md"), "")
    r = publish_generated(
        "CLAUDE.md", "generate-claude-md",
        {"policy_source": ".claude/features/policy/",
         "header_source": "policy-header.json"},
        feature_dir=feat, repo_root=root,
    )
    expected = "# H\n\n@.claude/features/policy/a.md\n@.claude/features/policy/b.md\n"
    if not r.passed:
        fail(f"t3: publish_generated generate-claude-md failed: {r.messages}")
    elif open(os.path.join(root, "CLAUDE.md")).read() != expected:
        fail(f"t3: composed CLAUDE.md mismatch: {open(os.path.join(root, 'CLAUDE.md')).read()!r}")
    else:
        ok("t3: publish_generated routes through real generate-claude-md producer")

# t4: idempotency holds end-to-end — second call is a no-op
with tempfile.TemporaryDirectory() as td:
    feat = os.path.join(td, "feature")
    root = os.path.join(td, "repo")
    os.makedirs(feat)
    os.makedirs(root)
    _write(os.path.join(feat, "src.txt"), "x\n")
    publish_generated("o.txt", "read-file", {"path": "src.txt"},
                      feature_dir=feat, repo_root=root)
    r2 = publish_generated("o.txt", "read-file", {"path": "src.txt"},
                           feature_dir=feat, repo_root=root)
    if not r2.passed:
        fail(f"t4: second call failed: {r2.messages}")
    elif not any("no-op" in m.lower() for m in r2.messages):
        fail(f"t4: second call should report no-op: {r2.messages}")
    else:
        ok("t4: end-to-end idempotency through real producers")

if FAIL:
    print("test-producers-publish-generated-integration: FAIL", file=sys.stderr)
    sys.exit(1)
print("test-producers-publish-generated-integration: all checks passed.")
