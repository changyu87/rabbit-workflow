#!/usr/bin/env python3
"""rabbit-cage Inv 10a test — CLAUDE.md header content (BUG-88).

Verifies generate-claude-md.py emits the structured orientation block:
  - H1 "Rabbit Workflow"
  - Four trait bullets in order: Feature-oriented, Scope-protected,
    Drift-protected, Subagent-driven
  - Token-cost judgment bullet
  - Dispatcher-role paragraph forbidding direct edits to scope-protected
    files without explicit human approval
  - Three @-import lines follow (philosophy, spec-rules, coding-rules)
"""
import os
import subprocess
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = subprocess.run(
    ["git", "-C", SCRIPT_DIR, "rev-parse", "--show-toplevel"],
    capture_output=True, text=True, check=True,
).stdout.strip()
GENERATE_SCRIPT = os.path.join(
    REPO_ROOT, ".claude/features/rabbit-cage/scripts/generate-claude-md.py"
)

pass_n = 0
fail_n = 0


def ok(t, msg):
    global pass_n
    print(f"  PASS t{t}: {msg}")
    pass_n += 1


def fail_t(t, msg):
    global fail_n
    print(f"  FAIL t{t}: {msg}")
    fail_n += 1


print("test-claude-md-header.py")

result = subprocess.run(
    [sys.executable, GENERATE_SCRIPT], capture_output=True, text=True
)
output = result.stdout

# t1: output starts with H1 + first trait bullet opening
expected_opening = "# Rabbit Workflow\n\n- **Feature-oriented:**"
if output.startswith(expected_opening):
    ok(1, "output starts with H1 + Feature-oriented bullet opening")
else:
    fail_t(1, f"output does not start with expected opening; got first 80 chars: {output[:80]!r}")

# t2: trait bullets present in order
traits = ["Feature-oriented", "Scope-protected", "Drift-protected", "Subagent-driven"]
positions = [output.find(f"**{t}:**") for t in traits]
if all(p >= 0 for p in positions) and positions == sorted(positions):
    ok(2, "all four trait bold-headings present in order")
else:
    fail_t(2, f"trait bullets missing or out of order; positions={positions}")

# t3: token-cost judgment bullet
if "token-heavy" in output and "judgment" in output:
    ok(3, "token-cost judgment bullet present (contains 'token-heavy' and 'judgment')")
else:
    fail_t(3, "token-cost judgment bullet missing ('token-heavy' or 'judgment' not found)")

# t4: dispatcher-role paragraph
if "You are the dispatcher" in output and "scope-protected file without explicit human" in output:
    ok(4, "dispatcher-role paragraph present")
else:
    fail_t(4, "dispatcher-role paragraph missing")

# t5: three @-import lines follow header (philosophy, spec-rules, coding-rules in order)
phil_idx = output.find("@.claude/features/policy/philosophy.md")
spec_idx = output.find("@.claude/features/policy/spec-rules.md")
code_idx = output.find("@.claude/features/policy/coding-rules.md")
if phil_idx > 0 and spec_idx > phil_idx and code_idx > spec_idx:
    ok(5, "three @-import lines follow in order: philosophy, spec-rules, coding-rules")
else:
    fail_t(5, f"@-import lines missing or out of order; phil={phil_idx} spec={spec_idx} code={code_idx}")

# t7: dispatcher paragraph appears AFTER all trait bullets (structural order)
dispatcher_idx = output.find("You are the dispatcher")
last_trait_idx = max(positions) if all(p >= 0 for p in positions) else -1
if dispatcher_idx > last_trait_idx >= 0:
    ok(7, "dispatcher paragraph follows the trait bullet block")
else:
    fail_t(7, f"dispatcher paragraph not after trait block; dispatcher={dispatcher_idx} last_trait={last_trait_idx}")

print()
print(f"Results: {pass_n} passed, {fail_n} failed")
sys.exit(0 if fail_n == 0 else 1)
