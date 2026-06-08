#!/usr/bin/env python3
"""test-build-prompt.py — Inv 46

E2E test that scripts/build-prompt.py assembles a prompt file from the
policy block plus a slot-substituted template body, walks
.claude/features/*/feature.json to find the matching prompts entry,
and exits 0/1/2 with the documented semantics.

Tests run the CLI under RABBIT_ROOT=<tmpdir> to point the discovery
walk at a controlled features tree.

t-success: well-formed call writes a file containing the sentinel,
           the philosophy content, and the slot-substituted body.
t-missing-slot: --callable-id provided but a declared slot is unset →
                exit 1 with diagnostic on stderr.
t-unknown-id:  --callable-id names no entry → exit 2 with diagnostic.
t-value-with-placeholder-text: slot value contains literal {{declared_name}}
                substring → exit 0 (declared name MUST NOT be flagged as
                orphan; slot values are user data).
t-true-orphan: template body contains a {{name}} not in declared slots →
                exit 1 with stderr naming the undeclared name.
t-mixed-declared-and-undeclared: body has one declared and one undeclared
                placeholder; slot value also contains literal {{declared}} →
                exit 1 with stderr naming ONLY the undeclared one.
t-standalone-out-dir: repo_root basename is NOT `.rabbit` → the assembled
                prompt lands under <repo_root>/.rabbit/prompts/ (Inv 52).
t-vendored-out-dir-no-doubling: repo_root basename IS `.rabbit` (vendored
                install) → the assembled prompt lands under a SINGLE
                .rabbit segment <repo_root>/prompts/, never the doubled
                <repo_root>/.rabbit/prompts/ (Inv 52).

Version: 1.1.0
Owner: rabbit-workflow team (contract)
Deprecation criterion: when prompt-contract assembly is native to Claude Code.
"""

import json
import os
import subprocess
import sys
import tempfile

FEATURE_DIR = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), ".."))
BUILD_PROMPT = os.path.join(FEATURE_DIR, "scripts", "build-prompt.py")

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


def make_tree(tmpdir, prompts_entry, *, template_body, philosophy_body="PHILOSOPHY-MARKER\n"):
    """Build a fake .claude/features/ tree under tmpdir.

    Returns the tmpdir (which serves as RABBIT_ROOT).
    """
    features_root = os.path.join(tmpdir, ".claude", "features")
    os.makedirs(features_root)
    # policy/philosophy.md
    policy_dir = os.path.join(features_root, "policy")
    os.makedirs(policy_dir)
    with open(os.path.join(policy_dir, "philosophy.md"), "w") as f:
        f.write(philosophy_body)
    # templates/prompts/<id>.txt under contract feature
    if prompts_entry is not None and template_body is not None:
        tpl_dir = os.path.join(features_root, "contract", "templates", "prompts")
        os.makedirs(tpl_dir, exist_ok=True)
        with open(os.path.join(tpl_dir, f"{prompts_entry['id']}.txt"), "w") as f:
            f.write(template_body)
    # fakefeat with the prompts entry
    fdir = os.path.join(features_root, "fakefeat")
    os.makedirs(fdir)
    data = dict(BASE_FEATURE)
    if prompts_entry is not None:
        data["prompts"] = [prompts_entry]
    with open(os.path.join(fdir, "feature.json"), "w") as f:
        json.dump(data, f)
    return tmpdir


def run_cli(repo_root, *args):
    env = dict(os.environ)
    env["RABBIT_ROOT"] = repo_root
    return subprocess.run(
        ["python3", BUILD_PROMPT, *args],
        capture_output=True, text=True, env=env,
    )


# ---------- t-success ----------
with tempfile.TemporaryDirectory() as td:
    entry = {
        "id": "demo-prompt",
        "kind": "skill",
        "inject": [".claude/features/policy/philosophy.md"],
        "slots": ["task_description", "feature_name"],
    }
    make_tree(
        td,
        entry,
        template_body="TASK: {{task_description}} (feature={{feature_name}})\n",
    )
    r = run_cli(
        td,
        "--callable-id", "demo-prompt",
        "--slot", "task_description=Foo",
        "--slot", "feature_name=fakefeat",
    )
    if r.returncode != 0:
        fail(f"t-success: expected exit 0, got {r.returncode}; stderr={r.stderr}")
    else:
        out_path = r.stdout.strip()
        if not out_path or not os.path.isfile(out_path):
            fail(f"t-success: stdout must name an existing file, got {out_path!r}; stderr={r.stderr}")
        else:
            with open(out_path) as f:
                content = f.read()
            for token in (
                "RABBIT-POLICY-BLOCK-v1",
                "PHILOSOPHY-MARKER",
                "TASK: Foo (feature=fakefeat)",
            ):
                if token not in content:
                    fail(f"t-success: assembled prompt missing token {token!r}")
            if FAIL == 0:
                ok("t-success: assembled prompt contains sentinel, policy content, slot-substituted body")

# ---------- t-missing-slot ----------
with tempfile.TemporaryDirectory() as td:
    entry = {
        "id": "demo-prompt",
        "kind": "skill",
        "inject": [".claude/features/policy/philosophy.md"],
        "slots": ["task_description", "feature_name"],
    }
    make_tree(td, entry, template_body="TASK: {{task_description}} (feature={{feature_name}})\n")
    r = run_cli(
        td,
        "--callable-id", "demo-prompt",
        "--slot", "task_description=Foo",
        # missing feature_name
    )
    if r.returncode != 1:
        fail(f"t-missing-slot: expected exit 1, got {r.returncode}; stdout={r.stdout!r} stderr={r.stderr!r}")
    elif "missing" not in r.stderr.lower() and "slot" not in r.stderr.lower():
        fail(f"t-missing-slot: stderr must mention missing slot; got {r.stderr!r}")
    else:
        ok("t-missing-slot: exit 1 with diagnostic on stderr")

# ---------- t-unknown-id ----------
with tempfile.TemporaryDirectory() as td:
    entry = {
        "id": "demo-prompt",
        "kind": "skill",
        "inject": [".claude/features/policy/philosophy.md"],
        "slots": [],
    }
    make_tree(td, entry, template_body="no slots\n")
    r = run_cli(td, "--callable-id", "nonexistent")
    if r.returncode != 2:
        fail(f"t-unknown-id: expected exit 2, got {r.returncode}; stdout={r.stdout!r} stderr={r.stderr!r}")
    elif "id" not in r.stderr.lower() and "prompts" not in r.stderr.lower():
        fail(f"t-unknown-id: stderr must mention the missing id; got {r.stderr!r}")
    else:
        ok("t-unknown-id: exit 2 with diagnostic on stderr")

# ---------- t-value-with-placeholder-text ----------
with tempfile.TemporaryDirectory() as td:
    entry = {
        "id": "demo-prompt",
        "kind": "skill",
        "inject": [".claude/features/policy/philosophy.md"],
        "slots": ["args"],
    }
    make_tree(td, entry, template_body="TASK: {{args}}\n")
    r = run_cli(
        td,
        "--callable-id", "demo-prompt",
        "--slot", "args=See docs about {{args}} substitution",
    )
    if r.returncode != 0:
        fail(f"t-value-with-placeholder-text: expected exit 0, got {r.returncode}; "
             f"stdout={r.stdout!r} stderr={r.stderr!r}")
    else:
        out_path = r.stdout.strip()
        if not out_path or not os.path.isfile(out_path):
            fail(f"t-value-with-placeholder-text: stdout must name an existing file, "
                 f"got {out_path!r}; stderr={r.stderr}")
        else:
            with open(out_path) as f:
                content = f.read()
            if "TASK: See docs about {{args}} substitution" not in content:
                fail("t-value-with-placeholder-text: assembled prompt missing "
                     "verbatim substituted value")
            else:
                ok("t-value-with-placeholder-text: declared slot name in value not flagged as orphan")

# ---------- t-true-orphan ----------
with tempfile.TemporaryDirectory() as td:
    entry = {
        "id": "demo-prompt",
        "kind": "skill",
        "inject": [".claude/features/policy/philosophy.md"],
        "slots": ["args"],
    }
    make_tree(td, entry, template_body="TASK: {{args}} and {{unknown_slot}}\n")
    r = run_cli(
        td,
        "--callable-id", "demo-prompt",
        "--slot", "args=Foo",
    )
    if r.returncode != 1:
        fail(f"t-true-orphan: expected exit 1, got {r.returncode}; "
             f"stdout={r.stdout!r} stderr={r.stderr!r}")
    elif "unknown_slot" not in r.stderr:
        fail(f"t-true-orphan: stderr must name 'unknown_slot'; got {r.stderr!r}")
    else:
        ok("t-true-orphan: exit 1 with stderr naming the undeclared placeholder")

# ---------- t-value-with-undeclared-placeholder-text ----------
with tempfile.TemporaryDirectory() as td:
    entry = {
        "id": "demo-prompt",
        "kind": "skill",
        "inject": [".claude/features/policy/philosophy.md"],
        "slots": ["args"],
    }
    make_tree(td, entry, template_body="TASK: {{args}}\n")
    r = run_cli(
        td,
        "--callable-id", "demo-prompt",
        "--slot", "args=See docs about {{placeholder}} syntax",
    )
    if r.returncode != 0:
        fail(f"t-value-with-undeclared-placeholder-text: expected exit 0, got {r.returncode}; "
             f"stdout={r.stdout!r} stderr={r.stderr!r}")
    else:
        out_path = r.stdout.strip()
        if not out_path or not os.path.isfile(out_path):
            fail(f"t-value-with-undeclared-placeholder-text: stdout must name an existing file, "
                 f"got {out_path!r}; stderr={r.stderr}")
        else:
            with open(out_path) as f:
                content = f.read()
            if "TASK: See docs about {{placeholder}} syntax" not in content:
                fail("t-value-with-undeclared-placeholder-text: assembled prompt missing "
                     "verbatim substituted value")
            else:
                ok("t-value-with-undeclared-placeholder-text: undeclared name in slot value not flagged as orphan")

# ---------- t-mixed-declared-and-undeclared ----------
with tempfile.TemporaryDirectory() as td:
    entry = {
        "id": "demo-prompt",
        "kind": "skill",
        "inject": [".claude/features/policy/philosophy.md"],
        "slots": ["args"],
    }
    make_tree(td, entry, template_body="TASK: {{args}} {{also_unknown}}\n")
    r = run_cli(
        td,
        "--callable-id", "demo-prompt",
        "--slot", "args=value containing {{args}} literal",
    )
    if r.returncode != 1:
        fail(f"t-mixed-declared-and-undeclared: expected exit 1, got {r.returncode}; "
             f"stdout={r.stdout!r} stderr={r.stderr!r}")
    elif "also_unknown" not in r.stderr:
        fail(f"t-mixed-declared-and-undeclared: stderr must name 'also_unknown'; "
             f"got {r.stderr!r}")
    elif "'args'" in r.stderr or '"args"' in r.stderr:
        fail(f"t-mixed-declared-and-undeclared: stderr must NOT name declared "
             f"'args' as orphan; got {r.stderr!r}")
    else:
        ok("t-mixed-declared-and-undeclared: exit 1 naming only the undeclared placeholder")

# ---------- t-standalone-out-dir ----------
# repo_root basename is NOT `.rabbit`: the prompt must land under
# <repo_root>/.rabbit/prompts/ (a single appended `.rabbit` segment).
with tempfile.TemporaryDirectory() as td:
    entry = {
        "id": "demo-prompt",
        "kind": "skill",
        "inject": [".claude/features/policy/philosophy.md"],
        "slots": ["args"],
    }
    make_tree(td, entry, template_body="TASK: {{args}}\n")
    r = run_cli(td, "--callable-id", "demo-prompt", "--slot", "args=Foo")
    if r.returncode != 0:
        fail(f"t-standalone-out-dir: expected exit 0, got {r.returncode}; "
             f"stdout={r.stdout!r} stderr={r.stderr!r}")
    else:
        out_path = os.path.normpath(r.stdout.strip())
        expected_dir = os.path.normpath(os.path.join(td, ".rabbit", "prompts"))
        if os.path.normpath(os.path.dirname(out_path)) != expected_dir:
            fail(f"t-standalone-out-dir: prompt must land under {expected_dir!r}, "
                 f"got {os.path.dirname(out_path)!r}")
        else:
            ok("t-standalone-out-dir: prompt under <repo_root>/.rabbit/prompts/")

# ---------- t-vendored-out-dir-no-doubling ----------
# repo_root basename IS `.rabbit` (vendored install): the prompt must land
# under a SINGLE `.rabbit` segment <repo_root>/prompts/, NEVER the doubled
# <repo_root>/.rabbit/prompts/.
with tempfile.TemporaryDirectory() as td:
    rabbit_root = os.path.join(td, ".rabbit")
    entry = {
        "id": "demo-prompt",
        "kind": "skill",
        "inject": [".claude/features/policy/philosophy.md"],
        "slots": ["args"],
    }
    make_tree(rabbit_root, entry, template_body="TASK: {{args}}\n")
    r = run_cli(rabbit_root, "--callable-id", "demo-prompt", "--slot", "args=Foo")
    if r.returncode != 0:
        fail(f"t-vendored-out-dir-no-doubling: expected exit 0, got {r.returncode}; "
             f"stdout={r.stdout!r} stderr={r.stderr!r}")
    else:
        out_path = os.path.normpath(r.stdout.strip())
        expected_dir = os.path.normpath(os.path.join(rabbit_root, "prompts"))
        doubled_dir = os.path.normpath(os.path.join(rabbit_root, ".rabbit", "prompts"))
        actual_dir = os.path.normpath(os.path.dirname(out_path))
        if actual_dir == doubled_dir:
            fail(f"t-vendored-out-dir-no-doubling: prompt doubled to {doubled_dir!r} "
                 f"(the #1073 bug)")
        elif actual_dir != expected_dir:
            fail(f"t-vendored-out-dir-no-doubling: prompt must land under {expected_dir!r}, "
                 f"got {actual_dir!r}")
        else:
            ok("t-vendored-out-dir-no-doubling: single `.rabbit` segment, no doubling")

if FAIL:
    print("test-build-prompt: FAIL", file=sys.stderr)
    sys.exit(1)
print("test-build-prompt: all checks passed.")
