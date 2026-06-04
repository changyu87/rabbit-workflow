#!/usr/bin/env python3
"""test-changelog-continuity.py — issue #517 (rabbit-auto-evolve CHANGELOG traceability)

End-to-end check that docs/CHANGELOG.md has no missing-version traceability
gap. The feature version (feature.json / docs/spec.md / docs/contract.md /
SKILL.md, lockstep) advances one release at a time, so every version that was
ever cut MUST have a corresponding entry in the changelog — a jump from 0.20.0
straight to 0.22.0 (the #517 gap, where the 0.21.0 bump from #507 shipped with
no changelog entry) is a traceability hole.

This test reads the version headers from the changelog ENTRY bullets (the
`- **vX.Y.Z — ...` form) — NOT arbitrary `vN.N.N` strings in entry prose, which
include unrelated per-script version references (e.g. `install-cron.py 1.0.0 →
1.1.0`). It then asserts that the run of consecutive minor-version entries that
SPANS 0.21.0 is contiguous: specifically that the documented 0.20.0 → 0.22.0
release stream has its 0.21.0 entry (the #517 gap). It does not police the
whole history for holes — early history may legitimately begin partway and some
releases bundle several issues — it pins exactly the #517 traceability hole.

  t1  docs/CHANGELOG.md exists and is non-empty.
  t2  at least two entry-bullet version headers are present (sequence is
      meaningful).
  t3  the specific #517 gap is closed: a 0.21.0 entry bullet exists when both
      the 0.20.0 and 0.22.0 entry bullets are present.
  t4  the 0.20.0 → 0.22.0 entry stream is contiguous (0.20.0, 0.21.0, 0.22.0
      all present as entry bullets), so no minor is skipped across that span.

Run non-interactively. Exits non-zero on failure.

Version: 0.41.0
Owner: rabbit-workflow team
Deprecation criterion: when a cross-feature harness enforces changelog/version
continuity workflow-wide, making this per-feature assertion redundant.
"""
import os
import re
import sys

FEATURE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
CHANGELOG = os.path.join(FEATURE_DIR, "docs", "CHANGELOG.md")

PASS = 0
FAIL = 0


def ok(name, msg):
    global PASS
    print(f"  PASS {name}: {msg}")
    PASS += 1


def ko(name, msg):
    global FAIL
    print(f"  FAIL {name}: {msg}", file=sys.stderr)
    FAIL += 1


# t1
if not os.path.isfile(CHANGELOG) or os.path.getsize(CHANGELOG) == 0:
    ko("t1", f"missing or empty: {CHANGELOG}")
    print(f"Results: {PASS} passed, {FAIL} failed")
    sys.exit(1)
ok("t1", "docs/CHANGELOG.md exists and is non-empty")

with open(CHANGELOG, encoding="utf-8") as f:
    text = f.read()

# Collect version headers from ENTRY bullets only:
#   - **v0.21.0 — 2026-06-03** — ...
# This deliberately ignores `vN.N.N` strings that appear inside entry prose
# (e.g. per-script version bumps like `install-cron.py 1.0.0 -> 1.1.0`), which
# are not feature-release entries.
entry_re = re.compile(r"^- \*\*v(\d+)\.(\d+)\.(\d+) ", re.MULTILINE)
seen = set()
for m in entry_re.finditer(text):
    seen.add((int(m.group(1)), int(m.group(2)), int(m.group(3))))

# t2
if len(seen) < 2:
    ko("t2", f"fewer than two entry-bullet version headers found: "
             f"{sorted(seen)}")
    print(f"Results: {PASS} passed, {FAIL} failed")
    sys.exit(1)
ok("t2", f"{len(seen)} distinct entry-bullet version headers present")

# t3: the specific #517 gap — 0.21.0 present when 0.20.0 and 0.22.0 are present.
if (0, 21, 0) in seen:
    ok("t3", "0.21.0 entry present (the #517 gap is closed)")
elif (0, 20, 0) in seen and (0, 22, 0) in seen:
    ko("t3", "0.20.0 and 0.22.0 entries present but 0.21.0 is MISSING "
             "(#517 gap)")
else:
    ok("t3", "0.20.0/0.22.0 span not both present; #517-specific check n/a")

# t4: the documented 0.20.0 -> 0.22.0 release stream is contiguous.
span = [(0, 20, 0), (0, 21, 0), (0, 22, 0)]
if all(v in seen for v in span):
    ok("t4", "0.20.0 -> 0.21.0 -> 0.22.0 entry stream is contiguous")
elif (0, 20, 0) in seen and (0, 22, 0) in seen:
    missing = [f"{a}.{b}.{c}" for (a, b, c) in span if (a, b, c) not in seen]
    ko("t4", f"0.20.0->0.22.0 stream is missing entries: {missing}")
else:
    ok("t4", "0.20.0/0.22.0 span endpoints not both present; check n/a")

print()
print(f"Results: {PASS} passed, {FAIL} failed")
sys.exit(0 if FAIL == 0 else 1)
