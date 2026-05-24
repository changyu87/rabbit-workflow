#!/usr/bin/env python3
"""test-producers-generate-claude-md.py — exercises the generate-claude-md
producer: composes a CLAUDE.md from a policy header JSON (a JSON file with
a top-level `header` string) plus one @-import line per `.md` file under
`policy_source`. @-import paths are emitted repo-root-relative; policy
files are emitted in alphabetical order; non-.md files in policy_source
are ignored.
"""

import json
import os
import sys
import tempfile

FEATURE_DIR = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, FEATURE_DIR)

from lib import producers  # noqa: E402

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


# t1: composes header + blank line + @-imports for each .md file
with tempfile.TemporaryDirectory() as td:
    feat = os.path.join(td, "feature")
    root = os.path.join(td, "repo")
    os.makedirs(feat)
    os.makedirs(root)
    _write(os.path.join(feat, "policy-header.json"),
           json.dumps({"header": "# Project\n\nLine two."}))
    policy_dir = os.path.join(root, ".claude/features/policy")
    _write(os.path.join(policy_dir, "alpha.md"), "alpha")
    _write(os.path.join(policy_dir, "beta.md"), "beta")
    out = producers.call_producer(
        "generate-claude-md",
        {"policy_source": ".claude/features/policy/",
         "header_source": "policy-header.json"},
        feature_dir=feat, repo_root=root,
    )
    expected = (
        "# Project\n\nLine two.\n"
        "\n"
        "@.claude/features/policy/alpha.md\n"
        "@.claude/features/policy/beta.md\n"
    )
    if out != expected:
        fail(f"t1: composition mismatch.\nexpected={expected!r}\nactual={out!r}")
    else:
        ok("t1: composes header + blank line + @-imports for each .md")

# t2: policy files are emitted in alphabetical order regardless of FS order
with tempfile.TemporaryDirectory() as td:
    feat = os.path.join(td, "feature")
    root = os.path.join(td, "repo")
    os.makedirs(feat)
    os.makedirs(root)
    _write(os.path.join(feat, "h.json"), json.dumps({"header": "H"}))
    policy_dir = os.path.join(root, ".claude/features/policy")
    for name in ("zulu.md", "alpha.md", "mike.md"):
        _write(os.path.join(policy_dir, name), name)
    out = producers.call_producer(
        "generate-claude-md",
        {"policy_source": ".claude/features/policy/", "header_source": "h.json"},
        feature_dir=feat, repo_root=root,
    )
    expected_imports = (
        "@.claude/features/policy/alpha.md\n"
        "@.claude/features/policy/mike.md\n"
        "@.claude/features/policy/zulu.md\n"
    )
    if not out.endswith(expected_imports):
        fail(f"t2: imports not in alphabetical order. tail={out[-200:]!r}")
    else:
        ok("t2: policy files emitted in alphabetical order")

# t3: non-.md files in policy_source are ignored
with tempfile.TemporaryDirectory() as td:
    feat = os.path.join(td, "feature")
    root = os.path.join(td, "repo")
    os.makedirs(feat)
    os.makedirs(root)
    _write(os.path.join(feat, "h.json"), json.dumps({"header": "H"}))
    policy_dir = os.path.join(root, ".claude/features/policy")
    _write(os.path.join(policy_dir, "real.md"), "x")
    _write(os.path.join(policy_dir, "README.txt"), "ignored")
    _write(os.path.join(policy_dir, "config.json"), "{}")
    out = producers.call_producer(
        "generate-claude-md",
        {"policy_source": ".claude/features/policy/", "header_source": "h.json"},
        feature_dir=feat, repo_root=root,
    )
    if ("README.txt" in out) or ("config.json" in out):
        fail(f"t3: non-.md files leaked into output: {out!r}")
    elif "@.claude/features/policy/real.md\n" not in out:
        fail(f"t3: real .md file missing from output: {out!r}")
    else:
        ok("t3: non-.md files in policy_source are ignored")

# t4: header_source resolves feature-dir-relative; policy_source repo-root-relative
with tempfile.TemporaryDirectory() as td:
    feat = os.path.join(td, "feature")
    root = os.path.join(td, "repo")
    os.makedirs(feat)
    os.makedirs(root)
    _write(os.path.join(feat, "policy-header.json"),
           json.dumps({"header": "HEAD"}))
    policy_dir = os.path.join(root, ".claude/features/policy")
    _write(os.path.join(policy_dir, "one.md"), "one")
    out = producers.call_producer(
        "generate-claude-md",
        {"policy_source": ".claude/features/policy/",
         "header_source": "policy-header.json"},
        feature_dir=feat, repo_root=root,
    )
    if out != "HEAD\n\n@.claude/features/policy/one.md\n":
        fail(f"t4: path-convention output unexpected: {out!r}")
    else:
        ok("t4: header_source resolves feature-dir; policy_source resolves repo-root")

if FAIL:
    print("test-producers-generate-claude-md: FAIL", file=sys.stderr)
    sys.exit(1)
print("test-producers-generate-claude-md: all checks passed.")
