#!/usr/bin/env python3
"""Tests for dispatch-tdd-subagent.py — new 9-step interface."""
import os
import subprocess
import sys
import tempfile
import json

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(SCRIPT_DIR, "..", "scripts", "dispatch-tdd-subagent.py")
REPO_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, "..", "..", "..", ".."))


def run(args, capture=True):
    return subprocess.run(
        [sys.executable, SCRIPT] + args,
        capture_output=capture, text=True
    )


def test_missing_scope_fails():
    r = run(["--spec", "/dev/null"])
    assert r.returncode == 2, f"Expected 2, got {r.returncode}"


def test_missing_spec_fails():
    r = run(["--scope", "tdd-subagent"])
    assert r.returncode == 2, f"Expected 2, got {r.returncode}"


def test_linked_item_without_type_fails():
    spec = os.path.join(REPO_ROOT, ".claude/features/tdd-subagent/docs/spec/spec.md")
    r = run(["--scope", "tdd-subagent", "--spec", spec, "--linked-item", "/tmp/fake"])
    assert r.returncode == 2, f"Expected 2, got {r.returncode}"


def test_item_type_without_linked_item_fails():
    spec = os.path.join(REPO_ROOT, ".claude/features/tdd-subagent/docs/spec/spec.md")
    r = run(["--scope", "tdd-subagent", "--spec", spec, "--item-type", "bug"])
    assert r.returncode == 2, f"Expected 2, got {r.returncode}"


def test_valid_invocation_emits_prompt():
    spec = os.path.join(REPO_ROOT, ".claude/features/tdd-subagent/docs/spec/spec.md")
    r = run(["--scope", "tdd-subagent", "--spec", spec])
    assert r.returncode == 0, f"Expected 0, got {r.returncode}\n{r.stderr}"
    assert len(r.stdout) > 100, "Prompt too short"


def test_prompt_contains_all_9_steps():
    spec = os.path.join(REPO_ROOT, ".claude/features/tdd-subagent/docs/spec/spec.md")
    r = run(["--scope", "tdd-subagent", "--spec", spec])
    assert r.returncode == 0
    prompt = r.stdout
    for step in ["SPEC-READ", "HUMAN-APPROVAL", "LOCK", "TEST-WRITE",
                 "TEST-RED", "IMPLEMENT", "CODE-REVIEW", "TEST-GREEN", "UNLOCK"]:
        assert step in prompt, f"Step {step} missing from prompt"


def test_no_human_approval_flag():
    spec = os.path.join(REPO_ROOT, ".claude/features/tdd-subagent/docs/spec/spec.md")
    r = run(["--scope", "tdd-subagent", "--spec", spec, "--no-human-approval"])
    assert r.returncode == 0
    assert "Skipped (--no-human-approval)" in r.stdout


def test_code_review_full_loop_flag():
    spec = os.path.join(REPO_ROOT, ".claude/features/tdd-subagent/docs/spec/spec.md")
    r = run(["--scope", "tdd-subagent", "--spec", spec, "--code-review-full-loop"])
    assert r.returncode == 0
    assert "--code-review-full-loop" in r.stdout or "full loop" in r.stdout.lower()


def test_max_iterations_default_3():
    spec = os.path.join(REPO_ROOT, ".claude/features/tdd-subagent/docs/spec/spec.md")
    r = run(["--scope", "tdd-subagent", "--spec", spec])
    assert r.returncode == 0
    assert "Max iterations: 3" in r.stdout


def test_max_iterations_override():
    spec = os.path.join(REPO_ROOT, ".claude/features/tdd-subagent/docs/spec/spec.md")
    r = run(["--scope", "tdd-subagent", "--spec", spec, "--max-iterations", "7"])
    assert r.returncode == 0
    assert "Max iterations: 7" in r.stdout


def test_prompt_contains_e2e_rule():
    spec = os.path.join(REPO_ROOT, ".claude/features/tdd-subagent/docs/spec/spec.md")
    r = run(["--scope", "tdd-subagent", "--spec", spec])
    assert r.returncode == 0
    assert "end-to-end test" in r.stdout.lower() or "e2e" in r.stdout.lower()


def test_impl_suggestion_included_when_provided():
    spec = os.path.join(REPO_ROOT, ".claude/features/tdd-subagent/docs/spec/spec.md")
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump({"schema_version": "1.0.0", "feature": "tdd-subagent",
                   "implementation_approach": "test approach"}, f)
        impl_path = f.name
    try:
        r = run(["--scope", "tdd-subagent", "--spec", spec, "--impl-suggestion", impl_path])
        assert r.returncode == 0
        assert "Implementation Suggestion" in r.stdout
    finally:
        os.unlink(impl_path)


def test_max_iterations_zero_fails():
    spec = os.path.join(REPO_ROOT, ".claude/features/tdd-subagent/docs/spec/spec.md")
    r = run(["--scope", "tdd-subagent", "--spec", spec, "--max-iterations", "0"])
    assert r.returncode == 2, f"Expected 2, got {r.returncode}"


def test_tdd_report_path_uses_feature_name():
    spec = os.path.join(REPO_ROOT, ".claude/features/tdd-subagent/docs/spec/spec.md")
    r = run(["--scope", "tdd-subagent", "--spec", spec])
    assert r.returncode == 0
    assert "tdd-report-tdd-subagent.json" in r.stdout


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    fail = 0
    for t in tests:
        try:
            t()
            print(f"PASS: {t.__name__}")
        except Exception as e:
            print(f"FAIL: {t.__name__}: {e}")
            fail += 1
    print()
    print("ALL PASS" if fail == 0 else f"FAILED: {fail}")
    sys.exit(0 if fail == 0 else 1)
