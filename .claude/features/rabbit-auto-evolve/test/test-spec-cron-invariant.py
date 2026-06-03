#!/usr/bin/env python3
"""test-spec-cron-invariant.py — rabbit-auto-evolve Inv 32 (issue #414).

End-to-end regression for the architectural switch from self-chained
`ScheduleWakeup` to an external system-cron trigger. It asserts:
  1. The spec carries the Inv 32 text (cron-owned scheduling; ScheduleWakeup
     and CronCreate NEVER used).
  2. NEITHER the source SKILL.md NOR the deployed SKILL.md contains any
     `ScheduleWakeup` or `CronCreate` reference.
  3. BOTH SKILL.md copies document the cron-owned scheduling and the headless
     tick (`tick-headless.py`).
"""

import re
import sys
from pathlib import Path

FEATURE_DIR = Path(__file__).resolve().parents[1]
SPEC_MD = FEATURE_DIR / "specs" / "spec.md"
if not SPEC_MD.is_file():
    SPEC_MD = FEATURE_DIR / "docs" / "spec" / "spec.md"

SOURCE_SKILL = FEATURE_DIR / "skills" / "rabbit-auto-evolve" / "SKILL.md"
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


# --- (1) Spec carries Inv 32 -------------------------------------------
spec = norm(SPEC_MD.read_text())
spec_low = spec.lower()

SPEC_REQUIRED = [
    "414",
    "system cron",
    "tick-headless.py",
    "install-cron.py",
    "uninstall-cron.py",
    "sole tick scheduler",
]
missing = [s for s in SPEC_REQUIRED if s.lower() not in spec_low]
if missing:
    fail(f"spec.md missing cron-invariant phrase(s): {missing!r}")
else:
    ok("spec.md carries the cron-owned-scheduling invariant (Inv 32)")

# The spec MUST explicitly forbid ScheduleWakeup AND CronCreate in the Inv 32
# context (the strings may appear elsewhere in the spec while describing the
# OLD removed behaviour, so we only require the NEVER statement to be present).
if "never used in rabbit-auto-evolve" in spec_low or (
    "schedulewakeup" in spec_low and "croncreate" in spec_low
    and "never" in spec_low
):
    ok("spec.md documents that ScheduleWakeup and CronCreate are NEVER used")
else:
    fail("spec.md does not document the ScheduleWakeup/CronCreate NEVER rule")


# --- (2)+(3) SKILL.md copies -------------------------------------------
def check_skill(path, label):
    if not path.is_file():
        fail(f"{label} SKILL.md not found at {path}")
        return
    body = path.read_text()
    flat = norm(body)
    flat_low = flat.lower()

    # No ScheduleWakeup anywhere.
    if "schedulewakeup" in flat_low:
        fail(f"{label}: SKILL.md still references ScheduleWakeup (must be removed)")
    else:
        ok(f"{label}: no ScheduleWakeup reference")

    # No CronCreate anywhere.
    if "croncreate" in flat_low:
        fail(f"{label}: SKILL.md still references CronCreate (must not be used)")
    else:
        ok(f"{label}: no CronCreate reference")

    # No stale /loop reference.
    if "/loop" in flat_low:
        fail(f"{label}: SKILL.md still references /loop")
    else:
        ok(f"{label}: no /loop reference")

    # Documents cron-owned scheduling.
    if "cron" in flat_low:
        ok(f"{label}: documents the system cron")
    else:
        fail(f"{label}: does not mention the system cron")

    # Documents the headless tick.
    if "tick-headless.py" in flat_low:
        ok(f"{label}: documents the headless tick (tick-headless.py)")
    else:
        fail(f"{label}: does not document tick-headless.py")


check_skill(SOURCE_SKILL, "source")
check_skill(DEPLOYED_SKILL, "deployed")

sys.exit(FAIL)
