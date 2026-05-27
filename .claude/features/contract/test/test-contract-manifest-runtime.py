#!/usr/bin/env python3
"""test-contract-manifest-runtime.py — verifies contract feature.json
declares EXACTLY one manifest entry (publish_hook for the prompt-injector
source) and runtime.Stop with EXACTLY two entries in fixed order
(check_prompt_injection_failures, then cleanup_old_prompts). Configuration
remains absent or [].
"""

import json
import os
import sys

FEATURE_DIR = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
FEATURE_JSON = os.path.join(FEATURE_DIR, "feature.json")

FAIL = 0


def fail(msg):
    global FAIL
    print(f"FAIL: {msg}", file=sys.stderr)
    FAIL = 1


def ok(msg):
    print(f"PASS: {msg}")


with open(FEATURE_JSON) as f:
    data = json.load(f)

# manifest
manifest = data.get("manifest")
if not isinstance(manifest, list):
    fail(f"manifest must be a list, got {type(manifest).__name__}")
elif len(manifest) != 1:
    fail(f"manifest must have exactly 1 entry, got {len(manifest)}")
else:
    entry = manifest[0]
    expected = {"api": "publish_hook",
                "args": {"event": "PreToolUse",
                          "source": "hooks/prompt-injector.py"}}
    if entry == expected:
        ok("manifest[0] == publish_hook for hooks/prompt-injector.py at PreToolUse")
    else:
        fail(f"manifest[0] mismatch: expected {expected!r}, got {entry!r}")

# runtime
runtime = data.get("runtime")
if not isinstance(runtime, dict):
    fail(f"runtime must be a dict, got {type(runtime).__name__}")
elif set(runtime.keys()) != {"Stop"}:
    fail(f"runtime must have exactly one key 'Stop', got {sorted(runtime.keys())}")
else:
    stop = runtime["Stop"]
    if not isinstance(stop, list) or len(stop) != 2:
        fail(f"runtime.Stop must be a list of length 2, got {stop!r}")
    else:
        e0 = stop[0]
        e1 = stop[1]
        exp0 = {"api": "check_prompt_injection_failures",
                "args": {"log_path": ".rabbit/prompts/.injection-failures.log"}}
        exp1 = {"api": "cleanup_old_prompts", "args": {"max_age_days": 7}}
        if e0 == exp0:
            ok("runtime.Stop[0] == check_prompt_injection_failures with correct log_path")
        else:
            fail(f"runtime.Stop[0] mismatch: expected {exp0!r}, got {e0!r}")
        if e1 == exp1:
            ok("runtime.Stop[1] == cleanup_old_prompts with max_age_days=7")
        else:
            fail(f"runtime.Stop[1] mismatch: expected {exp1!r}, got {e1!r}")

# configuration absent or []
configuration = data.get("configuration", [])
if configuration == [] or "configuration" not in data:
    ok("configuration is absent or []")
else:
    fail(f"configuration must be absent or [], got {configuration!r}")


if FAIL:
    print("test-contract-manifest-runtime: FAIL", file=sys.stderr)
    sys.exit(1)
print("test-contract-manifest-runtime: all checks passed.")
