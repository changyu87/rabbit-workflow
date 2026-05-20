#!/usr/bin/env python3
"""RABBIT-CAGE-BACKLOG-24: validate-all.py is removed from rabbit-cage.

E2E test verifying the spec change behind BACKLOG-24:
  * Inv 40 no longer enumerates validate-all.py
  * contract.md provides.scripts no longer lists validate-all.py
  * The script file itself is absent from scripts/
  * README.md does not advertise validate-all.py
  * No other rabbit-cage source file references the deleted script
    (test code excepted — tests may still reference the absence as
    an assertion)

Feature-audit duties are now owned by the rabbit-feature-audit skill in
the rabbit-feature feature (see rabbit-feature SKILL.md).
"""
import json
import os
import subprocess
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = subprocess.run(
    ["git", "-C", SCRIPT_DIR, "rev-parse", "--show-toplevel"],
    capture_output=True, text=True, check=True,
).stdout.strip()
CAGE = os.path.join(REPO_ROOT, ".claude/features/rabbit-cage")

fail_n = 0


def ok(msg):
    print(f"  PASS: {msg}")


def bad(msg):
    global fail_n
    print(f"  FAIL: {msg}")
    fail_n += 1


print("test-RABBIT-CAGE-BACKLOG-24-validate-all-removed")
print()

# [1] script file is absent
print("[1] scripts/validate-all.py is absent")
if not os.path.exists(os.path.join(CAGE, "scripts", "validate-all.py")):
    ok("scripts/validate-all.py does not exist")
else:
    bad("scripts/validate-all.py still exists; BACKLOG-24 not applied")

# [2] spec.md Inv 40 does not list validate-all.py in the live `scripts/`
# enumeration. Narrative mention (e.g. "The legacy `validate-all.py` script
# was removed in RABBIT-CAGE-BACKLOG-24") is permitted; only the live
# enumeration MUST omit the script.
print("[2] docs/spec/spec.md Inv 40 live enumeration omits validate-all.py")
with open(os.path.join(CAGE, "docs/spec/spec.md")) as f:
    spec_text = f.read()
inv40_lines = [ln for ln in spec_text.splitlines()
               if "Python runtime scripts in rabbit-cage are" in ln]
if not inv40_lines:
    bad("spec.md missing Inv 40 enumeration sentence")
else:
    inv40 = inv40_lines[0]
    # Slice the live enumeration: everything between "in `scripts/`" and the
    # next ". " (sentence terminator). The removal note follows after.
    marker = "in `scripts/`"
    idx = inv40.find(marker)
    if idx == -1:
        bad("Inv 40 enumeration missing `scripts/` marker")
    else:
        tail = inv40[idx + len(marker):]
        terminator = tail.find(". ")
        live_enum = tail[:terminator] if terminator != -1 else tail
        if "`validate-all.py`" in live_enum:
            bad("Inv 40 live enumeration still lists `validate-all.py`")
        else:
            ok("Inv 40 live enumeration does not list validate-all.py")

# [3] contract.md provides.scripts has no validate-all.py entry
print("[3] contract.md provides.scripts omits validate-all.py")
with open(os.path.join(CAGE, "docs/spec/contract.md")) as f:
    contract_text = f.read()
# extract the first JSON block fenced by ```json ... ```
start = contract_text.find("```json")
end = contract_text.find("```", start + len("```json"))
if start == -1 or end == -1:
    bad("contract.md missing ```json``` fenced block")
else:
    body = contract_text[start + len("```json"):end].strip()
    try:
        data = json.loads(body)
    except Exception as e:
        bad(f"contract.md JSON unparseable: {e}")
    else:
        scripts = data.get("provides", {}).get("scripts", [])
        bad_entries = [s for s in scripts if "validate-all.py" in s.get("path", "")]
        if bad_entries:
            bad(f"contract.md provides.scripts still lists validate-all.py: {bad_entries}")
        else:
            ok("contract.md provides.scripts omits validate-all.py")

# [4] README.md does not advertise validate-all.py
print("[4] README.md omits validate-all.py")
readme = os.path.join(CAGE, "README.md")
if os.path.exists(readme):
    with open(readme) as f:
        readme_text = f.read()
    if "validate-all.py" in readme_text:
        bad("README.md still mentions validate-all.py")
    else:
        ok("README.md does not mention validate-all.py")
else:
    ok("README.md not present (vacuously satisfied)")

# [5] no other non-test source under rabbit-cage references validate-all.py
print("[5] no non-test rabbit-cage source references validate-all.py")
offending = []
for root, dirs, files in os.walk(CAGE):
    # skip test/ subtree and __pycache__
    rel = os.path.relpath(root, CAGE)
    if rel == "test" or rel.startswith("test" + os.sep) or "__pycache__" in rel:
        continue
    for fname in files:
        path = os.path.join(root, fname)
        # skip spec/contract (already validated structurally above)
        if path.endswith(("docs/spec/spec.md", "docs/spec/contract.md", "README.md")):
            continue
        try:
            with open(path, encoding="utf-8") as fp:
                contents = fp.read()
        except (UnicodeDecodeError, OSError):
            continue
        if "validate-all.py" in contents or "validate_all" in contents:
            offending.append(os.path.relpath(path, REPO_ROOT))
if offending:
    bad(f"non-test rabbit-cage sources still reference validate-all: {offending}")
else:
    ok("no non-test rabbit-cage source references validate-all.py")

print()
if fail_n:
    print(f"FAIL: {fail_n} check(s) failed")
    sys.exit(1)
print("PASS")
