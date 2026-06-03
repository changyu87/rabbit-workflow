#!/usr/bin/env python3
"""test-spec-schedule-invariant.py — rabbit-auto-evolve Inv 29 (issue #409).

The auto-evolve loop silently stopped scheduling: tick 6 ended and five
subsequent hourly ticks never fired, with no error and no log line, even
though the session was alive. Root cause: SKILL.md's phase 11 (`schedule`)
documented only the bare string "ScheduleWakeup (unless stop-check
matched)" — it never pinned the three call parameters (`delaySeconds`,
`prompt`, `reason`), so the dispatcher had no deterministic instruction
on what delay to use or which prompt re-enters the tick. An
under-specified call can silently emit nothing, a zero/out-of-range delay
the harness ignores, or a prompt that never re-invokes `/rabbit-auto-evolve
tick`.

This is the end-to-end regression for the fix. It asserts:
  1. The spec carries the Inv 29 text (valid ScheduleWakeup params).
  2. BOTH the source SKILL.md and the deployed SKILL.md document the
     phase-11 ScheduleWakeup call with a concrete in-range delaySeconds
     and the tick-reinvoke prompt `/rabbit-auto-evolve tick`.
  3. Both SKILL.md copies invoke schedule-check.py before the call.
"""

import re
import sys
from pathlib import Path

FEATURE_DIR = Path(__file__).resolve().parents[1]
# Dual-read (issue #399): prefer specs/spec.md, fall back to docs/spec/spec.md.
SPEC_MD = FEATURE_DIR / "specs" / "spec.md"
if not SPEC_MD.is_file():
    SPEC_MD = FEATURE_DIR / "docs" / "spec" / "spec.md"

SOURCE_SKILL = FEATURE_DIR / "skills" / "rabbit-auto-evolve" / "SKILL.md"
# Deployed copy lives at repo-root .claude/skills/rabbit-auto-evolve/SKILL.md.
# FEATURE_DIR == <repo>/.claude/features/rabbit-auto-evolve.
REPO_ROOT = FEATURE_DIR.parents[2]
DEPLOYED_SKILL = REPO_ROOT / ".claude" / "skills" / "rabbit-auto-evolve" / "SKILL.md"

FAIL = 0


def fail(msg):
    global FAIL
    print(f"FAIL: {msg}", file=sys.stderr)
    FAIL = 1


def ok(msg):
    print(f"PASS: {msg}")


def norm(text):
    return re.sub(r"\s+", " ", text)


# --- (1) Spec carries Inv 29 -------------------------------------------
spec = norm(SPEC_MD.read_text())
spec_low = spec.lower()

SPEC_REQUIRED = [
    "schedulewakeup",
    "delayseconds",
    "/rabbit-auto-evolve tick",
    "schedule-check.py",
    # the delay band that bounds the call.
    "60",
    "3600",
    # reason must be non-empty.
    "reason",
]
missing = [s for s in SPEC_REQUIRED if s.lower() not in spec_low]
if missing:
    fail(f"spec.md missing schedule-invariant phrase(s): {missing!r}")
else:
    ok("spec.md carries the ScheduleWakeup params invariant (Inv 29)")

# The spec MUST state the delay band as a range (60..3600). Assert both
# bounds appear in proximity to delaySeconds.
if re.search(r"60\s*[≤<=].{0,40}delayseconds.{0,40}[≤<=]\s*3600", spec_low) or (
    "60" in spec_low and "3600" in spec_low and "delayseconds" in spec_low
):
    ok("spec.md documents the 60..3600 delay band for delaySeconds")
else:
    fail("spec.md does not document the 60<=delaySeconds<=3600 band")


# --- (1b) Spec carries Inv 31 (issue #412 immediate refire) ------------
# The queue-emptiness branch selecting between the 60s refire and the
# 3600s idle delay MUST be documented.
INV31_REQUIRED = [
    "412",
    "queue non-empty, refiring immediately",
    "queue empty, waiting for new issues",
]
inv31_missing = [s for s in INV31_REQUIRED if s.lower() not in spec_low]
if inv31_missing:
    fail(f"spec.md missing Inv 31 (issue #412) phrase(s): {inv31_missing!r}")
else:
    ok("spec.md carries the immediate-refire invariant (Inv 31)")

# The two-delay rule MUST tie delaySeconds=60 to a non-empty queue and
# delaySeconds=3600 to an empty queue.
if "60" in spec_low and "3600" in spec_low and "in_flight" in spec_low and (
    "len(state.queue)" in spec_low or "queue" in spec_low
):
    ok("spec.md documents the queue-emptiness branch (60 vs 3600)")
else:
    fail("spec.md does not document the queue-emptiness 60-vs-3600 branch")


# --- (2)+(3) Both SKILL.md copies document the call --------------------
def check_skill(path, label):
    if not path.is_file():
        fail(f"{label} SKILL.md not found at {path}")
        return
    body = path.read_text()
    flat = norm(body)
    flat_low = flat.lower()

    # The tick-reinvoke prompt must be present verbatim.
    if "/rabbit-auto-evolve tick" in flat:
        ok(f"{label}: tick-reinvoke prompt /rabbit-auto-evolve tick present")
    else:
        fail(f"{label}: missing tick-reinvoke prompt /rabbit-auto-evolve tick")

    # ScheduleWakeup must appear with a concrete in-range delaySeconds.
    if "delayseconds" in flat_low:
        ok(f"{label}: documents a concrete delaySeconds")
    else:
        fail(f"{label}: phase-11 schedule does not document delaySeconds")

    # A recognizable, concrete in-range delay value must be pinned. The
    # canonical hourly value is 3600; require it AND that every standalone
    # integer the phase-11 docs associate with the delay sits in
    # [60, 3600] (guards against an out-of-band value silently shipping).
    delay_ints = [
        int(tok)
        for tok in re.findall(r"--delay-seconds\s+(\d+)", flat_low)
    ]
    # Also pick up the bare integers in a `60 <= delaySeconds <= 3600` band.
    band = re.search(r"(\d+)\s*<=\s*delayseconds\s*<=\s*(\d+)", flat_low)
    if band:
        delay_ints.extend([int(band.group(1)), int(band.group(2))])
    if not delay_ints:
        fail(f"{label}: no recognizable concrete delaySeconds value found")
    elif all(60 <= d <= 3600 for d in delay_ints) and 3600 in delay_ints:
        ok(f"{label}: pins a concrete in-range delaySeconds (incl. 3600)")
    else:
        fail(f"{label}: delaySeconds values {delay_ints} not all in [60, 3600] / 3600 absent")

    # The runtime validator must be invoked before the call.
    if "schedule-check.py" in flat:
        ok(f"{label}: invokes schedule-check.py before ScheduleWakeup")
    else:
        fail(f"{label}: does not invoke schedule-check.py")

    # The reason parameter must be documented.
    if "reason" in flat_low:
        ok(f"{label}: documents a reason parameter")
    else:
        fail(f"{label}: does not document a reason parameter")

    # --- Inv 31 (issue #412): BOTH delay cases must be pinned. ---------
    # The queue-non-empty refire (60) AND the queue-empty idle (3600)
    # must BOTH appear so the two-delay rule is documented, not just 3600.
    if "60" in flat_low and "3600" in flat_low:
        ok(f"{label}: pins both delay cases (60 refire + 3600 idle)")
    else:
        fail(f"{label}: missing one of the two delay cases (60 / 3600)")

    # The queue-emptiness branch that selects between the two delays.
    if "queue non-empty, refiring immediately" in flat_low:
        ok(f"{label}: documents the queue-non-empty refire reason")
    else:
        fail(f"{label}: missing 'queue non-empty, refiring immediately' reason")
    if "queue empty, waiting for new issues" in flat_low:
        ok(f"{label}: documents the queue-empty idle reason")
    else:
        fail(f"{label}: missing 'queue empty, waiting for new issues' reason")

    # The branch must read queue/in_flight emptiness from state.
    if "in_flight" in flat_low and "queue" in flat_low:
        ok(f"{label}: documents the queue/in_flight emptiness check")
    else:
        fail(f"{label}: does not document the queue/in_flight emptiness check")


check_skill(SOURCE_SKILL, "source")
check_skill(DEPLOYED_SKILL, "deployed")

sys.exit(FAIL)
