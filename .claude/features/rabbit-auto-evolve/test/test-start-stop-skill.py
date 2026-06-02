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

    # Inv 10 (v0.7.7 — issue #386): the `start` subcommand MUST route on
    # the check-preconditions report shape. Specifically:
    #
    # - On fresh state (`active-marker` check `ok: false`) the skill MUST
    #   automatically invoke `/rabbit-auto-evolve on` rather than dumping
    #   the failing-checklist to the user. The SKILL.md `start` prose MUST
    #   describe this routing in actionable terms.
    # - When markers exist but `bypass-permissions` is still `ok: false`
    #   (user forgot to restart after `on`), the skill MUST surface a
    #   short branded reminder rather than re-running `on`.
    # - Only genuinely-unexpected `all_pass: false` shapes fall through to
    #   the failing-checks surface.
    #
    # Extract the `start` section first so the assertions target the
    # right scope (other sections may legitimately mention checks/all_pass).
    start_m = re.search(
        r"(?ms)^###\s+`?start`?\s*$(.+?)(?=^###\s|^##\s|\Z)", text)
    if not start_m:
        print("FAIL: Inv 10: SKILL.md missing `### start` subcommand section",
              file=sys.stderr)
        sys.exit(1)
    start_body = start_m.group(1)
    start_lower = start_body.lower()

    # The routing table must be present in actionable terms — look for the
    # routing keywords plus the three distinct branches.
    inv10_required_phrases = [
        # Fresh-state branch: must auto-invoke `on`, not show checklist.
        ("automatically invoke",
         "Inv 10: `start` section must describe auto-invocation of `on` on "
         "fresh state — search-phrase 'automatically invoke' not found"),
        ("/rabbit-auto-evolve on",
         "Inv 10: `start` section must name the auto-invoked command "
         "(`/rabbit-auto-evolve on`)"),
        # Active-marker check identifier must appear (so the routing is
        # tied to the report shape, not vibes).
        ("active-marker",
         "Inv 10: `start` section must reference the `active-marker` check "
         "id from check-preconditions.py to anchor the routing"),
        # Bypass-permissions reminder branch.
        ("bypass-permissions",
         "Inv 10: `start` section must reference the `bypass-permissions` "
         "check id to anchor the restart-reminder branch"),
        # The short branded reminder branch must mention restart.
        ("restart claude",
         "Inv 10: `start` section must instruct the user to restart Claude "
         "when markers exist but bypass-permissions has not loaded"),
    ]
    for needle, msg in inv10_required_phrases:
        if needle not in start_lower:
            print(f"FAIL: {msg}", file=sys.stderr)
            sys.exit(1)

    # The old checklist-dump prose must be gone. v0.7.6 said: "On
    # `all_pass: false`, surface each failing `checks[*].detail` string to
    # the user as actionable guidance and STOP" — that as the SOLE
    # all_pass=false branch is what #386 fixes. The phrase MAY survive in
    # the "any other shape" fallback branch, but it MUST NOT be the only
    # behavior described for all_pass=false.
    forbidden_start_substrings = [
        # The blanket "surface every failing check and STOP" instruction.
        "surface each failing",
    ]
    for needle in forbidden_start_substrings:
        if needle in start_body:
            print(
                f"FAIL: Inv 10: `start` section still contains the pre-#386 "
                f"blanket failing-checklist instruction (substring "
                f"{needle!r}). Replace with the routing table that "
                f"auto-invokes `on` on fresh state.",
                file=sys.stderr,
            )
            sys.exit(1)

    print("PASS: test-start-stop-skill.py")


if __name__ == "__main__":
    main()
