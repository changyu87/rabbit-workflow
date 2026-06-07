#!/usr/bin/env python3
"""test-prompts-spec-artifact-agree.py — issue #825

End-to-end check that rabbit-decompose's spec Invariant 1 and its
feature.json `prompts` artifact describe the SAME prompt-contract surface.

Background (#825): an earlier spec Invariant 1 required a one-entry
`prompts` array (id: rabbit-decompose), but feature.json shipped
`prompts: []`. The contract gate's check_prompts_section treats an empty
`prompts` as vacuously valid, so the spec<->artifact mismatch went
uncaught. rabbit-decompose is an inline dispatcher-orchestrated skill with
NO backing subagent, dispatch script, or prompt template — so the real,
coherent state is `prompts: []` and a spec that documents the absence of a
prompt-contract surface (it does not require an entry).

This test pins that coherence so the two surfaces cannot drift apart again:

  - feature.json `prompts` is exactly [] (empty list).
  - spec Invariant 1 does NOT require a `prompts` entry — it must not say
    the prompts array "MUST contain ... one entry".
  - spec Invariant 1 positively documents the empty/absent prompt-contract
    surface (the `prompts` array is empty / no prompt template).
  - There is no prompt template at the contract's convention-resolved path
    templates/prompts/rabbit-decompose.txt (consistent with prompts: []).

If a future change genuinely adds a backing prompt to rabbit-decompose,
this test is the canonical place to flip: it must then assert the one-entry
array AND the template's existence together, never one without the other.

Run non-interactively. Exits non-zero on failure.

Version: 1.0.0
Owner: rabbit-workflow team
Deprecation criterion: when the contract gate validates spec<->prompts
coherence cross-feature (non-vacuously for empty arrays), making this
per-feature assertion redundant.
"""
import json
import os
import re
import sys

FEATURE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
FEATURES_ROOT = os.path.abspath(os.path.join(FEATURE_DIR, ".."))


def fail(msg):
    print(f"FAIL: {msg}", file=sys.stderr)
    sys.exit(1)


# --- feature.json prompts is exactly empty ---------------------------------
with open(os.path.join(FEATURE_DIR, "feature.json"), encoding="utf-8") as f:
    feature = json.load(f)

prompts = feature.get("prompts", None)
if prompts is None:
    fail("feature.json has no `prompts` key")
if not isinstance(prompts, list):
    fail(f"feature.json `prompts` must be a list, got {type(prompts).__name__}")
if prompts != []:
    fail(
        "feature.json `prompts` is non-empty; rabbit-decompose ships no "
        f"prompt-contract surface, expected [] but got {prompts!r}. If a "
        "backing prompt was genuinely added, update spec Invariant 1 AND "
        "add templates/prompts/rabbit-decompose.txt, then flip this test."
    )

# --- locate spec Invariant 1 ------------------------------------------------
with open(os.path.join(FEATURE_DIR, "docs", "spec.md"), encoding="utf-8") as f:
    spec_text = f.read()

m = re.search(r"^## Invariants\s*$", spec_text, re.MULTILINE)
if not m:
    fail("docs/spec.md has no `## Invariants` section")
inv_body = spec_text[m.end():]
# Invariant 1 runs from "1." up to "2." (next numbered invariant).
m1 = re.search(r"^1\.\s", inv_body, re.MULTILINE)
if not m1:
    fail("docs/spec.md has no Invariant 1")
m2 = re.search(r"^2\.\s", inv_body, re.MULTILINE)
inv1 = inv_body[m1.start(): (m2.start() if m2 else len(inv_body))]

# --- Invariant 1 must NOT require a prompts entry ---------------------------
# The bug was a "prompts array MUST contain ... entry" requirement.
bad = re.search(
    r"`?prompts`?\s+array\s+MUST\s+contain", inv1, re.IGNORECASE
)
if bad:
    fail(
        "spec Invariant 1 still requires a `prompts` entry "
        "('prompts array MUST contain ...'), but feature.json `prompts` is "
        "empty. The spec and artifact disagree (#825)."
    )

# --- Invariant 1 must positively document the empty/absent surface ---------
if "prompts" not in inv1.lower():
    fail(
        "spec Invariant 1 does not mention `prompts` at all; it must "
        "document that rabbit-decompose's `prompts` array is empty (no "
        "prompt-contract surface)."
    )
mentions_empty = re.search(
    r"`?prompts`?\s+array\s+(?:MUST\s+be\s+empty|is\s+empty|MUST\s+remain\s+empty)",
    inv1,
    re.IGNORECASE,
)
if not mentions_empty:
    fail(
        "spec Invariant 1 mentions `prompts` but does not assert it is "
        "empty; it must positively document the empty prompt-contract "
        "surface (e.g. 'the `prompts` array MUST be empty')."
    )

# --- no prompt template on disk (consistent with prompts: []) --------------
tpl = os.path.join(
    FEATURES_ROOT, "contract", "templates", "prompts", "rabbit-decompose.txt"
)
if os.path.isfile(tpl):
    fail(
        f"a prompt template exists at {tpl} but feature.json `prompts` is "
        "empty; either declare the prompt in feature.json + spec or remove "
        "the template. The surfaces disagree."
    )

print("All checks passed.")
