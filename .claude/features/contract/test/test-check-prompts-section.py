#!/usr/bin/env python3
"""test-check-prompts-section.py — exercises contract.lib.checks.check_prompts_section.

Spec Inv 53: cross-feature lint validating each feature's prompts section
against prompts.schema.json, plus globally-unique ids, inject-path existence,
universal-policy inclusion (philosophy.md), template existence at
.claude/features/contract/templates/prompts/<id>.txt, and bidirectional
slot/placeholder correspondence.

Tests construct a fake features tree in a tempdir and exercise the
function directly. They do NOT mutate the real repo tree.
"""

import os
import sys
import json
import tempfile

sys.path.insert(0, os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")))
from lib.checks import check_prompts_section  # noqa: E402

FAIL = 0


def fail(msg):
    global FAIL
    print(f"FAIL: {msg}", file=sys.stderr)
    FAIL = 1


def ok(msg):
    print(f"PASS: {msg}")


BASE = {
    "name": "x", "version": "1.0.0", "owner": "x", "tdd_state": "spec",
    "summary": "x", "surface": {}, "deprecation_criterion": "x",
}


def make_features_tree(tmpdir, features_specs, *, philosophy=True,
                       inject_paths_to_create=None, templates_to_create=None):
    """Build a fake .claude/features/ tree under tmpdir.

    features_specs: dict mapping feature_name -> prompts section value (list)
                    or None to omit the prompts key.
    inject_paths_to_create: list of repo-rel paths to actually create as empty files.
    templates_to_create: dict mapping prompt-id -> template body text.
    Returns: features_root path (tmpdir/.claude/features).
    """
    features_root = os.path.join(tmpdir, ".claude", "features")
    os.makedirs(features_root)
    # universal-policy file
    policy_dir = os.path.join(features_root, "policy")
    os.makedirs(policy_dir)
    if philosophy:
        with open(os.path.join(policy_dir, "philosophy.md"), "w") as f:
            f.write("# philosophy\n")
    # templates/prompts/<id>.txt
    if templates_to_create:
        prompts_tpl_dir = os.path.join(features_root, "contract", "templates", "prompts")
        os.makedirs(prompts_tpl_dir, exist_ok=True)
        for pid, body in templates_to_create.items():
            with open(os.path.join(prompts_tpl_dir, f"{pid}.txt"), "w") as f:
                f.write(body)
    # extra inject-path files
    if inject_paths_to_create:
        for rel in inject_paths_to_create:
            full = os.path.join(tmpdir, rel)
            os.makedirs(os.path.dirname(full), exist_ok=True)
            if not os.path.exists(full):
                with open(full, "w") as f:
                    f.write("# stub\n")
    # write each feature's feature.json
    for fname, prompts in features_specs.items():
        fdir = os.path.join(features_root, fname)
        os.makedirs(fdir, exist_ok=True)
        data = dict(BASE)
        data["name"] = fname
        if prompts is not None:
            data["prompts"] = prompts
        with open(os.path.join(fdir, "feature.json"), "w") as f:
            json.dump(data, f)
    return features_root


# ---------------------------------------------------------------------------
# t-valid: one feature, one entry, philosophy in inject, template matches slots
# ---------------------------------------------------------------------------
with tempfile.TemporaryDirectory() as td:
    entry = {
        "id": "my-prompt",
        "kind": "skill",
        "inject": [".claude/features/policy/philosophy.md"],
        "slots": ["foo", "bar"],
    }
    make_features_tree(
        td,
        {"feat-a": [entry]},
        templates_to_create={"my-prompt": "hello {{foo}} and {{bar}}\n"},
    )
    features_root = os.path.join(td, ".claude", "features")
    r = check_prompts_section(features_root)
    if r.passed:
        ok("t-valid: well-formed entry passes")
    else:
        fail(f"t-valid: should pass, got messages={r.messages}")


# ---------------------------------------------------------------------------
# t-no-prompts-section: feature has no prompts key -> vacuous pass
# ---------------------------------------------------------------------------
with tempfile.TemporaryDirectory() as td:
    make_features_tree(td, {"feat-a": None})
    features_root = os.path.join(td, ".claude", "features")
    r = check_prompts_section(features_root)
    if r.passed:
        ok("t-no-prompts-section: feature without prompts section passes vacuously")
    else:
        fail(f"t-no-prompts-section: should pass, got messages={r.messages}")


# ---------------------------------------------------------------------------
# t-missing-philosophy: inject lacks philosophy.md -> fail
# ---------------------------------------------------------------------------
with tempfile.TemporaryDirectory() as td:
    entry = {
        "id": "my-prompt",
        "kind": "skill",
        "inject": [".claude/features/feat-a/SOMETHING.md"],
        "slots": [],
    }
    make_features_tree(
        td,
        {"feat-a": [entry]},
        inject_paths_to_create=[".claude/features/feat-a/SOMETHING.md"],
        templates_to_create={"my-prompt": "no slots\n"},
    )
    features_root = os.path.join(td, ".claude", "features")
    r = check_prompts_section(features_root)
    if not r.passed and any("philosophy" in m for m in r.messages):
        ok("t-missing-philosophy: inject without philosophy.md is rejected")
    else:
        fail(f"t-missing-philosophy: expected failure citing philosophy, got passed={r.passed}, messages={r.messages}")


# ---------------------------------------------------------------------------
# t-duplicate-id: two features both declare id 'shared-id' -> fail
# ---------------------------------------------------------------------------
with tempfile.TemporaryDirectory() as td:
    entry = {
        "id": "shared-id",
        "kind": "skill",
        "inject": [".claude/features/policy/philosophy.md"],
        "slots": [],
    }
    make_features_tree(
        td,
        {"feat-a": [dict(entry)], "feat-b": [dict(entry)]},
        templates_to_create={"shared-id": "no slots\n"},
    )
    features_root = os.path.join(td, ".claude", "features")
    r = check_prompts_section(features_root)
    if not r.passed and any("shared-id" in m and ("duplicate" in m.lower() or "unique" in m.lower()) for m in r.messages):
        ok("t-duplicate-id: duplicate ids across features are rejected")
    else:
        fail(f"t-duplicate-id: expected duplicate-id failure, got passed={r.passed}, messages={r.messages}")


# ---------------------------------------------------------------------------
# t-missing-template: entry references id 'x' but no templates/prompts/x.txt
# ---------------------------------------------------------------------------
with tempfile.TemporaryDirectory() as td:
    entry = {
        "id": "no-template",
        "kind": "skill",
        "inject": [".claude/features/policy/philosophy.md"],
        "slots": [],
    }
    make_features_tree(td, {"feat-a": [entry]})  # no templates_to_create
    features_root = os.path.join(td, ".claude", "features")
    r = check_prompts_section(features_root)
    if not r.passed and any("template" in m.lower() and "no-template" in m for m in r.messages):
        ok("t-missing-template: missing convention-resolved template is rejected")
    else:
        fail(f"t-missing-template: expected missing-template failure, got passed={r.passed}, messages={r.messages}")


# ---------------------------------------------------------------------------
# t-orphan-placeholder: template has {{extra}} not in slots -> fail
# ---------------------------------------------------------------------------
with tempfile.TemporaryDirectory() as td:
    entry = {
        "id": "orphan-ph",
        "kind": "skill",
        "inject": [".claude/features/policy/philosophy.md"],
        "slots": ["foo"],
    }
    make_features_tree(
        td,
        {"feat-a": [entry]},
        templates_to_create={"orphan-ph": "hello {{foo}} and {{extra}}\n"},
    )
    features_root = os.path.join(td, ".claude", "features")
    r = check_prompts_section(features_root)
    if not r.passed and any("extra" in m for m in r.messages):
        ok("t-orphan-placeholder: template placeholder not in slots is rejected")
    else:
        fail(f"t-orphan-placeholder: expected orphan-placeholder failure, got passed={r.passed}, messages={r.messages}")


# ---------------------------------------------------------------------------
# t-orphan-slot: slots includes 'unused' not in template -> fail
# ---------------------------------------------------------------------------
with tempfile.TemporaryDirectory() as td:
    entry = {
        "id": "orphan-slot",
        "kind": "skill",
        "inject": [".claude/features/policy/philosophy.md"],
        "slots": ["foo", "unused"],
    }
    make_features_tree(
        td,
        {"feat-a": [entry]},
        templates_to_create={"orphan-slot": "hello {{foo}}\n"},
    )
    features_root = os.path.join(td, ".claude", "features")
    r = check_prompts_section(features_root)
    if not r.passed and any("unused" in m for m in r.messages):
        ok("t-orphan-slot: slot not in template is rejected")
    else:
        fail(f"t-orphan-slot: expected orphan-slot failure, got passed={r.passed}, messages={r.messages}")


# ---------------------------------------------------------------------------
# t-missing-inject-path: inject lists a path that doesn't exist -> fail
# ---------------------------------------------------------------------------
with tempfile.TemporaryDirectory() as td:
    entry = {
        "id": "no-inject-file",
        "kind": "skill",
        "inject": [
            ".claude/features/policy/philosophy.md",
            ".claude/features/nope/missing.md",
        ],
        "slots": [],
    }
    make_features_tree(
        td,
        {"feat-a": [entry]},
        templates_to_create={"no-inject-file": "no slots\n"},
    )
    features_root = os.path.join(td, ".claude", "features")
    r = check_prompts_section(features_root)
    if not r.passed and any("missing.md" in m for m in r.messages):
        ok("t-missing-inject-path: non-existent inject path is rejected")
    else:
        fail(f"t-missing-inject-path: expected missing-inject-path failure, got passed={r.passed}, messages={r.messages}")


# ---------------------------------------------------------------------------
# t-schema-violation: kind not in [skill, subagent] -> fail
# ---------------------------------------------------------------------------
with tempfile.TemporaryDirectory() as td:
    entry = {
        "id": "bad-kind",
        "kind": "wizard",
        "inject": [".claude/features/policy/philosophy.md"],
        "slots": [],
    }
    make_features_tree(
        td,
        {"feat-a": [entry]},
        templates_to_create={"bad-kind": "no slots\n"},
    )
    features_root = os.path.join(td, ".claude", "features")
    r = check_prompts_section(features_root)
    if not r.passed and any("kind" in m for m in r.messages):
        ok("t-schema-violation: invalid kind enum is rejected")
    else:
        fail(f"t-schema-violation: expected kind enum failure, got passed={r.passed}, messages={r.messages}")


if FAIL:
    print("test-check-prompts-section: FAIL", file=sys.stderr)
    sys.exit(1)
print("test-check-prompts-section: all checks passed.")
