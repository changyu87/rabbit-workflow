#!/usr/bin/env python3
"""Inv 49 — `--affected-invariants` scoped spec embedding.

Four scenarios:

  A) Baseline (flag omitted): assembled prompt contains the full spec —
     every numbered invariant from the source spec.md appears in the
     embedded SPEC block.

  B) Scoped subset (flag with a valid subset): assembled prompt contains
     the named invariants AND does NOT contain non-named invariants AND
     contains the NOTE line naming the count + list.

  C) Unknown number: dispatcher exits 1 with stderr substring 'unknown
     invariant number'.

  D) Size assertion: scoped prompt is materially smaller than full-spec
     form (at least 30% reduction for any feature with >=10 invariants).

The fixture is the rabbit-cage spec.md (longest spec, has retired
tombstones, >20 invariants) — a good stress test.
"""
import os
import re
import subprocess
import sys

from _helpers import DISPATCH_PY, REPO_ROOT, report

passed = failed = 0


def ok(msg):
    global passed
    passed += 1
    print(f"  ok   {msg}")


def ko(msg):
    global failed
    failed += 1
    print(f"  FAIL {msg}")


FIXTURE_FEATURE = "rabbit-cage"
FIXTURE_SPEC = os.path.join(
    REPO_ROOT, ".claude", "features", FIXTURE_FEATURE,
    "docs", "spec", "spec.md",
)


def _spec_invariant_numbers(spec_path):
    """Return the sorted list of invariant numbers in the ## Invariants
    section of the given spec file. Includes retired tombstones."""
    with open(spec_path) as f:
        text = f.read()
    m = re.search(r"^## Invariants\s*$(.*?)(?=^## |\Z)", text,
                  re.MULTILINE | re.DOTALL)
    if not m:
        return []
    body = m.group(1)
    return sorted({int(x) for x in re.findall(r"^([0-9]+)\.\s", body,
                                              re.MULTILINE)})


def _invariants_section_of_prompt(prompt):
    """Extract the ## Invariants section body from the embedded spec in
    the assembled prompt. The prompt contains the spec verbatim in the
    SPEC block, including the `## Invariants` heading. We slice from
    the heading to the next `## ` heading (or end of SPEC block).

    Returns empty string if no ## Invariants section found.
    """
    m = re.search(r"^## Invariants\s*$", prompt, re.MULTILINE)
    if not m:
        return ""
    body_start = prompt.find("\n", m.end()) + 1
    nxt = re.search(r"^## ", prompt[body_start:], re.MULTILINE)
    body_end = body_start + nxt.start() if nxt else len(prompt)
    return prompt[body_start:body_end]


env_base = os.environ.copy()
env_base.pop("RABBIT_ROOT", None)

ALL_INVS = _spec_invariant_numbers(FIXTURE_SPEC)
if not ALL_INVS:
    ko(f"fixture {FIXTURE_SPEC} has no parseable invariants; cannot run test")
    report(passed, failed)


# ---------------------------------------------------------------------------
# Scenario A: baseline — flag omitted, full spec embedded.
# ---------------------------------------------------------------------------
res_full = subprocess.run(
    [sys.executable, DISPATCH_PY, "--scope", FIXTURE_FEATURE,
     "--spec", FIXTURE_SPEC],
    capture_output=True, text=True, env=env_base,
)
if res_full.returncode != 0:
    ko(f"scenario A: dispatch failed rc={res_full.returncode}: "
       f"{res_full.stderr!r}")
    full_prompt = ""
else:
    full_prompt = res_full.stdout
    # Check every numbered invariant appears in the embedded ## Invariants
    # section of the spec block. Scope the grep to that section (other
    # spec sections also contain numbered lists like "1. ..." that would
    # collide otherwise).
    full_inv_body = _invariants_section_of_prompt(full_prompt)
    missing = [n for n in ALL_INVS
               if not re.search(rf"^{n}\.\s", full_inv_body, re.MULTILINE)]
    if not missing:
        ok(f"scenario A: full-spec form embeds all {len(ALL_INVS)} "
           "invariants from source")
    else:
        ko(f"scenario A: full-spec form missing invariants: {missing!r}")


# ---------------------------------------------------------------------------
# Scenario B: scoped subset — only named invariants are embedded.
# ---------------------------------------------------------------------------
# Pick three valid (non-retired) invariants from the fixture. Use the
# first three available numbers in ALL_INVS that look reasonable.
# rabbit-cage has invariants 1..30 with some retired tombstones; we
# pick 4, 16, 22 per the impl-suggestion's hint.
desired = [4, 16, 22]
desired = [n for n in desired if n in ALL_INVS]
if len(desired) < 2:
    ko(f"scenario B: fixture does not contain enough of [4,16,22]; "
       f"available: {ALL_INVS}")
else:
    flag_value = ",".join(str(n) for n in desired)
    res_scoped = subprocess.run(
        [sys.executable, DISPATCH_PY, "--scope", FIXTURE_FEATURE,
         "--spec", FIXTURE_SPEC,
         "--affected-invariants", flag_value],
        capture_output=True, text=True, env=env_base,
    )
    if res_scoped.returncode != 0:
        ko(f"scenario B: dispatch failed rc={res_scoped.returncode}: "
           f"{res_scoped.stderr!r}")
        scoped_prompt = ""
    else:
        scoped_prompt = res_scoped.stdout
        scoped_inv_body = _invariants_section_of_prompt(scoped_prompt)
        # All named invariants present in the Invariants section.
        for n in desired:
            if re.search(rf"^{n}\.\s", scoped_inv_body, re.MULTILINE):
                ok(f"scenario B: scoped prompt contains invariant {n}")
            else:
                ko(f"scenario B: scoped prompt missing requested invariant {n}")
        # Non-named invariants absent from the Invariants section.
        not_named = [n for n in ALL_INVS if n not in desired]
        leaked = [n for n in not_named
                  if re.search(rf"^{n}\.\s", scoped_inv_body, re.MULTILINE)]
        if not leaked:
            ok(f"scenario B: scoped prompt embeds no unrequested "
               f"invariants ({len(not_named)} checked)")
        else:
            ko(f"scenario B: scoped prompt leaked unrequested invariants: "
               f"{leaked!r}")
        # NOTE line present with count + list.
        note_re = (r"NOTE:\s+scoped view of "
                   rf"{len(desired)}\s+selected invariants")
        if re.search(note_re, scoped_prompt):
            ok("scenario B: NOTE line present naming count + scoped view")
        else:
            ko("scenario B: NOTE line missing or malformed in scoped prompt")


# ---------------------------------------------------------------------------
# Scenario C: unknown invariant number is fatal.
# ---------------------------------------------------------------------------
# Pick a number guaranteed not to be in ALL_INVS.
bogus = max(ALL_INVS) + 999
res_bogus = subprocess.run(
    [sys.executable, DISPATCH_PY, "--scope", FIXTURE_FEATURE,
     "--spec", FIXTURE_SPEC,
     "--affected-invariants", str(bogus)],
    capture_output=True, text=True, env=env_base,
)
if res_bogus.returncode == 1:
    ok(f"scenario C: unknown invariant number {bogus} exits 1")
else:
    ko(f"scenario C: expected exit 1 for unknown number {bogus}, "
       f"got rc={res_bogus.returncode}")
if "unknown invariant number" in res_bogus.stderr:
    ok("scenario C: stderr contains 'unknown invariant number'")
else:
    ko(f"scenario C: stderr missing 'unknown invariant number'; "
       f"got: {res_bogus.stderr!r}")


# ---------------------------------------------------------------------------
# Scenario D: size win — scoped prompt at most 70% of full prompt.
# ---------------------------------------------------------------------------
if full_prompt and len(desired) >= 2:
    res_scoped2 = subprocess.run(
        [sys.executable, DISPATCH_PY, "--scope", FIXTURE_FEATURE,
         "--spec", FIXTURE_SPEC,
         "--affected-invariants", ",".join(str(n) for n in desired)],
        capture_output=True, text=True, env=env_base,
    )
    if res_scoped2.returncode != 0:
        ko(f"scenario D: scoped dispatch failed rc={res_scoped2.returncode}")
    else:
        full_size = len(full_prompt)
        scoped_size = len(res_scoped2.stdout)
        ratio = scoped_size / full_size if full_size else 1.0
        # >=30% reduction => scoped <= 70% of full.
        if ratio <= 0.70:
            ok(f"scenario D: scoped/full size ratio {ratio:.2f} "
               f"(scoped={scoped_size}, full={full_size}) <= 0.70")
        else:
            ko(f"scenario D: scoped/full size ratio {ratio:.2f} "
               f"(scoped={scoped_size}, full={full_size}) > 0.70 "
               "(insufficient size win)")
else:
    ko("scenario D: skipped — scenario A failed or scenario B inputs missing")


report(passed, failed)
