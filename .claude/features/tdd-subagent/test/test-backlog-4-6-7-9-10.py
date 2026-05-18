#!/usr/bin/env python3
# E2E tests for TDD-SUBAGENT-BACKLOG-4, 6, 7, 9, 10.
#
# BACKLOG-4: dispatch-tdd-subagent.py emits a distinct yellow [rabbit] note
#            in the prompt preamble when .rabbit-human-approval-bypass exists.
# BACKLOG-6: feature.json schema reference declared in spec; the contract
#            schema enum lists `spec-update`.
# BACKLOG-7: assembled prompt includes a JSON HANDOFF schema (HANDOFF_JSON
#            block + handoff_schema_version) alongside YAML HANDOFF.
# BACKLOG-9: agents/tdd-subagent.md does NOT instruct the subagent to
#            choose between an agent-local and feature-local scripts path.
# BACKLOG-10: test_helpers.py exists with make_feature_dir() and the three
#            legacy fixture tests import it.
import json
import os
import subprocess
import sys
import tempfile

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
FEATURE_DIR = os.path.join(REPO_ROOT, ".claude", "features", "tdd-subagent")
DISPATCH = os.path.join(FEATURE_DIR, "scripts", "dispatch-tdd-subagent.py")
AGENT_MD = os.path.join(FEATURE_DIR, "agents", "tdd-subagent.md")
SPEC_MD = os.path.join(FEATURE_DIR, "docs", "spec", "spec.md")
HELPERS = os.path.join(FEATURE_DIR, "test", "test_helpers.py")
SCHEMA = os.path.join(
    REPO_ROOT, ".claude", "features", "contract", "schemas", "feature.json.schema.json"
)
MARKER = os.path.join(REPO_ROOT, ".rabbit-human-approval-bypass")

PASS = 0
FAIL = 0


def ok(msg):
    global PASS
    print(f"  ok   {msg}")
    PASS += 1


def ko(msg):
    global FAIL
    print(f"  FAIL {msg}")
    FAIL += 1


def run_dispatch(extra_env=None):
    env = os.environ.copy()
    env["RABBIT_ROOT"] = REPO_ROOT
    if extra_env:
        env.update(extra_env)
    spec_path = SPEC_MD
    return subprocess.run(
        [
            sys.executable,
            DISPATCH,
            "--scope", "tdd-subagent",
            "--spec", spec_path,
        ],
        capture_output=True, text=True, env=env,
    )


# BACKLOG-4: dispatch shows a yellow bypass note when marker exists.
def b4():
    # Marker absent -> no yellow note.
    marker_existed = os.path.isfile(MARKER)
    if marker_existed:
        os.unlink(MARKER)
    try:
        r = run_dispatch()
        if r.returncode != 0:
            ko(f"b4: dispatch failed without marker: {r.stderr}")
            return
        if "HUMAN APPROVAL BYPASS" in r.stdout and "\x1b[33m" in r.stdout:
            ko("b4: yellow bypass note appeared when marker absent (false positive)")
            return
        ok("b4a: no bypass note in prompt when marker absent")

        # Marker present -> yellow note in preamble.
        with open(MARKER, "w") as f:
            f.write("")
        r = run_dispatch()
        if r.returncode != 0:
            ko(f"b4: dispatch failed with marker: {r.stderr}")
            return
        out = r.stdout
        if "\x1b[33m" not in out:
            ko("b4b: prompt missing yellow ANSI \\x1b[33m for bypass note")
            return
        if ".rabbit-human-approval-bypass" not in out:
            ko("b4b: prompt bypass note does not name the marker path")
            return
        if "/rabbit-config human-approval true" not in out:
            ko("b4b: prompt bypass note does not name the revoke skill")
            return
        if "[rabbit]" not in out:
            ko("b4b: prompt bypass note missing [rabbit] tag")
            return
        # Note must be in preamble, before STEP 1 SPEC-READ.
        pre = out.split("STEP 1")[0]
        if "\x1b[33m" not in pre:
            ko("b4b: yellow bypass note not in preamble (before STEP 1)")
            return
        ok("b4b: yellow bypass note in preamble when marker present")
    finally:
        # Restore marker state.
        if os.path.isfile(MARKER):
            os.unlink(MARKER)
        if marker_existed:
            with open(MARKER, "w") as f:
                f.write("")


# BACKLOG-6: spec invariant 33 references the contract schema; the
# contract schema enum lists `spec-update`.
def b6():
    with open(SPEC_MD) as f:
        spec = f.read()
    if "feature.json.schema.json" not in spec:
        ko("b6: spec does not reference feature.json.schema.json")
        return
    if "Inv 33" in spec or "33." in spec:
        ok("b6a: spec declares feature.json schema reference (Inv 33)")
    else:
        ko("b6a: spec missing Inv 33 schema reference")
        return
    if not os.path.isfile(SCHEMA):
        ko(f"b6: schema file missing: {SCHEMA}")
        return
    with open(SCHEMA) as f:
        sch = json.load(f)
    enum = sch.get("properties", {}).get("tdd_state", {}).get("enum", [])
    if "spec-update" not in enum:
        ko(f"b6b: schema tdd_state.enum missing 'spec-update': {enum}")
        return
    ok("b6b: schema tdd_state.enum includes 'spec-update'")


# BACKLOG-7: assembled prompt has HANDOFF_JSON block and handoff_schema_version.
# The check inspects the prompt AFTER the SPEC body so spec text alone does
# not satisfy the test (the spec mentions HANDOFF_JSON when documenting the
# behaviour, but the prompt MUST also include an instruction block).
def b7():
    r = run_dispatch()
    if r.returncode != 0:
        ko(f"b7: dispatch failed: {r.stderr}")
        return
    out = r.stdout
    # Slice off everything up to and including the SPEC body so we only
    # inspect prompt instructions the dispatcher itself authored.
    if "STEP 9 — UNLOCK" not in out:
        ko("b7: prompt missing STEP 9 — UNLOCK heading")
        return
    tail = out[out.index("STEP 9 — UNLOCK"):]
    if "HANDOFF_JSON:" not in tail:
        ko("b7: prompt missing 'HANDOFF_JSON:' marker after STEP 9")
        return
    if "handoff_schema_version" not in tail:
        ko("b7: prompt missing 'handoff_schema_version' field after STEP 9")
        return
    if '"1.0.0"' not in tail:
        ko("b7: prompt missing handoff schema version '1.0.0' after STEP 9")
        return
    # Legacy YAML HANDOFF must also remain for backward compatibility.
    if "HANDOFF:" not in tail:
        ko("b7: prompt missing legacy 'HANDOFF:' block after STEP 9")
        return
    ok("b7: prompt includes structured HANDOFF_JSON schema v1.0.0 + legacy YAML")


# BACKLOG-9: agent file does not describe a dual-path scripts layout.
def b9():
    with open(AGENT_MD) as f:
        content = f.read()
    # The confusing dual-path phrasing must be gone.
    if "agent-local" in content:
        ko("b9: agents/tdd-subagent.md still mentions 'agent-local' scripts path")
        return
    # The phrase "Use the deployed path" was tied to the dual-path advice;
    # it should also be gone.
    if "deployed path when invoking from outside" in content:
        ko("b9: agents/tdd-subagent.md still has stale 'deployed path' note")
        return
    ok("b9: agents/tdd-subagent.md dual-path note removed")


# BACKLOG-10: test_helpers.py exists with make_feature_dir; three tests
# import it (no longer define their own fix()).
def b10():
    if not os.path.isfile(HELPERS):
        ko(f"b10: test_helpers.py missing: {HELPERS}")
        return
    with open(HELPERS) as f:
        h = f.read()
    if "def make_feature_dir" not in h:
        ko("b10: test_helpers.py missing make_feature_dir()")
        return
    ok("b10a: test_helpers.py exists with make_feature_dir()")

    # Validate the helper writes a flat-schema feature.json.
    tmp = tempfile.mkdtemp()
    try:
        # Import the module fresh.
        import importlib.util
        spec = importlib.util.spec_from_file_location("th", HELPERS)
        th = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(th)
        d = os.path.join(tmp, "x")
        th.make_feature_dir(d, "x", "impl")
        with open(os.path.join(d, "feature.json")) as f:
            fj = json.load(f)
        # Must be flat shape.
        if not isinstance(fj.get("owner"), str):
            ko(f"b10b: helper feature.json owner not string: {fj.get('owner')}")
            return
        if "deprecation_criterion" not in fj:
            ko("b10b: helper feature.json missing flat deprecation_criterion")
            return
        if "deprecation" in fj and isinstance(fj["deprecation"], dict):
            ko("b10b: helper feature.json still has legacy nested deprecation object")
            return
        if fj.get("tdd_state") != "impl":
            ko(f"b10b: helper tdd_state wrong: {fj.get('tdd_state')}")
            return
        # Required sibling files must exist.
        for sib in ("spec.md", "contract.md", os.path.join("test", "run.py")):
            if not os.path.exists(os.path.join(d, sib)):
                ko(f"b10b: helper did not create {sib}")
                return
        ok("b10b: make_feature_dir() writes flat schema + sibling files")
    finally:
        import shutil
        shutil.rmtree(tmp, ignore_errors=True)

    # Three legacy fixture tests must import the helper.
    for t in ("test-tdd-step.py", "test-context.py", "test-drift-check.py"):
        p = os.path.join(FEATURE_DIR, "test", t)
        with open(p) as f:
            content = f.read()
        if "from test_helpers import" not in content and "import test_helpers" not in content:
            ko(f"b10c: {t} does not import test_helpers")
            return
    ok("b10c: test-tdd-step.py, test-context.py, test-drift-check.py import test_helpers")


b4()
b6()
b7()
b9()
b10()

print()
if FAIL == 0:
    print(f"backlog-4/6/7/9/10: {PASS} passed.")
    sys.exit(0)
print(f"backlog-4/6/7/9/10: {FAIL} failure(s), {PASS} passed.")
sys.exit(1)
