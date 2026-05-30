#!/usr/bin/env python3
"""Inv 17-23, 25: rabbit-feature-scope scripts.

Covers resolve-scope.py + format-feature-context.py behavioural invariants.

Version: 1.0.0
Owner: rabbit-workflow team
Deprecation criterion: when scope resolution is automated by the dispatch
infrastructure.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
RESOLVE_SCOPE = SCRIPTS_DIR / "resolve-scope.py"
FORMAT_CTX = SCRIPTS_DIR / "format-feature-context.py"

REPO_ROOT = Path(__file__).resolve().parents[4]


# Inv 17: resolve-scope.py emits prompt only (never calls Agent itself)
def test_inv17_resolve_scope_does_not_invoke_agent() -> None:
    text = RESOLVE_SCOPE.read_text()
    # Direct Agent tool invocation patterns (Python or shell) MUST NOT appear.
    assert "Agent(" not in text, (
        "resolve-scope.py must not invoke Agent() directly; it must only emit "
        "a prompt for the caller to dispatch"
    )


# Inv 18: default model — no Opus override in the script or prompt content
def test_inv18_no_opus_override() -> None:
    text = RESOLVE_SCOPE.read_text()
    assert "opus" not in text.lower(), (
        "resolve-scope.py must not name 'opus' — the Agent uses the default model"
    )


# Inv 19: uses find-feature.py list-json
def test_inv19_uses_find_feature_list_json() -> None:
    text = RESOLVE_SCOPE.read_text()
    assert "find-feature.py" in text, (
        "resolve-scope.py must reference find-feature.py for feature enumeration"
    )
    assert "list-json" in text, (
        "resolve-scope.py must use the 'list-json' subcommand"
    )
    assert "registry.json" not in text, (
        "resolve-scope.py must NOT read registry.json; use find-feature.py list-json"
    )


# Inv 21: resolve-scope.py is executable and pure-shell
def test_inv21_executable_and_pure_shell() -> None:
    assert os.access(RESOLVE_SCOPE, os.X_OK), "resolve-scope.py must be executable"
    text = RESOLVE_SCOPE.read_text()
    # No inline `python3 -c` or python3 heredocs.
    assert not re.search(r"python3\s+-c", text), (
        "resolve-scope.py must not contain 'python3 -c' inline calls"
    )
    assert not re.search(r"python3\s*<<", text), (
        "resolve-scope.py must not contain python3 heredocs"
    )


# Inv 25: Agent prompt is feature-agnostic — no hardcoded feature names in RULES
def test_inv25_prompt_does_not_hardcode_feature_names() -> None:
    text = RESOLVE_SCOPE.read_text()
    # Extract the prompt body assigned to `prompt = f"""..."""`.
    m = re.search(r'prompt\s*=\s*f"""(.*?)"""', text, re.DOTALL)
    assert m, "resolve-scope.py must define the prompt as a triple-quoted f-string"
    prompt_body = m.group(1)
    # The RULES section (anything after the 'Rules:' anchor) must not hardcode
    # specific feature names. Catalog of feature names that historically appeared
    # as hardcoded examples:
    forbidden = ["contract", "rabbit-cage", "rabbit-feature", "tdd-subagent"]
    rules_pos = prompt_body.find("Rules:")
    assert rules_pos != -1, "prompt must contain a 'Rules:' anchor"
    rules_block = prompt_body[rules_pos:]
    leaked = [name for name in forbidden if name in rules_block]
    assert not leaked, (
        f"Agent prompt RULES section must not hardcode feature names; leaked: {leaked}"
    )


# Inv 22: format-feature-context.py stdin/stdout contract
def test_inv22_format_context_stdin_to_stdout() -> None:
    payload = json.dumps([
        {"name": "alpha", "summary": "a", "tdd_state": "test-green",
         "version": "1.0.0", "path": ".claude/features/alpha"},
    ]).encode()
    proc = subprocess.run(
        ["python3", str(FORMAT_CTX)], input=payload,
        capture_output=True,
    )
    assert proc.returncode == 0, (
        f"format-feature-context.py exited {proc.returncode}; stderr={proc.stderr!r}"
    )
    out = proc.stdout.decode()
    assert "Feature: alpha" in out, (
        f"format-feature-context.py must emit the feature name; got: {out!r}"
    )


# Inv 23: tolerates missing optional keys
def test_inv23_tolerates_missing_optional_keys() -> None:
    # Only 'name' is required; missing summary/tdd_state/version/path must not crash.
    payload = json.dumps([{"name": "minimal"}]).encode()
    proc = subprocess.run(
        ["python3", str(FORMAT_CTX)], input=payload, capture_output=True,
    )
    assert proc.returncode == 0, (
        f"format-feature-context.py must tolerate missing optional keys; "
        f"exited {proc.returncode}; stderr={proc.stderr!r}"
    )
    assert b"Feature: minimal" in proc.stdout, (
        f"output must include the feature name; got: {proc.stdout!r}"
    )


def test_inv23_missing_name_is_fatal() -> None:
    payload = json.dumps([{"summary": "no name"}]).encode()
    proc = subprocess.run(
        ["python3", str(FORMAT_CTX)], input=payload, capture_output=True,
    )
    assert proc.returncode != 0, (
        "format-feature-context.py must exit non-zero when 'name' is missing"
    )


# Inv 20: scope Agent response schema documented in resolve-scope.py prompt
def test_inv20_response_schema_in_prompt() -> None:
    text = RESOLVE_SCOPE.read_text()
    m = re.search(r'prompt\s*=\s*f"""(.*?)"""', text, re.DOTALL)
    assert m, "resolve-scope.py must define the prompt as a triple-quoted f-string"
    prompt_body = m.group(1)
    assert '"features"' in prompt_body, (
        "prompt must document the 'features' key in the response JSON"
    )
    assert '"rationale"' in prompt_body, (
        "prompt must document the 'rationale' key in the response JSON"
    )
    # Empty-list acceptance must be documented.
    assert "empty" in prompt_body.lower() or "[]" in prompt_body, (
        "prompt must document that an empty features list is a valid response"
    )


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    fail = 0
    for t in tests:
        try:
            t()
            print(f"PASS {t.__name__}")
        except AssertionError as e:
            print(f"FAIL {t.__name__}: {e}", file=sys.stderr)
            fail += 1
    sys.exit(0 if fail == 0 else 1)
