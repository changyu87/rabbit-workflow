#!/usr/bin/env python3
# E2E test for TDD-SUBAGENT-BACKLOG-9.
#
# BACKLOG-9: agents/tdd-subagent.md does NOT instruct the subagent to choose
#            between an agent-local and feature-local scripts path.
import os
import sys

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
AGENT_MD = os.path.join(
    REPO_ROOT, ".claude", "features", "tdd-subagent", "agents", "tdd-subagent.md"
)

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


b9()

print()
if FAIL == 0:
    print(f"backlog-9: {PASS} passed.")
    sys.exit(0)
print(f"backlog-9: {FAIL} failure(s), {PASS} passed.")
sys.exit(1)
