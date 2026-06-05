#!/usr/bin/env python3
"""test-install-referenced-scripts-listed.py — Inv 65.

Cross-feature install referenced->listed closure gate. The companion to
Inv 64's listed->exists direction.

Inv 64 (`test-install-closure-integrity.py`) screens the install closure
in the listed->exists direction: every SOURCE path the rabbit-cage install
closure ENUMERATES exists on disk. The INVERSE direction was not screened
by the repo-wide gate: a script that an install-SHIPPED SKILL.md REFERENCES
via a literal `.claude/features/<feature>/scripts/<name>.py` path, but that
is ABSENT from `install.py`'s `FEATURE_INCLUDES[<feature>]`, never gets
copied during a fresh install — so the shipped skill reaches the user
missing a script it needs. That class was caught only by the rabbit-cage
suite (`test/test-feature-includes-scripts-closure.py`), which runs when
rabbit-cage is touched but does NOT gate an arbitrary feature's PR; #897
(rabbit-decompose's handoff-scaffold.py) slipped through exactly here.

This test wires the referenced->listed check into contract's cross-feature
gate (the repo-wide gate that runs on every feature's PR). It scans every
SKILL.md install.py SHIPS (its SKILLS list — the authoritative shipped
surface, the same surface install.py copies and the rabbit-cage closure
test scans) for literal `scripts/<name>.py` references, imports
`FEATURE_INCLUDES` from `.claude/features/rabbit-cage/install.py` (a
cross-feature READ/INVOKE declared in contract's docs/contract.md), and
asserts every referenced `scripts/<name>.py` is present in
`FEATURE_INCLUDES[<feature>]`.

  t1: every install-shipped-SKILL-referenced scripts/<name>.py is listed in
      FEATURE_INCLUDES[<feature>] (referenced_scripts_not_listed returns []).
  t2: RED-proof — given a synthetic FEATURE_INCLUDES copy with a known
      real reference dropped, the SAME checker reports that (skill, feature,
      script) triple. Proves the gate demonstrably catches a
      referenced-but-unlisted script.

The reference-extraction regex mirrors the rabbit-cage closure test's
`SCRIPT_REF_RE`; rabbit-cage's test is not cleanly importable as a library
(it executes assertions at import time), so the minimal logic is mirrored
here rather than editing rabbit-cage.

Degenerate self-build: if rabbit-cage/install.py is legitimately absent (no
install closure to verify), the check is SKIPPED gracefully rather than
errored. In the normal repo install.py is present and the check MUST run.
"""

import importlib.util
import os
import re
import subprocess
import sys

FEATURE_DIR = os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
)


def repo_root():
    result = subprocess.run(
        ["git", "-C", FEATURE_DIR, "rev-parse", "--show-toplevel"],
        capture_output=True, text=True,
    )
    if result.returncode == 0 and result.stdout.strip():
        return result.stdout.strip()
    return os.path.normpath(os.path.join(FEATURE_DIR, "..", "..", ".."))


ROOT = repo_root()
INSTALL_PY = os.path.join(ROOT, ".claude/features/rabbit-cage/install.py")

# Matches literal paths like .claude/features/<feature>/scripts/<name>.py
# (mirrors rabbit-cage test-feature-includes-scripts-closure.py SCRIPT_REF_RE).
SCRIPT_REF_RE = re.compile(r"\.claude/features/([\w-]+)/scripts/([\w.-]+\.py)")

FAIL = 0


def fail_t(n, msg):
    global FAIL
    print(f"FAIL t{n}: {msg}", file=sys.stderr)
    FAIL = 1


def ok(n, msg):
    print(f"PASS t{n}: {msg}")


def extract_skill_refs(skills):
    """Return a sorted list of (skill_src_rel, feature, script_basename)
    triples for every literal scripts/<name>.py reference found in each
    install-shipped SKILL.md body."""
    triples = set()
    for src_rel, _dst_rel in skills:
        src_abs = os.path.join(ROOT, src_rel)
        if not os.path.isfile(src_abs):
            # A missing shipped-skill source is Inv 64's concern
            # (listed->exists); skip here so the two gates stay orthogonal.
            continue
        with open(src_abs) as f:
            body = f.read()
        for feature, script in SCRIPT_REF_RE.findall(body):
            triples.add((src_rel, feature, script))
    return sorted(triples)


def referenced_scripts_not_listed(triples, includes):
    """Return the sorted list of (skill, feature, script) triples whose
    scripts/<script> is NOT present in includes[feature]."""
    missing = []
    for src_rel, feature, script in triples:
        rel = f"scripts/{script}"
        if rel not in set(includes.get(feature, [])):
            missing.append((src_rel, feature, script))
    return missing


# Degenerate self-build: no install closure to verify -> skip gracefully.
if not os.path.isfile(INSTALL_PY):
    print(
        "SKIP t1: rabbit-cage/install.py absent (degenerate self-build); "
        "no install closure to verify"
    )
    print("\nResults: skipped (no install.py)")
    sys.exit(0)

spec = importlib.util.spec_from_file_location(
    "rabbit_cage_install_refclosure", INSTALL_PY
)
install_mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(install_mod)

includes = getattr(install_mod, "FEATURE_INCLUDES", None)
skills = getattr(install_mod, "SKILLS", None)

if includes is None:
    fail_t(1, "rabbit-cage/install.py does not export FEATURE_INCLUDES")
elif skills is None:
    fail_t(1, "rabbit-cage/install.py does not export SKILLS")
else:
    triples = extract_skill_refs(skills)
    missing = referenced_scripts_not_listed(triples, includes)
    if missing:
        named = ", ".join(
            f"{src} -> {feat}/{scr} (scripts/{scr} not in "
            f"FEATURE_INCLUDES[{feat!r}])"
            for src, feat, scr in missing
        )
        fail_t(
            1,
            "install-shipped SKILL.md references script(s) absent from "
            "FEATURE_INCLUDES — fresh install ships the skill without the "
            "script it needs: " + named,
        )
    else:
        ok(
            1,
            f"all {len(triples)} install-shipped-SKILL script reference(s) "
            "are listed in FEATURE_INCLUDES",
        )

    # t2: RED-proof. Drop a known real reference from a SYNTHETIC copy of
    # FEATURE_INCLUDES and assert the SAME checker reports it. This proves
    # the gate would catch a referenced-but-unlisted script (the #897
    # regression class) without mutating the real install.py.
    triples = extract_skill_refs(skills)
    if not triples:
        # No references at all -> cannot construct the RED proof. This is
        # itself a surprising state worth flagging rather than silently
        # passing t2.
        fail_t(
            2,
            "no install-shipped-SKILL script references found; cannot "
            "construct RED-proof fixture",
        )
    else:
        victim_src, victim_feat, victim_scr = triples[0]
        synthetic = {f: list(v) for f, v in includes.items()}
        synthetic[victim_feat] = [
            e for e in synthetic.get(victim_feat, [])
            if e != f"scripts/{victim_scr}"
        ]
        red = referenced_scripts_not_listed(triples, synthetic)
        red_keys = {(f, s) for _src, f, s in red}
        if (victim_feat, victim_scr) in red_keys:
            ok(
                2,
                "RED-proof: dropping scripts/"
                f"{victim_scr} from synthetic FEATURE_INCLUDES["
                f"{victim_feat!r}] makes the checker report "
                f"{victim_feat}/{victim_scr}",
            )
        else:
            fail_t(
                2,
                "RED-proof FAILED: dropping scripts/"
                f"{victim_scr} from FEATURE_INCLUDES[{victim_feat!r}] did "
                "NOT make the checker report it — the gate would not catch "
                "a referenced-but-unlisted script",
            )

print()
print(f"Results: {'all passed' if FAIL == 0 else 'failed'}")
sys.exit(0 if FAIL == 0 else 1)
