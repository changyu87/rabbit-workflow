#!/usr/bin/env python3
"""E2E test for Invariant 31: scope-guard.py validates the policy-block
sentinel on every Agent tool call by delegating to
contract.lib.checks.validate_agent_prompt_sentinel.

Five cases (per Inv 31's enforcement section):
  (i)   Agent call with prompt containing sentinel -> hook exits 0, stdout '{}',
        call proceeds.
  (ii)  Agent call with prompt missing sentinel + no bypass marker -> hook
        emits the deny-shape JSON with the canonical violation message,
        exits non-zero.
  (iii) Agent call with bypass marker '.rabbit/agent-sentinel-bypass' present
        -> hook exits 0 even when sentinel is absent.
  (iv)  Non-Agent tool call (Edit) -> hook does NOT invoke the sentinel
        validator (regression guard: existing file-write enforcement
        unchanged for unrelated paths).
  (v)   Agent call with malformed tool_input (no 'prompt' key) -> hook emits
        the deny-shape (defensive).
"""
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = subprocess.run(
    ["git", "-C", SCRIPT_DIR, "rev-parse", "--show-toplevel"],
    capture_output=True, text=True, check=True,
).stdout.strip()
SCOPE_GUARD = os.path.join(
    REPO_ROOT, ".claude/features/rabbit-cage/hooks/scope-guard.py"
)

SENTINEL = "RABBIT-POLICY-BLOCK-v1"
CANONICAL_VIOLATION_SUBSTR = "Agent dispatch missing RABBIT-POLICY-BLOCK-v1 sentinel"

failures = 0
total = 0


def ok(msg):
    global total
    total += 1
    print(f"  PASS t{total}: {msg}")


def fail_t(msg):
    global total, failures
    total += 1
    failures += 1
    print(f"  FAIL t{total}: {msg}")


def run_scope_guard(payload):
    """Invoke scope-guard.py with a JSON tool payload via stdin.

    Returns (returncode, stdout_text, stderr_text).
    """
    result = subprocess.run(
        [sys.executable, SCOPE_GUARD],
        input=json.dumps(payload),
        capture_output=True, text=True,
    )
    return result.returncode, result.stdout, result.stderr


def _ensure_no_bypass_marker():
    """Ensure <repo_root>/.rabbit/agent-sentinel-bypass is absent. Returns a
    restore callable that re-creates the marker only if it existed at entry."""
    marker = Path(REPO_ROOT) / ".rabbit" / "agent-sentinel-bypass"
    had = marker.is_file()
    saved_content = ""
    if had:
        saved_content = marker.read_text()
        marker.unlink()

    def restore():
        if had:
            marker.parent.mkdir(parents=True, exist_ok=True)
            marker.write_text(saved_content)
    return restore


def _create_bypass_marker():
    """Create the bypass marker. Returns a callable that removes it iff this
    function created it."""
    marker = Path(REPO_ROOT) / ".rabbit" / "agent-sentinel-bypass"
    if marker.is_file():
        # pre-existing; leave alone, restore = no-op
        return lambda: None
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.write_text("")

    def restore():
        if marker.is_file():
            marker.unlink()
    return restore


print("test-scope-guard-agent-sentinel.py")
print()
print("=== Invariant 31: scope-guard Agent sentinel validation ===")

restore_no_bypass = _ensure_no_bypass_marker()
try:
    # ------------------------------------------------------------------
    # Case (i): Agent call with prompt containing sentinel -> allow.
    # ------------------------------------------------------------------
    payload_ok = {
        "tool_name": "Agent",
        "tool_input": {
            "prompt": f"{SENTINEL}\n... real prompt body ...",
            "subagent_type": "general-purpose",
        },
    }
    rc, stdout, stderr = run_scope_guard(payload_ok)
    if rc == 0:
        ok("(i) Agent with sentinel: exit 0 (ALLOW)")
    else:
        fail_t(
            f"(i) Agent with sentinel: expected exit 0, got {rc}; "
            f"stderr={stderr!r}"
        )

    # ------------------------------------------------------------------
    # Case (ii): Agent call with prompt missing sentinel + no bypass -> deny.
    # ------------------------------------------------------------------
    payload_missing = {
        "tool_name": "Agent",
        "tool_input": {
            "prompt": "this prompt has no policy block marker",
            "subagent_type": "general-purpose",
        },
    }
    rc, stdout, stderr = run_scope_guard(payload_missing)
    if rc != 0:
        ok("(ii) Agent without sentinel: non-zero exit (DENY)")
    else:
        fail_t(
            "(ii) Agent without sentinel: expected non-zero exit, got 0; "
            f"stdout={stdout!r} stderr={stderr!r}"
        )

    # The deny-shape JSON MUST appear on stdout (Claude Code PreToolUse
    # deny convention).
    parsed = None
    try:
        parsed = json.loads(stdout) if stdout.strip() else None
    except json.JSONDecodeError:
        parsed = None
    if (
        parsed is not None
        and isinstance(parsed.get("hookSpecificOutput"), dict)
        and parsed["hookSpecificOutput"].get("hookEventName") == "PreToolUse"
        and parsed["hookSpecificOutput"].get("permissionDecision") == "deny"
        and isinstance(
            parsed["hookSpecificOutput"].get("permissionDecisionReason"), str
        )
        and CANONICAL_VIOLATION_SUBSTR
        in parsed["hookSpecificOutput"]["permissionDecisionReason"]
    ):
        ok(
            "(ii) Agent without sentinel: stdout carries deny-shape JSON "
            "with canonical violation message"
        )
    else:
        fail_t(
            "(ii) Agent without sentinel: stdout does not carry the expected "
            f"deny-shape JSON; stdout={stdout!r}"
        )

    # ------------------------------------------------------------------
    # Case (v): Agent call with malformed tool_input (no 'prompt') -> deny.
    # Tested before (iii) to keep the bypass-marker handling isolated.
    # ------------------------------------------------------------------
    payload_malformed = {
        "tool_name": "Agent",
        "tool_input": {"subagent_type": "general-purpose"},
    }
    rc, stdout, stderr = run_scope_guard(payload_malformed)
    if rc != 0:
        ok("(v) Agent with no 'prompt' key: non-zero exit (defensive DENY)")
    else:
        fail_t(
            "(v) Agent with no 'prompt' key: expected non-zero exit, got 0; "
            f"stdout={stdout!r} stderr={stderr!r}"
        )

    parsed_v = None
    try:
        parsed_v = json.loads(stdout) if stdout.strip() else None
    except json.JSONDecodeError:
        parsed_v = None
    if (
        parsed_v is not None
        and isinstance(parsed_v.get("hookSpecificOutput"), dict)
        and parsed_v["hookSpecificOutput"].get("permissionDecision") == "deny"
    ):
        ok("(v) malformed Agent input: deny-shape JSON emitted")
    else:
        fail_t(
            "(v) malformed Agent input: missing deny-shape JSON; "
            f"stdout={stdout!r}"
        )

    # ------------------------------------------------------------------
    # Case (iv): non-Agent tool (Edit) -> sentinel validator is NOT invoked.
    # Use a target on the allowlist so scope-guard's pre-existing file-write
    # path returns ALLOW; the test confirms scope-guard does not crash or
    # mis-route through the sentinel branch.
    # ------------------------------------------------------------------
    allowed_target = os.path.join(REPO_ROOT, ".rabbit", "agent-sentinel-test-tmp")
    payload_nonagent = {
        "tool_name": "Edit",
        "tool_input": {"file_path": allowed_target, "old_string": "x", "new_string": "y"},
    }
    rc, stdout, stderr = run_scope_guard(payload_nonagent)
    if rc == 0 and CANONICAL_VIOLATION_SUBSTR not in stdout + stderr:
        ok(
            "(iv) non-Agent Edit on allowlisted .rabbit/ path: exit 0 and "
            "sentinel validator was NOT invoked"
        )
    else:
        fail_t(
            "(iv) non-Agent Edit on allowlisted .rabbit/ path: expected "
            f"exit 0 with no sentinel message; got rc={rc} "
            f"stdout={stdout!r} stderr={stderr!r}"
        )
finally:
    restore_no_bypass()

# ------------------------------------------------------------------
# Case (iii): Agent call with bypass marker present -> allow even with no
# sentinel. Done in its own try/finally so the marker is always cleaned up.
# ------------------------------------------------------------------
restore_bypass = _create_bypass_marker()
try:
    payload_bypass = {
        "tool_name": "Agent",
        "tool_input": {
            "prompt": "no sentinel here at all",
            "subagent_type": "general-purpose",
        },
    }
    rc, stdout, stderr = run_scope_guard(payload_bypass)
    if rc == 0:
        ok(
            "(iii) Agent without sentinel + bypass marker: exit 0 (ALLOW)"
        )
    else:
        fail_t(
            "(iii) Agent without sentinel + bypass marker: expected exit 0, "
            f"got {rc}; stdout={stdout!r} stderr={stderr!r}"
        )
finally:
    restore_bypass()

print()
print(f"Results: {total - failures} passed, {failures} failed")
if failures == 0:
    print("ALL TESTS PASSED")
    sys.exit(0)
else:
    print(f"{failures} TEST(S) FAILED")
    sys.exit(1)
