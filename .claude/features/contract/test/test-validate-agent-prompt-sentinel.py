#!/usr/bin/env python3
"""test-validate-agent-prompt-sentinel.py — Inv 56 (b)

End-to-end tests for contract.lib.checks.validate_agent_prompt_sentinel.

Covers the 5 cases declared in Inv 56 enforcement section:
  (i)   prompt containing sentinel → passed=True
  (ii)  prompt missing sentinel + no bypass marker → passed=False (canonical msg)
  (iii) prompt missing sentinel + bypass marker present → passed=True
  (iv)  empty/missing prompt key → passed=False
  (v)   non-string prompt (defensive) → passed=False

Run non-interactively. Exits non-zero on failure.
"""

import importlib.util
import os
import sys
import tempfile

FEATURE_DIR = os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
)
CHECKS_PATH = os.path.join(FEATURE_DIR, "lib", "checks.py")
SENTINEL = "RABBIT-POLICY-BLOCK-v1"
CANONICAL_MSG_FRAGMENT = "Agent dispatch missing RABBIT-POLICY-BLOCK-v1 sentinel"

PASS = 0
FAIL = 0


def ok(name, msg):
    global PASS
    print(f"  PASS {name}: {msg}")
    PASS += 1


def fail(name, msg):
    global FAIL
    print(f"  FAIL {name}: {msg}", file=sys.stderr)
    FAIL += 1


def load_checks():
    spec = importlib.util.spec_from_file_location(
        "contract_lib_checks", CHECKS_PATH
    )
    if spec is None or spec.loader is None:
        return None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


checks = load_checks()
if checks is None:
    fail("load", f"cannot import {CHECKS_PATH}")
    sys.exit(1)

if not hasattr(checks, "validate_agent_prompt_sentinel"):
    fail(
        "exists",
        "contract.lib.checks must export validate_agent_prompt_sentinel "
        "(Inv 56 b)",
    )
    sys.exit(1)
ok("exists", "validate_agent_prompt_sentinel exported")

validate = checks.validate_agent_prompt_sentinel


# Use a fresh tmp dir as repo_root so no bypass marker exists by default
with tempfile.TemporaryDirectory() as tmp:
    repo_root = tmp

    # case (i): prompt contains sentinel → passed=True
    tool_input = {"prompt": f"some prefix\n{SENTINEL}\nsome suffix"}
    res = validate(tool_input, repo_root=repo_root)
    if res.passed and res.messages == []:
        ok("i", "sentinel present → passed=True, empty messages")
    else:
        fail(
            "i",
            f"expected passed=True/messages=[]; got passed={res.passed}, "
            f"messages={res.messages}",
        )

    # case (ii): prompt missing sentinel + no bypass → passed=False
    tool_input = {"prompt": "this prompt has no sentinel"}
    res = validate(tool_input, repo_root=repo_root)
    if not res.passed and any(CANONICAL_MSG_FRAGMENT in m for m in res.messages):
        ok("ii", "missing sentinel → passed=False with canonical message")
    else:
        fail(
            "ii",
            f"expected passed=False + canonical msg; got passed={res.passed}, "
            f"messages={res.messages}",
        )

    # case (iv): missing prompt key → passed=False
    tool_input = {}
    res = validate(tool_input, repo_root=repo_root)
    if not res.passed and any(CANONICAL_MSG_FRAGMENT in m for m in res.messages):
        ok("iv-missing", "missing prompt key → passed=False")
    else:
        fail(
            "iv-missing",
            f"expected passed=False; got passed={res.passed}, "
            f"messages={res.messages}",
        )

    # case (iv): empty prompt → passed=False
    tool_input = {"prompt": ""}
    res = validate(tool_input, repo_root=repo_root)
    if not res.passed and any(CANONICAL_MSG_FRAGMENT in m for m in res.messages):
        ok("iv-empty", "empty prompt → passed=False")
    else:
        fail(
            "iv-empty",
            f"expected passed=False; got passed={res.passed}, "
            f"messages={res.messages}",
        )

    # case (v): non-string prompt → passed=False
    for non_str in (None, 123, ["a", "list"], {"nested": "dict"}):
        tool_input = {"prompt": non_str}
        res = validate(tool_input, repo_root=repo_root)
        if not res.passed:
            ok("v", f"non-string prompt ({type(non_str).__name__}) → passed=False")
        else:
            fail(
                "v",
                f"expected passed=False for non-string prompt "
                f"{non_str!r}; got passed={res.passed}",
            )


# case (iii): bypass marker present → passed=True even without sentinel
with tempfile.TemporaryDirectory() as tmp:
    repo_root = tmp
    rabbit_dir = os.path.join(repo_root, ".rabbit")
    os.makedirs(rabbit_dir)
    marker_path = os.path.join(rabbit_dir, "agent-sentinel-bypass")
    with open(marker_path, "w") as f:
        f.write("")

    tool_input = {"prompt": "no sentinel here either"}
    res = validate(tool_input, repo_root=repo_root)
    if res.passed:
        ok("iii", "bypass marker present → passed=True without sentinel")
    else:
        fail(
            "iii",
            f"expected passed=True with bypass marker; got passed={res.passed}, "
            f"messages={res.messages}",
        )

    # Same with missing prompt key — bypass still wins
    tool_input = {}
    res = validate(tool_input, repo_root=repo_root)
    if res.passed:
        ok("iii-missing", "bypass + missing prompt key → passed=True")
    else:
        fail(
            "iii-missing",
            f"expected passed=True; got passed={res.passed}, "
            f"messages={res.messages}",
        )


print()
print(f"PASS: {PASS}, FAIL: {FAIL}")
sys.exit(0 if FAIL == 0 else 1)
