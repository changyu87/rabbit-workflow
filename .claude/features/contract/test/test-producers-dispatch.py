#!/usr/bin/env python3
"""test-producers-dispatch.py — exercises lib.producers dispatcher surface:
the call_producer entry point, the PRODUCERS registry, and the _resolve
helper's path conventions (feature-dir vs repo-root).
"""

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


# t1: PRODUCERS registry contains read-file and expand-at-imports
missing = [n for n in ("read-file", "expand-at-imports") if n not in producers.PRODUCERS]
if missing:
    fail(f"t1: registry missing {missing!r}")
else:
    ok("t1: PRODUCERS registry contains read-file and expand-at-imports")

# t2: call_producer raises KeyError on unknown name
try:
    producers.call_producer("nope", {}, feature_dir="/tmp", repo_root="/tmp")
    fail("t2: expected KeyError, got success")
except KeyError as e:
    if "nope" in str(e):
        ok("t2: call_producer raises KeyError naming the unknown producer")
    else:
        fail(f"t2: KeyError raised but message does not mention name: {e}")

# t3: _resolve — absolute path passes through
abs_path = "/tmp/some-abs-path"
got = producers._resolve(abs_path, "/feat", "/repo")
if got != abs_path:
    fail(f"t3: absolute path not preserved: {got}")
else:
    ok("t3: _resolve preserves absolute paths unchanged")

# t4: _resolve — relative path starting with .claude/ resolves repo-root
got = producers._resolve(".claude/features/policy/", "/feat", "/repo")
if got != os.path.join("/repo", ".claude/features/policy/"):
    fail(f"t4: .claude/ path did not resolve repo-root-relative: {got}")
else:
    ok("t4: _resolve treats '.claude/'-prefixed paths as repo-root-relative")

# t5: _resolve — other relative paths resolve feature-dir
got = producers._resolve("policy-header.json", "/feat", "/repo")
if got != os.path.join("/feat", "policy-header.json"):
    fail(f"t5: bare path did not resolve feature-dir-relative: {got}")
else:
    ok("t5: _resolve treats bare paths as feature-dir-relative")

# t6: call_producer forwards feature_dir/repo_root and args as kwargs
# Inject a sentinel producer to verify forwarding.
captured = {}


def _sentinel(*, feature_dir, repo_root, alpha, beta):
    captured["feature_dir"] = feature_dir
    captured["repo_root"] = repo_root
    captured["alpha"] = alpha
    captured["beta"] = beta
    return "sentinel-output"


producers.PRODUCERS["__sentinel__"] = _sentinel
try:
    result = producers.call_producer(
        "__sentinel__", {"alpha": 1, "beta": "two"},
        feature_dir="/F", repo_root="/R",
    )
    if (result == "sentinel-output"
            and captured == {"feature_dir": "/F", "repo_root": "/R",
                             "alpha": 1, "beta": "two"}):
        ok("t6: call_producer forwards args + context kwargs to registered fn")
    else:
        fail(f"t6: unexpected dispatch behaviour: result={result!r} captured={captured}")
finally:
    del producers.PRODUCERS["__sentinel__"]

if FAIL:
    print("test-producers-dispatch: FAIL", file=sys.stderr)
    sys.exit(1)
print("test-producers-dispatch: all checks passed.")
