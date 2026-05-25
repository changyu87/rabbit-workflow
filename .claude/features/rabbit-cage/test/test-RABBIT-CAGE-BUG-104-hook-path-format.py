#!/usr/bin/env python3
"""rabbit-cage Inv 15 regression — every hook command registered in
.claude/settings.json MUST be CWD-independent (begin with
'$(git rev-parse --show-toplevel)/').

A bare relative path such as '.claude/hooks/scope-guard.py' is forbidden
because Claude Code's Bash tool persists CWD between calls; after any
`cd` into a subdirectory the relative path resolves outside the repo and
the hook silently fails (non-blocking 'No such file or directory').

Regression guard for RABBIT-CAGE-BUG-104.
"""
import json
import os
import subprocess
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = subprocess.run(
    ["git", "-C", SCRIPT_DIR, "rev-parse", "--show-toplevel"],
    capture_output=True, text=True, check=True,
).stdout.strip()
SETTINGS_PATH = os.path.join(REPO_ROOT, ".claude", "settings.json")
REQUIRED_PREFIX = "$(git rev-parse --show-toplevel)/"

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


print("test-RABBIT-CAGE-BUG-104-hook-path-format.py")

# t1: settings.json exists and is valid JSON
try:
    with open(SETTINGS_PATH) as f:
        data = json.load(f)
    ok(1, ".claude/settings.json exists and is valid JSON")
except Exception as e:
    fail_t(1, f".claude/settings.json missing or invalid JSON: {e}")
    print()
    print(f"Results: {pass_n} passed, {fail_n} failed")
    sys.exit(1)

# t2: hooks section is present (rabbit-cage registers four events)
hooks_section = data.get("hooks", {})
if isinstance(hooks_section, dict) and hooks_section:
    ok(2, "hooks section is present and non-empty")
else:
    fail_t(2, "hooks section missing or empty in .claude/settings.json")

# t3: every command across every event begins with the required prefix
violations = []
total_commands = 0
for event, entries in hooks_section.items():
    if not isinstance(entries, list):
        continue
    for entry in entries:
        for h in entry.get("hooks", []):
            cmd = h.get("command", "")
            total_commands += 1
            if not cmd.startswith(REQUIRED_PREFIX):
                violations.append(f"{event}: {cmd!r}")

if total_commands == 0:
    fail_t(3, "no hook commands found under any event — expected at least one")
elif violations:
    fail_t(3, f"{len(violations)} hook command(s) not CWD-independent: "
              + "; ".join(violations))
else:
    ok(3, f"all {total_commands} hook command(s) begin with "
          f"'$(git rev-parse --show-toplevel)/'")

# t4: all four rabbit-cage-owned events are registered
expected_events = {"PreToolUse", "Stop", "SessionStart", "UserPromptSubmit"}
missing = expected_events - set(hooks_section.keys())
if not missing:
    ok(4, "all four rabbit-cage events registered (PreToolUse, Stop, "
          "SessionStart, UserPromptSubmit)")
else:
    fail_t(4, f"events missing from settings.json hooks: {sorted(missing)}")

print()
print(f"Results: {pass_n} passed, {fail_n} failed")
sys.exit(0 if fail_n == 0 else 1)
