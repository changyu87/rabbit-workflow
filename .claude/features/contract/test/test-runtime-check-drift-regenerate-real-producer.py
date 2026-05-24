#!/usr/bin/env python3
"""test-runtime-check-drift-regenerate-real-producer.py — BUG-43 regression.

Exercises check_drift_regenerate end-to-end against the REAL
lib.producers.generate_claude_md producer (no stub). The pre-fix code path
hardcoded an empty args dict when calling call_producer, so producers
requiring named args (e.g. generate-claude-md needs policy_source +
header_source) raised TypeError and the API silently returned an
error_result. After CONTRACT-BUG-43 fix, check_drift_regenerate accepts
an optional `args: dict` parameter and forwards it to call_producer.

Asserts:
  - First call (target absent): returns [print_result, inject_result] and
    writes the composed CLAUDE.md to target.
  - Second call (target now matches): returns ok_result without rewriting.
  - No TypeError surfaces (the alert path uses an actual print result; an
    error_result on either call indicates the BUG-43 regression).
"""

import json
import os
import sys
import tempfile

FEATURE_DIR = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, FEATURE_DIR)

# IMPORTANT: do NOT stub lib.producers; this test exercises the real one.
from lib.runtime import check_drift_regenerate  # noqa: E402

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


ALERT = {"text": "CLAUDE.md regenerated", "icon": "warn", "color": "red"}

# t1: target absent, real producer called with forwarded args.
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

    args = {
        "policy_source": ".claude/features/policy",
        "header_source": "policy-header.json",
    }
    r = check_drift_regenerate(
        "CLAUDE.md", "generate-claude-md", ALERT, args,
        feature_dir=feat, repo_root=root,
    )

    # Assert: no TypeError -> not an error_result; we got the regen branch.
    if isinstance(r, dict) and r.get("type") == "error":
        fail(f"t1: error_result returned (BUG-43 regression): {r!r}")
    elif not (isinstance(r, list) and len(r) == 2
              and r[0].get("type") == "print"
              and r[1].get("type") == "inject"):
        fail(f"t1: expected [print, inject], got {r!r}")
    else:
        target = os.path.join(root, "CLAUDE.md")
        if not os.path.isfile(target):
            fail(f"t1: target not written: {target}")
        else:
            with open(target) as f:
                wrote = f.read()
            # Body should carry the header text and both @-imports in
            # alphabetical order.
            expected_imports = (
                "@.claude/features/policy/alpha.md\n"
                "@.claude/features/policy/beta.md\n"
            )
            if "# Project" in wrote and wrote.endswith(expected_imports):
                ok("t1: real producer executed; [print, inject] returned; target written")
            else:
                fail(f"t1: target content unexpected: {wrote!r}")

    # t2: invoke again; target now matches producer output -> ok_result.
    r2 = check_drift_regenerate(
        "CLAUDE.md", "generate-claude-md", ALERT, args,
        feature_dir=feat, repo_root=root,
    )
    if isinstance(r2, dict) and r2.get("type") == "ok":
        ok("t2: second call returns ok_result (target matches producer output)")
    elif isinstance(r2, dict) and r2.get("type") == "error":
        fail(f"t2: error_result on second call (BUG-43 regression): {r2!r}")
    else:
        fail(f"t2: expected ok_result, got {r2!r}")


# t3: omitting the args parameter (default None) MUST NOT TypeError; the
# producer will simply fail its own required-args check, which becomes an
# error_result rather than a Python-level exception bubbling out.
with tempfile.TemporaryDirectory() as td:
    feat = os.path.join(td, "feature")
    root = os.path.join(td, "repo")
    os.makedirs(feat)
    os.makedirs(root)
    r = check_drift_regenerate(
        "CLAUDE.md", "generate-claude-md", ALERT,
        feature_dir=feat, repo_root=root,
    )
    # Producer raises TypeError internally (missing kwargs); runtime catches
    # and returns an error_result. The key assertion is: no uncaught
    # TypeError from the runtime API surface.
    if isinstance(r, dict) and r.get("type") == "error":
        ok("t3: omitted args -> producer fails inside the API; surfaced as error_result (no TypeError leak)")
    else:
        fail(f"t3: expected error_result when args omitted, got {r!r}")


if FAIL:
    print("test-runtime-check-drift-regenerate-real-producer: FAIL",
          file=sys.stderr)
    sys.exit(1)
print("test-runtime-check-drift-regenerate-real-producer: all checks passed.")
