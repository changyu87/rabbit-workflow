#!/usr/bin/env python3
"""test-tick-skill.py — SKILL.md documents the 12-phase tick algorithm
naming every script and the disk-state path.

Per spec Inv 10: the SKILL.md `tick` subcommand documentation must
enumerate all 12 phases (0..11) and name every Phase C script plus the
disk-state path `.rabbit/auto-evolve-state.json`.

Per spec Inv 32 (issue #414): phase 11 (`schedule`) is now a no-op owned
by the system cron — SKILL.md must NOT mention `ScheduleWakeup` and MUST
document the cron-owned scheduling.
"""

import os
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

    # The 12 phase names from design doc §4.
    phase_names = [
        "stop-check",
        "restart-check",
        "fetch",
        "triage",
        "plan",
        "dispatch",
        "merge",
        "release",
        "cleanup",
        "catch-up",
        "persist",
        "schedule",
    ]
    for name in phase_names:
        if name not in text:
            print(f"FAIL: SKILL.md missing phase name: {name}", file=sys.stderr)
            sys.exit(1)

    # The Phase C scripts that must be named. As of v0.7.1 / Inv 18 the
    # canonical tick pipe references `triage-batch.py` as the bridge
    # between `fetch-queue.py` and `plan-batch.py`; SKILL.md tick prose
    # must reference it via its full feature-relative path (asserted via
    # the bare-prefix loop below).
    scripts = [
        "set-evolve-mode.py",
        "fetch-queue.py",
        "triage-issue.py",
        "triage-batch.py",
        "plan-batch.py",
        "safety-check.py",
        "merge-prs.py",
        "release-bump.py",
        "cleanup-branches.py",
        "classify-merge-restart.py",
        "update-state.py",
    ]
    for script in scripts:
        if script not in text:
            print(f"FAIL: SKILL.md missing script name: {script}", file=sys.stderr)
            sys.exit(1)

    # Inv 16 — every script reference must use the full feature-relative
    # prefix `.claude/features/rabbit-auto-evolve/scripts/`. Bare
    # `scripts/<name>.py` is forbidden because Claude resolves SKILL paths
    # relative to the deployed SKILL.md location
    # (`.claude/skills/rabbit-auto-evolve/`), which has no `scripts/` dir.
    import re as _re
    feature_prefix = ".claude/features/rabbit-auto-evolve/scripts/"
    for script in scripts:
        full_ref = feature_prefix + script
        if full_ref not in text:
            print(
                f"FAIL: Inv 16: SKILL.md missing feature-relative reference "
                f"to script: {full_ref}",
                file=sys.stderr,
            )
            sys.exit(1)
        bare_re = _re.compile(
            r"(?<!\.claude/features/rabbit-auto-evolve/)scripts/"
            + _re.escape(script)
        )
        if bare_re.search(text):
            print(
                f"FAIL: Inv 16: bare `scripts/{script}` found in SKILL.md; "
                f"every reference must use the full feature-relative prefix",
                file=sys.stderr,
            )
            sys.exit(1)

    if ".rabbit/auto-evolve-state.json" not in text:
        print("FAIL: SKILL.md missing disk-state path .rabbit/auto-evolve-state.json",
              file=sys.stderr)
        sys.exit(1)

    # Inv 32 (issue #414): scheduling is owned by the system cron — the
    # self-chained ScheduleWakeup call was removed entirely.
    if "ScheduleWakeup" in text:
        print("FAIL: SKILL.md still references ScheduleWakeup (Inv 32: removed)",
              file=sys.stderr)
        sys.exit(1)
    if "cron" not in text.lower():
        print("FAIL: SKILL.md missing cron-owned scheduling (Inv 32)",
              file=sys.stderr)
        sys.exit(1)

    # Inv 55 (issue #882 reopen): the in-session phase-6 reconcile.
    # The `in-progress` label must cover the FULL TDD subagent execution
    # window, so the dispatcher records all `dispatched` journal entries,
    # THEN runs reconcile-labels.py, THEN fires the Agent calls. Assert the
    # SKILL.md phase-6 (`dispatch`) section documents this ordering: the
    # record-all-dispatched step, a reconcile-labels.py invocation, and the
    # Agent dispatch — in that physical order in the text.
    reconcile_ref = (
        ".claude/features/rabbit-auto-evolve/scripts/reconcile-labels.py"
    )
    if reconcile_ref not in text:
        print(
            "FAIL: Inv 55: SKILL.md missing feature-relative reference to "
            f"{reconcile_ref}",
            file=sys.stderr,
        )
        sys.exit(1)

    lower = text.lower()
    # Scope the ordering assertion to the SKILL.md phase-6 (`dispatch`)
    # section ONLY: between the "Phase 6 (`dispatch`)" heading and the
    # "Post-dispatch segment" heading that follows it. The phase-6 reconcile
    # must live HERE (in-session, before the Agent calls) — the post-dispatch
    # reconcile (a different, later touchpoint) must NOT satisfy this check.
    p6_start = lower.find("phase 6 (`dispatch`)")
    if p6_start < 0:
        print("FAIL: Inv 55: SKILL.md has no 'Phase 6 (`dispatch`)' section",
              file=sys.stderr)
        sys.exit(1)
    p6_end = lower.find("post-dispatch segment", p6_start)
    if p6_end < 0:
        print("FAIL: Inv 55: SKILL.md phase-6 section has no following "
              "'Post-dispatch segment' boundary", file=sys.stderr)
        sys.exit(1)
    p6 = lower[p6_start:p6_end]

    # Within phase 6: record-dispatch.py (--status dispatched) -> a
    # reconcile-labels.py call -> the Agent dispatch, in ascending position.
    pos_record = p6.find("record-dispatch.py")
    pos_reconcile = p6.find("reconcile-labels.py", pos_record if pos_record >= 0 else 0)
    pos_agent = p6.find("agent call", pos_reconcile if pos_reconcile >= 0 else 0)
    if pos_record < 0:
        print("FAIL: Inv 55: SKILL.md phase-6 lacks a record-dispatch.py step",
              file=sys.stderr)
        sys.exit(1)
    if pos_reconcile < 0:
        print(
            "FAIL: Inv 55: SKILL.md phase-6 lacks a reconcile-labels.py call "
            "AFTER recording dispatched entries (covering the live TDD window)",
            file=sys.stderr,
        )
        sys.exit(1)
    if pos_agent < 0 or not (pos_record < pos_reconcile < pos_agent):
        print(
            "FAIL: Inv 55: SKILL.md phase-6 must document the ordering "
            "record-all-dispatched -> reconcile-labels.py -> Agent calls",
            file=sys.stderr,
        )
        sys.exit(1)

    # spec Inv 55 must enumerate the phase-6 in-session touchpoint.
    spec_path = os.path.join(
        REPO_ROOT,
        ".claude/features/rabbit-auto-evolve/docs/spec.md",
    )
    with open(spec_path) as f:
        spec = f.read().lower()
    if "phase-6 in-session add" not in spec:
        print(
            "FAIL: Inv 55: spec.md does not enumerate the phase-6 in-session "
            "reconcile touchpoint",
            file=sys.stderr,
        )
        sys.exit(1)

    print("PASS: test-tick-skill.py")


if __name__ == "__main__":
    main()
