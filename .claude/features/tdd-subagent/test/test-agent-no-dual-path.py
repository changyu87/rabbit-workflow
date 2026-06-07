#!/usr/bin/env python3
"""Inv 27 — agents/rabbit-tdd-subagent.md does not describe a dual-path
layout for the state-machine scripts (agent-local OR feature-local fork)."""
from _helpers import AGENT_PATH, report

passed = failed = 0


def ok(msg):
    global passed
    passed += 1
    print(f"  ok   {msg}")


def ko(msg):
    global failed
    failed += 1
    print(f"  FAIL {msg}")


with open(AGENT_PATH) as f:
    content = f.read()

# Inv 27: agent file says use the absolute path supplied by the prompt.
if "absolute path" in content and "the prompt provides" in content:
    ok("inv27: agent file instructs subagent to use prompt-supplied absolute path")
else:
    ko("inv27: agent file missing absolute-path-from-prompt instruction")

# Inv 27: agent file does NOT describe a fork (no 'OR' / 'either ... or' patterns
# between two state-machine script paths).
banned_phrases = [
    " OR ",                    # caps OR between two paths
    "agent-local OR",
    "either .claude/agents",
    "either of",
    "resolve a fork",          # explicit warning is OK, but ensure not instructing a fork
]
violations = [p for p in banned_phrases if p in content and p != "resolve a fork"]
# "do not resolve a fork yourself" is explicitly allowed — it's the anti-fork instruction.
if "do not\nresolve a fork yourself" in content or "do not resolve a fork yourself" in content:
    ok("inv27: agent file warns against resolving a fork")
else:
    ko("inv27: agent file missing 'do not resolve a fork' warning")
if not violations:
    ok("inv27: agent file does not describe a dual-path fork")
else:
    ko(f"inv27: agent file contains fork-describing phrases: {violations}")

report(passed, failed)
