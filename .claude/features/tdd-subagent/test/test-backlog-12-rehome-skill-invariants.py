#!/usr/bin/env python3
# E2E test for BACKLOG-12: re-home four SKILL.md content invariants
# (former Inv 15, 17, 18, 26 of tdd-subagent v1.19.0) into the
# rabbit-feature spec; renumber survivors gap-free.
#
# This is the tdd-subagent-side of the change: the tdd-subagent spec no
# longer carries the four cross-feature invariants and its surviving
# invariants are renumbered gap-free. The behaviours themselves continue
# to exist; they are simply declared by their new owner (rabbit-feature),
# which is the secondary feature touched by the same rabbit-feature-touch
# cycle.
#
# Assertions on tdd-subagent/docs/spec/spec.md:
#   - version bumped to 1.20.0
#   - the four cross-feature invariant subjects are gone from the
#     Invariants section body
#   - a "Migrated Invariants (BACKLOG-12)" trace table is present and
#     lists exactly the four moves with the new rabbit-feature numbers
#   - the surviving invariants are numbered 1..28 contiguously (no gaps,
#     no duplicates)
#   - cross-references inside the spec body point at the new numbers:
#       * Inv 25 holds the feature.json schema reference
#       * Inv 27 holds the HANDOFF JSON inline-declaration rule
#       * the "Contract Schema References" section mentions Inv 25 and
#         Inv 27 (not the old Inv 29 / Inv 31)
#   - the "Out of Scope" section names SKILL.md content invariants as
#     out-of-scope (cross-feature ownership statement)
import os
import re
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SPEC = os.path.abspath(os.path.join(
    SCRIPT_DIR, "..", "docs", "spec", "spec.md"
))

PASS = 0
FAIL = 0


def ok(msg):
    global PASS
    PASS += 1
    print(f"  ok   {msg}")


def ko(msg):
    global FAIL
    FAIL += 1
    print(f"  FAIL {msg}")


def main():
    if not os.path.isfile(SPEC):
        ko(f"spec.md not found at {SPEC}")
        return 1
    with open(SPEC) as f:
        spec = f.read()

    # 1. Version bump.
    # BACKLOG-12 bumped the spec to 1.20.0; later cycles may bump further
    # (e.g., BACKLOG-13 -> 1.21.0). Accept any 1.x version with x >= 20
    # rather than pinning to a single value.
    m = re.search(r"^version:\s*1\.(\d+)\.(\d+)\s*$", spec, re.MULTILINE)
    if m and int(m.group(1)) >= 20:
        ok(f"spec version is 1.{m.group(1)}.{m.group(2)} (>= 1.20.0)")
    else:
        ko(f"spec version is not >= 1.20.0 (got: {m.group(0) if m else 'no match'})")

    # 2. Slice the Invariants section body (between "## Invariants"
    #    heading and the next "## " heading).
    inv_start = spec.find("## Invariants")
    if inv_start < 0:
        ko("'## Invariants' header missing in spec.md")
        return 1
    # Find the next top-level heading after Invariants.
    next_h2 = spec.find("\n## ", inv_start + len("## Invariants"))
    inv_body = spec[inv_start:next_h2 if next_h2 > 0 else len(spec)]

    # 3. Surviving invariants are numbered 1..28 contiguously.
    nums = [int(m.group(1)) for m in re.finditer(
        r"^(\d+)\.\s", inv_body, re.MULTILINE
    )]
    expected = list(range(1, 29))
    if nums == expected:
        ok("invariant numbering is contiguous 1..28 with no gaps or dups")
    else:
        ko(f"invariant numbering not 1..28 contiguous: got {nums}")

    # 4. The four removed cross-feature invariant SUBJECTS no longer
    #    appear as authoritative invariants in the body. We assert by
    #    looking for distinctive phrases that were unique to those
    #    invariants in the v1.19.0 spec.
    forbidden_subjects = [
        # Former Inv 15 (Step 4 bypass-marker SKILL.md doc requirement)
        "BEFORE any in-conversation\n    wait or impl-suggestion surfacing",
        # Former Inv 17 (Red Flags: no main-session Write/Edit on .claude/features/)
        "main session orchestrator MUST NOT use\n    Write or Edit tools",
        # Former Inv 18 (Red Flags: no main-session scope markers; PR #93)
        "constitution violations (PR #93)",
        # Former Inv 26 (B/B mode item.json read rule)
        "B/B mode MUST\n    read the item JSON from `<item-dir>/item.json`",
    ]
    leaked = [s for s in forbidden_subjects if s in inv_body]
    if not leaked:
        ok("four migrated invariant subjects no longer in Invariants body")
    else:
        ko(f"migrated invariant subjects still present in body: {leaked}")

    # 5. A "Migrated Invariants (BACKLOG-12)" trace section exists.
    migrated_header = "## Migrated Invariants (BACKLOG-12)"
    if migrated_header in spec:
        ok("Migrated Invariants (BACKLOG-12) trace section present")
    else:
        ko(f"'{migrated_header}' section missing from spec.md")
        return 1

    migrated_start = spec.find(migrated_header)
    next_h2_after_mig = spec.find("\n## ", migrated_start + len(migrated_header))
    migrated_body = spec[migrated_start:
                         next_h2_after_mig if next_h2_after_mig > 0 else len(spec)]

    # 6. The trace table lists all four moves with the correct new
    #    rabbit-feature invariant numbers.
    expected_rows = [
        ("Inv 15 (v1.19.0)", "Inv 9",
         "Step 4 `.rabbit-human-approval-bypass` marker doc"),
        ("Inv 17 (v1.19.0)", "Inv 10",
         "Red Flags — no main-session Write/Edit on `.claude/features/`"),
        ("Inv 18 (v1.19.0)", "Inv 11",
         "Red Flags — no main-session scope markers"),
        ("Inv 26 (v1.19.0)", "Inv 12",
         "B/B mode reads `item.json` (not `bug.json`)"),
    ]
    for old, new, subject_fragment in expected_rows:
        # Row must contain the old number, the new number, AND a
        # distinctive subject fragment (allow slight wording flex by
        # checking for any of these per row).
        if old in migrated_body and new in migrated_body and subject_fragment in migrated_body:
            ok(f"trace row present: {old} -> {new} ({subject_fragment})")
        else:
            ko(f"trace row missing or malformed for {old} -> {new}; "
               f"expected subject fragment '{subject_fragment}'")

    # 7. Internal cross-references point at the new numbers:
    #    - feature.json schema reference is at Inv 25 (was Inv 29)
    #    - HANDOFF JSON inline-declaration is at Inv 27 (was Inv 31)
    csr = spec.find("## Contract Schema References")
    if csr < 0:
        ko("'## Contract Schema References' section missing")
    else:
        csr_next = spec.find("\n## ", csr + 1)
        csr_body = spec[csr:csr_next if csr_next > 0 else len(spec)]
        if "Inv 25" in csr_body and "Inv 27" in csr_body:
            ok("Contract Schema References cites Inv 25 and Inv 27")
        else:
            ko("Contract Schema References does not cite Inv 25 / Inv 27")
        # Stale numbers must not leak into the cross-reference section.
        for stale in ("Inv 29", "Inv 31", "Inv 33"):
            if stale in csr_body:
                ko(f"Contract Schema References still cites stale '{stale}'")

    # 8. Inv 26 (the renumbered shared-fixture invariant) references
    #    Inv 25 internally (was 'Inv 29' before the gap-free renumber).
    if re.search(r"\(per Inv 25\)", inv_body):
        ok("Inv 26 internal '(per Inv 25)' reference is updated from 'per Inv 29'")
    else:
        ko("Inv 26 still references the stale 'per Inv 29' (should be 'per Inv 25')")

    # 9. Out of Scope names SKILL.md content invariants for
    #    rabbit-feature-touch as out-of-scope.
    oos = spec.find("## Out of Scope")
    if oos < 0:
        ko("'## Out of Scope' section missing")
    else:
        oos_body = spec[oos:]
        if "SKILL.md content invariants" in oos_body and "rabbit-feature" in oos_body:
            ok("Out of Scope names SKILL.md content invariants (rabbit-feature ownership)")
        else:
            ko("Out of Scope does not name SKILL.md content invariants as out of scope")

    print()
    print(f"summary: {PASS} passed, {FAIL} failed")
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
