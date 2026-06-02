#!/usr/bin/env python3
"""test-start-stop-skill.py — SKILL.md documents start / stop / status
subcommands with their preconditions and marker writes.

Per spec Inv 10:
- `start` verifies three preconditions, writes .rabbit-auto-evolve-running,
  runs one tick, calls ScheduleWakeup.
- `stop` writes .rabbit-auto-evolve-stop-requested; next tick observes it
  and does NOT call ScheduleWakeup.
- `status` is read-only.
"""

import os
import re
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__))))))
SKILL_PATH = os.path.join(
    REPO_ROOT,
    ".claude/features/rabbit-auto-evolve/skills/rabbit-auto-evolve/SKILL.md",
)


def main():
    if not os.path.isfile(SKILL_PATH):
        print(f"FAIL: SKILL.md does not exist at {SKILL_PATH}", file=sys.stderr)
        sys.exit(1)

    with open(SKILL_PATH) as f:
        text = f.read()

    # Three preconditions for start.
    required = [
        ".rabbit-auto-evolve-active",
        "human-approval",
        "bypass-permissions",
        # start writes the running marker
        ".rabbit-auto-evolve-running",
        # stop writes the stop marker
        ".rabbit-auto-evolve-stop-requested",
    ]
    for token in required:
        if token not in text:
            print(f"FAIL: SKILL.md missing token: {token}", file=sys.stderr)
            sys.exit(1)

    # status section is read-only.
    if "read-only" not in text:
        print("FAIL: SKILL.md missing 'read-only' descriptor for status",
              file=sys.stderr)
        sys.exit(1)

    # Inv 10: SKILL.md documents `on` and `off` subcommands (the activation
    # surface, replacing /rabbit-config auto-evolve per Inv 11).
    for heading in ("### `on`", "### `off`"):
        if heading not in text and heading.replace("`", "") not in text:
            print(f"FAIL: SKILL.md missing subcommand heading: {heading}",
                  file=sys.stderr)
            sys.exit(1)

    # Inv 17: start/stop subcommand text MUST invoke the wrapper scripts
    # via `python3 .claude/features/rabbit-auto-evolve/scripts/<name>.py`
    # — never a literal `touch .rabbit-auto-evolve-*` or
    # `echo ... > .rabbit-auto-evolve-*`. Scope-guard would deny those
    # writes (issue #367); routing through Python hides the path.
    required_invocations = [
        "python3 .claude/features/rabbit-auto-evolve/scripts/start-loop.py",
        "python3 .claude/features/rabbit-auto-evolve/scripts/stop-loop.py",
        # Inv 20: every tick exit path invokes end-tick.py.
        "python3 .claude/features/rabbit-auto-evolve/scripts/end-tick.py",
        # Inv 21: SKILL.md start section MUST invoke check-preconditions.py
        # rather than bare `ls .rabbit-auto-evolve-*` patterns.
        "python3 .claude/features/rabbit-auto-evolve/scripts/check-preconditions.py",
    ]
    for inv in required_invocations:
        if inv not in text:
            print(f"FAIL: Inv 17/20: SKILL.md missing script invocation: {inv}",
                  file=sys.stderr)
            sys.exit(1)

    # Inv 20: SKILL.md tick documentation must call out end-tick.py on
    # every exit path — not only the normal completion path. The prose
    # must mention each of the four named exit paths so a reader can see
    # the lifecycle invariant at a glance.
    inv20_required_phrases = [
        "normal completion",
        "phase 0 halt",
        "safety abort",
        "error abort",
    ]
    lowered = text.lower()
    for phrase in inv20_required_phrases:
        if phrase not in lowered:
            print(
                f"FAIL: Inv 20: SKILL.md tick documentation missing exit-path "
                f"phrase: {phrase!r} (end-tick.py must run on EVERY exit path)",
                file=sys.stderr,
            )
            sys.exit(1)

    forbidden_patterns = [
        r"touch\s+\.rabbit-auto-evolve-running",
        r"touch\s+\.rabbit-auto-evolve-stop-requested",
        r"touch\s+\.rabbit-auto-evolve-restart-needed",
        r"touch\s+\.rabbit-auto-evolve-aborted",
        r"echo\s+[^>\n]*>\s*\.rabbit-auto-evolve-running",
        r"echo\s+[^>\n]*>\s*\.rabbit-auto-evolve-stop-requested",
        r"echo\s+[^>\n]*>\s*\.rabbit-auto-evolve-restart-needed",
        r"echo\s+[^>\n]*>\s*\.rabbit-auto-evolve-aborted",
        # Inv 21: bare `ls` precondition checks emit ugly stderr noise on
        # fresh clones; SKILL.md must route through check-preconditions.py.
        r"ls\s+[^\n]*\.rabbit-auto-evolve-active",
        r"ls\s+[^\n]*\.rabbit-human-approval-bypass",
    ]
    for pat in forbidden_patterns:
        if re.search(pat, text):
            print(
                f"FAIL: Inv 17: SKILL.md contains forbidden marker-write "
                f"pattern matching /{pat}/ — route through "
                f".claude/features/rabbit-auto-evolve/scripts/<name>.py instead",
                file=sys.stderr,
            )
            sys.exit(1)

    print("PASS: test-start-stop-skill.py")


if __name__ == "__main__":
    main()
