#!/usr/bin/env python3
"""test-prompt-injector-hook.py — Inv 55

E2E test that hooks/prompt-injector.py implements the PreToolUse Skill
injection behaviour described in spec Inv 55.

Tests pipe a PreToolUse JSON event on stdin and assert the hook's
stdout JSON and exit code.

t-skill-registered: tool_name=Skill with a registered skill id emits
                    additionalContext containing the assembled prompt.
t-skill-unregistered: tool_name=Skill with an unknown skill emits {} silently.
t-agent: tool_name=Agent (non-Skill) emits {} silently.

Each test points RABBIT_ROOT at a tmpdir whose `.claude/features/contract`
subtree symlinks back to the real contract feature's scripts/ and lib/
dirs (so the hook's subprocess invocation of build-prompt.py works
against a controlled features tree).

Version: 1.0.0
Owner: rabbit-workflow team (contract)
Deprecation criterion: when Claude Code exposes a native prompt-injection mechanism.
"""

import json
import os
import subprocess
import sys
import tempfile

FEATURE_DIR = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), ".."))
HOOK = os.path.join(FEATURE_DIR, "hooks", "prompt-injector.py")
REAL_SCRIPTS = os.path.join(FEATURE_DIR, "scripts")
REAL_LIB = os.path.join(FEATURE_DIR, "lib")
REAL_TEMPLATES = os.path.join(FEATURE_DIR, "templates")

FAIL = 0


def ok(msg):
    print(f"PASS: {msg}")


def fail(msg):
    global FAIL
    print(f"FAIL: {msg}", file=sys.stderr)
    FAIL = 1


BASE_FEATURE = {
    "name": "fakefeat",
    "version": "1.0.0",
    "owner": "rabbit-workflow team",
    "tdd_state": "spec",
    "summary": "fake test feature",
    "surface": {},
    "deprecation_criterion": "when the test ends",
}


def make_tree(tmpdir, prompts_entry, template_body):
    """Build a fake .claude/features/ tree with contract scripts/lib symlinked in.

    Returns tmpdir (RABBIT_ROOT).
    """
    features_root = os.path.join(tmpdir, ".claude", "features")
    os.makedirs(features_root)
    # policy/philosophy.md
    policy_dir = os.path.join(features_root, "policy")
    os.makedirs(policy_dir)
    with open(os.path.join(policy_dir, "philosophy.md"), "w") as f:
        f.write("PHILOSOPHY-MARKER\n")
    # Symlink contract feature: scripts/, lib/ from the real tree
    # so build-prompt.py's import of lib.policy_block works.
    contract_dir = os.path.join(features_root, "contract")
    os.makedirs(contract_dir)
    os.symlink(REAL_SCRIPTS, os.path.join(contract_dir, "scripts"))
    os.symlink(REAL_LIB, os.path.join(contract_dir, "lib"))
    # templates/ must be writable (we add prompts/<id>.txt), so don't symlink
    # the whole dir — make a real templates/prompts subdir.
    tpl_dir = os.path.join(contract_dir, "templates", "prompts")
    os.makedirs(tpl_dir)
    if prompts_entry is not None and template_body is not None:
        with open(os.path.join(tpl_dir, f"{prompts_entry['id']}.txt"), "w") as f:
            f.write(template_body)
    # fakefeat with prompts entry
    fdir = os.path.join(features_root, "fakefeat")
    os.makedirs(fdir)
    data = dict(BASE_FEATURE)
    if prompts_entry is not None:
        data["prompts"] = [prompts_entry]
    with open(os.path.join(fdir, "feature.json"), "w") as f:
        json.dump(data, f)
    return tmpdir


def run_hook(repo_root, stdin_payload):
    env = dict(os.environ)
    env["RABBIT_ROOT"] = repo_root
    return subprocess.run(
        ["python3", HOOK],
        input=json.dumps(stdin_payload),
        capture_output=True, text=True, env=env,
        timeout=30,
    )


# ---------- t-skill-registered ----------
with tempfile.TemporaryDirectory() as td:
    entry = {
        "id": "test-skill",
        "kind": "skill",
        "inject": [".claude/features/policy/philosophy.md"],
        "slots": ["args"],
    }
    make_tree(td, entry, template_body="ARGS={{args}}\n")
    r = run_hook(td, {
        "tool_name": "Skill",
        "tool_input": {"skill": "test-skill", "args": "hello"},
    })
    if r.returncode != 0:
        fail(f"t-skill-registered: expected exit 0, got {r.returncode}; stderr={r.stderr!r}")
    else:
        try:
            payload = json.loads(r.stdout)
        except json.JSONDecodeError as e:
            fail(f"t-skill-registered: stdout is not valid JSON: {e}; stdout={r.stdout!r}")
            payload = None
        if payload is not None:
            hso = payload.get("hookSpecificOutput", {})
            if hso.get("hookEventName") != "PreToolUse":
                fail(f"t-skill-registered: hookEventName must be PreToolUse; got {hso!r}")
            ac = hso.get("additionalContext", "")
            for token in ("RABBIT-POLICY-BLOCK-v1", "PHILOSOPHY-MARKER", "ARGS=hello"):
                if token not in ac:
                    fail(f"t-skill-registered: additionalContext missing token {token!r}")
            if FAIL == 0:
                ok("t-skill-registered: additionalContext contains assembled prompt")

# ---------- t-skill-unregistered ----------
with tempfile.TemporaryDirectory() as td:
    # No prompts entry registered
    make_tree(td, None, template_body=None)
    r = run_hook(td, {
        "tool_name": "Skill",
        "tool_input": {"skill": "unknown-skill", "args": "x"},
    })
    if r.returncode != 0:
        fail(f"t-skill-unregistered: expected exit 0, got {r.returncode}; stderr={r.stderr!r}")
    else:
        try:
            payload = json.loads(r.stdout)
        except json.JSONDecodeError as e:
            fail(f"t-skill-unregistered: stdout is not valid JSON: {e}; stdout={r.stdout!r}")
            payload = None
        if payload is not None:
            if payload != {}:
                fail(f"t-skill-unregistered: expected silent {{}} output, got {payload!r}")
            else:
                ok("t-skill-unregistered: silent {} on unregistered skill")

# ---------- t-agent ----------
with tempfile.TemporaryDirectory() as td:
    make_tree(td, None, template_body=None)
    r = run_hook(td, {
        "tool_name": "Agent",
        "tool_input": {"prompt": "hello"},
    })
    if r.returncode != 0:
        fail(f"t-agent: expected exit 0, got {r.returncode}; stderr={r.stderr!r}")
    else:
        try:
            payload = json.loads(r.stdout)
        except json.JSONDecodeError as e:
            fail(f"t-agent: stdout is not valid JSON: {e}; stdout={r.stdout!r}")
            payload = None
        if payload is not None:
            if payload != {}:
                fail(f"t-agent: expected silent {{}} output, got {payload!r}")
            else:
                ok("t-agent: silent {} on non-Skill tool")

if FAIL:
    print("test-prompt-injector-hook: FAIL", file=sys.stderr)
    sys.exit(1)
print("test-prompt-injector-hook: all checks passed.")
