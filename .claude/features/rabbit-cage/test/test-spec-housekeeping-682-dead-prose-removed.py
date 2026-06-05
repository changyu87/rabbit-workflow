#!/usr/bin/env python3
"""test-spec-housekeeping-682-dead-prose-removed.py — issue #682 (round 2 of #677).

End-to-end content regression that rabbit-cage's live docs/spec.md no longer
carries the dead / historical / redundant prose removed by the #682 measured
line-removal pass. Each banned phrase below was verified DEAD or REDUNDANT by a
deterministic #639 check at removal time (past-defect narration, a rationale
paragraph duplicated verbatim across two invariants, or a three-layout
dual-read description restated in full three times). The surface describes the
CURRENT design; this narration belongs in commit messages and the CHANGELOG,
not the spec body.

The phrases removed and the #639 check that proved each dead/redundant:

  1. "Before this invariant was added, scope-guard wrote at" (Inv 25)
     — historical-edit narration of a past defect. The CURRENT invariant
       (single per-mode canonical location) is fully stated immediately
       above; the "what it used to do and why it was broken" sentence is
       CHANGELOG material.

  2. "the prior `_BOX_WIDTH - 2 = 30` char-column math under-counted"
     (Inv 38) — past-defect narration. The CURRENT math (inner field of
       2*_BOX_WIDTH - 4 = 60) is fully specified; the prior-math clause is
       CHANGELOG material.

  3. "a confusing and load-bearing two-run requirement that produces"
     (Inv 22h) — rationale narration of a defect the MUST already prevents.
       The normative "MUST os.execv ... BEFORE the copy loops" statement is
       the contract; the failure-mode storytelling is redundant.

  4. "Rationale — REJECTED alternative: dynamic" (Inv 27d) — verbatim
       duplicate of the GitHub-API rejection rationale already stated in
       Inv 26 (the line even says "Same rejection as Inv 26"). Collapsed to
       the single Inv 26 authoritative statement (rule #3, collapse
       redundancy).

  5. "csh/tcsh users have no way to inline-set" (Inv 27a) — rationale
       narration. The shell-agnostic behavior ("works in bash/zsh/csh/...")
       is stated; the justification paragraph is redundant.

  6. The three-layout dual-read carve-out is the AUTHORITATIVE subject of
       Inv 33; the full restatement in the scope-guard Semantics prose
       section (and Inv 17 a2) is redundant (rule #3). The verbose
       "Under `specs/` and legacy `docs/spec/` only the basename" sentence
       MUST survive in at most one location.

Non-interactive. Exits non-zero on failure.
"""

import os
import sys

TEST_DIR = os.path.dirname(os.path.abspath(__file__))
FEATURE_DIR = os.path.normpath(os.path.join(TEST_DIR, ".."))
SPEC = os.path.join(FEATURE_DIR, "docs", "spec.md")

# Verbatim dead/redundant phrases that MUST be absent from the live spec body.
# The `/rabbit-config` coexistence phrases are DEAD: the rabbit-config feature
# was retired, so the spec MUST NOT claim the central surface is "still live"
# or that "both surfaces are live".
BANNED_PHRASES = [
    "Before this invariant was added, scope-guard wrote at",
    "the prior `_BOX_WIDTH - 2 = 30` char-column math under-counted",
    "a confusing and load-bearing two-run requirement that produces",
    "Rationale — REJECTED alternative: dynamic",
    "csh/tcsh users have no way to inline-set",
    "The central `/rabbit-config scope-guard on`",
    "still-live central `/rabbit-config <sub>` surface",
    "both surfaces are live and mutate the same configurable",
]

# The verbose three-layout dual-read sentence MUST appear at most ONCE across
# the spec (round-1 left it restated in full in the scope-guard Semantics prose
# section AND Inv 17(a2) AND the authoritative Inv 33).
COLLAPSE_MARKER = "Under `specs/` and legacy `docs/spec/` only the basename"
COLLAPSE_MAX = 1

# Measured line-removal floor: round-1 left spec.md at 518 lines. The #682
# pass MUST cut real lines, not reword. Assert a hard ceiling well below the
# starting count so a future reword that re-inflates the body fails the gate.
# Ceiling raised 500 -> 510 by #709, which expanded Inv 7 to document the new
# `scope-guard` /rabbit-config configurable and the command-form revoke
# instruction — a real spec addition, not reword re-inflation; still well
# below the 518 starting count. Raised 510 -> 515 by #767 (phase 3 of #733),
# which added Inv 40 documenting the per-feature `/rabbit-cage-config` command
# + the deferred per-feature alert — a real spec addition, not re-inflation.
# Raised 515 -> 520 by #780 (retire-rabbit-config step 1 of #769), which
# re-homed the bypass-permissions per-feature alert into Inv 16 + Inv 40c
# (a fifth SessionStart entry + new emit_configurable_alert wiring) — a real
# spec addition, not re-inflation. Lowered 520 -> 515 by the rabbit-config
# retirement reduction wave (measured 519 -> 515), which cut the now-dead
# `/rabbit-config` coexistence prose from Inv 7, Inv 31, Inv 40, Inv 40c,
# and Out of Scope. The cuts are inline-sentence removals inside wrapped
# paragraphs, so the honest line delta is 4 — no load-bearing prose was
# force-cut to chase a larger number. Raised 515 -> 525 by #848, which reworked
# Inv 26 + Inv 27 to make the install default ref resolve GitHub's latest
# release dynamically (with an offline fallback) — a real spec addition
# documenting the new resolution ladder + graceful-degradation contract, not
# reword re-inflation. Raised 525 -> 526 by #850, which extended Inv 27 with
# the dynamic-default downgrade guard (the update ACTION must track the
# update-CHECK and never resolve a ref older than what is installed) plus its
# enforcing-test reference — a real spec addition documenting new behavior, not
# reword re-inflation. Raised 526 -> 537 by #855, which added Inv 41 (and a
# bullet in the scope-guard Semantics ALLOWED list) documenting that
# rabbit-cage's scope marker authorizes its owned repo-root bootstrap files
# (install.sh / install.py / README.md) without an override — a real spec
# addition documenting new scope-guard behavior, not reword re-inflation.
# Raised 537 -> 539 by #849, which added Inv 42 documenting the end-to-end
# plugin-install readiness test (the REAL installer run into a sandbox, asserting
# the whole tree is present + every hook path wired, no Claude launch) — a real
# spec addition documenting new test-enforced behavior, not reword re-inflation.
# Raised 539 -> 541 by #851, which added Inv 43 documenting that install.py
# canonicalizes installed surfaces via the publish flow so a fresh install is
# drift-free on its first Stop (with the RABBIT_ROOT-anchored publish_hook form
# + graceful degradation) — a real spec addition documenting new behavior, not
# reword re-inflation.
# Raised 541 -> 542 by #891, which added Inv 44 documenting that the SessionStart
# mode-marker WRITE path is reconciled to equal the scope-guard READ path (the
# plugin-install doubled-.rabbit fix) — a real spec addition documenting new
# behavior, not reword re-inflation.
SPEC_LINE_CEILING = 542

PASS = 0
FAIL = 0


def ok(name, msg):
    global PASS
    print(f"  PASS {name}: {msg}")
    PASS += 1


def fail(name, msg):
    global FAIL
    print(f"  FAIL {name}: {msg}", file=sys.stderr)
    FAIL += 1


if not os.path.isfile(SPEC):
    fail("exist", f"missing surface: {SPEC}")
else:
    with open(SPEC) as f:
        body = f.read()
    for phrase in BANNED_PHRASES:
        if phrase in body:
            fail("dead-prose", f"dead phrase still present in docs/spec.md: {phrase!r}")
        else:
            ok("dead-prose", f"absent: {phrase!r}")

    count = body.count(COLLAPSE_MARKER)
    if count > COLLAPSE_MAX:
        fail("collapse",
             f"three-layout dual-read restated {count}x (max {COLLAPSE_MAX}); "
             "collapse to the authoritative Inv 33")
    else:
        ok("collapse",
           f"three-layout dual-read description appears {count}x (<= {COLLAPSE_MAX})")

    n_lines = body.count("\n") + (0 if body.endswith("\n") else 1)
    if n_lines > SPEC_LINE_CEILING:
        fail("line-floor",
             f"docs/spec.md is {n_lines} lines (> ceiling {SPEC_LINE_CEILING}); "
             "the #682 pass must REMOVE lines, not reword")
    else:
        ok("line-floor", f"docs/spec.md is {n_lines} lines (<= {SPEC_LINE_CEILING})")

print()
print(f"Results: {PASS} passed, {FAIL} failed")

if FAIL > 0:
    print("test-spec-housekeeping-682-dead-prose-removed: FAIL", file=sys.stderr)
    sys.exit(1)

print("test-spec-housekeeping-682-dead-prose-removed: all checks passed.")
sys.exit(0)
