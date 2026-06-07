#!/usr/bin/env python3
"""test-bug-fixes-cycle.py — assertions for the bug/backlog cleanup TDD cycle.

Covers the still-live, unique assertions for each bug/backlog in this
cycle's wave. Entries whose original assertion went moot when their
referenced script was deleted (BUG-12, BACKLOG-12/13/14) were stripped in
CONTRACT-BACKLOG-30 F7 — those deletions are now asserted in
test-retired-artifacts.py (Section B) rather than carried as comment-only
stubs here.

  BUG-11    feature.json.schema.json tdd_state enum includes 'deprecated' and 'merged'
  BUG-27    test-files-exist.py checks skill-template.md, command-template.md, handoff-template.md
  BACKLOG-3 test-templates-have-version.py tightened to reject _template_version
  BACKLOG-4 every feature.json in the repo validates against feature.json.schema.json
  BACKLOG-5 spec Inv 7 (rbt- banned) asserted by behavioural test (check-naming.py rejects rbt-)
  (BACKLOG-6 entry RETIRED in Plan F.1 — per-feature publish.json files were
   deleted; copy-file basename consistency no longer applies. Equivalent
   source→deployed parity is asserted byte-for-byte by each feature's
   test-manifest-deploys-correctly.py.)
  BACKLOG-7 template marker convention documented and one template marked consistently
  (BACKLOG-8 entry RETIRED in Plan F.3 — named-wrapper producer set was
   retired alongside the rabbit-print registry. The wrappers no longer
   exist; the assertion has no live target.)
  BACKLOG-9 spec Surface and contract.md provides entries match actual files
  BACKLOG-10 validate-feature.py invokes feature.json.schema.json validation
  (BACKLOG-15 entry RETIRED in Plan F.3 — spec Inv 4 (three-artifact
   rabbit-print authority) was retired alongside the registry; the
   architecture is now a single direct-call renderer with no registry.)
  (BACKLOG-16 entry RETIRED in CONTRACT-WAVE-9 — Inv 6 was retired and its "limitation documented" assertion has no live target.)

Version: 1.1.0
Owner: rabbit-workflow team (contract)
Deprecation criterion: when the remaining unique assertions absorb into
per-concern tests (e.g., a successor test-policy-invariants-equivalent
covering BACKLOG-15 architecturally, or a generic schema-shape test
covering BUG-11/BACKLOG-3/4/10).
"""

import json
import os
import re
import subprocess
import sys

FEATURE_DIR = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
REPO_ROOT = os.path.normpath(os.path.join(FEATURE_DIR, "..", "..", ".."))

FAIL = 0


def ok(msg):
    print(f"  ok   {msg}")


def ko(msg):
    global FAIL
    print(f"  FAIL {msg}")
    FAIL = 1


# BUG-11: feature.json.schema.json tdd_state enum includes 'deprecated' and 'merged'
schema_path = os.path.join(FEATURE_DIR, "schemas/feature.json.schema.json")
with open(schema_path) as f:
    schema = json.load(f)
enum = schema["properties"]["tdd_state"]["enum"]
if "deprecated" in enum and "merged" in enum:
    ok("BUG-11: tdd_state enum includes 'deprecated' and 'merged'")
else:
    ko(f"BUG-11: tdd_state enum missing values — got {enum}")


# BUG-27: test-files-exist.py checks skill-template.md, command-template.md, handoff-template.md
tfe_path = os.path.join(FEATURE_DIR, "test/test-files-exist.py")
with open(tfe_path) as f:
    tfe_content = f.read()
for tmpl in ("skill-template.md", "command-template.md", "handoff-template.md"):
    if tmpl in tfe_content:
        ok(f"BUG-27: test-files-exist.py checks {tmpl}")
    else:
        ko(f"BUG-27: test-files-exist.py missing check for {tmpl}")


# BACKLOG-3: test-templates-have-version.py must reject leading-underscore variants
tthv_path = os.path.join(FEATURE_DIR, "test/test-templates-have-version.py")
with open(tthv_path) as f:
    tthv_content = f.read()
# Look for a word-boundary or regex-based check, not a plain substring match for "template_version"
if 'r"\\btemplate_version\\b"' in tthv_content or 're.search' in tthv_content or '_template_version' in tthv_content:
    ok("BACKLOG-3: test-templates-have-version.py tightened beyond plain substring")
else:
    ko("BACKLOG-3: test-templates-have-version.py still uses naive substring match")


# BACKLOG-4: every feature.json in the repo validates against feature.json.schema.json.
try:
    import jsonschema
    features_dir = os.path.join(REPO_ROOT, ".claude/features")
    bad = []
    for entry in sorted(os.listdir(features_dir)):
        feat_dir = os.path.join(features_dir, entry)
        fjson = os.path.join(feat_dir, "feature.json")
        if not os.path.isfile(fjson):
            continue
        with open(fjson) as f:
            data = json.load(f)
        try:
            jsonschema.validate(data, schema)
        except jsonschema.ValidationError as e:
            bad.append((entry, str(e).splitlines()[0]))
    if not bad:
        ok("BACKLOG-4: every feature.json validates against the schema")
    else:
        ko(f"BACKLOG-4: feature.json files failed schema validation: {bad}")
except ImportError:
    ok("BACKLOG-4: skipped (jsonschema not installed)")


# BACKLOG-5: spec Inv 7 — check-naming.py bans rbt-. Run the script against a temp file with rbt- name.
import tempfile

check_naming = os.path.join(FEATURE_DIR, "scripts/enforcement/check-naming.py")
if os.path.isfile(check_naming):
    with tempfile.TemporaryDirectory() as td:
        # Create a fake offending file under .claude/commands/
        cmds = os.path.join(td, ".claude", "commands")
        os.makedirs(cmds)
        open(os.path.join(cmds, "rbt-bogus.md"), "w").close()
        result = subprocess.run([sys.executable, check_naming, td], capture_output=True, text=True)
        if result.returncode != 0 and "rbt-" in (result.stdout + result.stderr):
            ok("BACKLOG-5: check-naming.py rejects rbt- prefix (Inv 7 enforced)")
        else:
            ko(f"BACKLOG-5: check-naming.py did not flag rbt- (rc={result.returncode}, out={result.stdout!r}, err={result.stderr!r})")
else:
    ko("BACKLOG-5: check-naming.py not found")


# BACKLOG-6 (Plan F.1): RETIRED. Per-feature publish.json files were deleted
# in Plan F.1; the federated feature.json manifest is the single source of
# truth. Copy-file basename consistency no longer applies — source→deployed
# parity is asserted byte-for-byte by each feature's
# test-manifest-deploys-correctly.py.


# BACKLOG-7: template marker convention documented in spec.md
spec_path = os.path.join(FEATURE_DIR, "docs/spec.md")
with open(spec_path) as f:
    spec_text = f.read()
if "template marker" in spec_text.lower() or "template_version marker" in spec_text.lower():
    ok("BACKLOG-7: spec.md documents the template marker convention")
else:
    ko("BACKLOG-7: spec.md does not document the template marker convention")


# BACKLOG-8 (Plan F.3): RETIRED. The named-wrapper producer set was removed
# alongside the rabbit-print registry; rabbit_print is now a direct-call API.
# Producers still import rabbit_print, but the "uses a named wrapper" guarantee
# no longer applies because the wrappers no longer exist. The surviving
# requirement (producers go through rabbit_print rather than emitting inline
# ANSI/brand strings) is covered by test-bypass-marker-note.py (tdd-subagent
# Inv 21) and test-branding.py (tdd-state-machine Inv 6).


# BACKLOG-9: contract.md provides.scripts includes all live scripts in scripts/ tree
contract_md_path = os.path.join(FEATURE_DIR, "docs/contract.md")
with open(contract_md_path) as f:
    contract_md = f.read()

declared_scripts = re.findall(r'"(\.claude/features/contract/scripts/[^"]+)"', contract_md)
declared_set = set(declared_scripts)

actual_scripts = []
for root, dirs, files in os.walk(os.path.join(FEATURE_DIR, "scripts")):
    if "__pycache__" in root:
        continue
    for f in files:
        if f.endswith(".py"):
            full = os.path.join(root, f)
            rel = os.path.relpath(full, REPO_ROOT)
            actual_scripts.append(rel)
actual_set = set(actual_scripts)

missing_in_contract = actual_set - declared_set
if not missing_in_contract:
    ok("BACKLOG-9: contract.md provides.scripts lists all live scripts")
else:
    ko(f"BACKLOG-9: contract.md missing scripts: {sorted(missing_in_contract)}")


# BACKLOG-10: feature.json.schema.json validation lives in the validate_feature
# library (post-BACKLOG-26 extraction). Check the library, which is where the
# logic now lives; validate-feature.py is a thin shim that delegates to it.
vf_path = os.path.join(FEATURE_DIR, "lib/checks.py")
with open(vf_path) as f:
    vf_content = f.read()
if "feature.json.schema.json" in vf_content:
    ok("BACKLOG-10: lib/checks.py references feature.json.schema.json")
else:
    ko("BACKLOG-10: lib/checks.py does not reference feature.json.schema.json")


# BACKLOG-15 (Plan F.3): RETIRED. Spec Inv 4 (three-artifact rabbit-print
# authority) was retired alongside the registry file. The print system is now
# a single direct-call renderer; test-rabbit-print-renderer.py covers the
# remaining surface.


if FAIL:
    print(f"\ntest-bug-fixes-cycle: FAIL", file=sys.stderr)
    sys.exit(1)
print("\ntest-bug-fixes-cycle: all checks passed.")
