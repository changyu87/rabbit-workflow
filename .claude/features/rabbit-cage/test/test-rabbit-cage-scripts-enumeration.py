#!/usr/bin/env python3
"""Inv 92 / RABBIT-CAGE-BACKLOG-25 part 1.

End-to-end completeness test for rabbit-cage Inv 18 script enumeration.

Walks .claude/features/rabbit-cage/hooks/*.py and
.claude/features/rabbit-cage/scripts/*.py on disk and asserts:
  (a) every on-disk Python file is named in the Inv 18 enumeration in
      spec.md;
  (b) every script named in the Inv 18 enumeration exists on disk.

The intent is to prevent silent drift of the kind that previously let
`repo-permissions.py` slip out of the enumeration unnoticed.

Notes:
- Test scope is rabbit-cage's own hooks/ and scripts/. `new-feature.py`
  was moved to rabbit-feature in RABBIT-CAGE-BACKLOG-26 and is therefore
  out-of-scope here.
- `_runtime_flags.py` is a private helper (underscore-prefixed) imported
  by other hooks; it is intentionally excluded from the public
  enumeration. The test follows the same convention.

Version: 1.0.0
Owner: rabbit-workflow team
Deprecation criterion: when Inv 18's enumeration is replaced by an
    auto-generated manifest derived from the on-disk script set.
"""
import os
import re
import subprocess
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = subprocess.run(
    ["git", "-C", SCRIPT_DIR, "rev-parse", "--show-toplevel"],
    capture_output=True, text=True, check=True,
).stdout.strip()

CAGE = os.path.join(REPO_ROOT, ".claude/features/rabbit-cage")
SPEC_MD = os.path.join(CAGE, "docs/spec/spec.md")

failures = 0


def fail(msg):
    global failures
    failures += 1
    print(f"FAIL: {msg}", file=sys.stderr)


def public_py_files(dirpath):
    if not os.path.isdir(dirpath):
        return set()
    out = set()
    for name in os.listdir(dirpath):
        if not name.endswith(".py"):
            continue
        # Private helpers (underscore-prefixed) are intentionally excluded
        # from the public enumeration — they are imported by other hooks,
        # not invoked directly.
        if name.startswith("_"):
            continue
        if os.path.isfile(os.path.join(dirpath, name)):
            out.add(name)
    return out


on_disk_hooks = public_py_files(os.path.join(CAGE, "hooks"))
on_disk_scripts = public_py_files(os.path.join(CAGE, "scripts"))

with open(SPEC_MD) as f:
    spec_text = f.read()

# Pull the Inv 18 paragraph: starts at "18. The Python runtime scripts in rabbit-cage"
# and stops at the next top-level numbered line.
m = re.search(
    r"^18\.\s+The Python runtime scripts in rabbit-cage(.*?)(?=^\d+\.\s)",
    spec_text, re.MULTILINE | re.DOTALL,
)
if not m:
    fail("could not locate Inv 18 paragraph in spec.md")
    print(f"\nResults: {0 if failures == 0 else 'FAIL'} (failures={failures})")
    sys.exit(1 if failures else 0)

inv18 = m.group(1)

# Enumerated names are mentioned as `name.py` (markdown-quoted) in the prose.
enumerated = set(re.findall(r"`([a-zA-Z0-9_-]+\.py)`", inv18))

# (a) every on-disk Python file is named in Inv 18.
hooks_missing_from_inv = on_disk_hooks - enumerated
scripts_missing_from_inv = on_disk_scripts - enumerated
if hooks_missing_from_inv:
    fail(f"hooks/ Python files NOT named in Inv 18 enumeration: {sorted(hooks_missing_from_inv)}")
if scripts_missing_from_inv:
    fail(f"scripts/ Python files NOT named in Inv 18 enumeration: {sorted(scripts_missing_from_inv)}")

# (b) every enumerated script that should live in rabbit-cage actually
# exists on disk. Inv 18 also mentions some out-of-scope scripts in prose
# (e.g. `new-feature.py` for the rabbit-feature note) — we restrict the
# disk check to entries that match a hooks/ or scripts/ file by basename.
on_disk_all = on_disk_hooks | on_disk_scripts
inv_missing_from_disk = []
for name in sorted(enumerated):
    if name in ("new-feature.py",):
        # Explicitly referenced as relocated to rabbit-feature in the same
        # paragraph; not expected on disk in rabbit-cage.
        continue
    if name not in on_disk_all:
        inv_missing_from_disk.append(name)
if inv_missing_from_disk:
    fail(f"Inv 18 enumerates scripts NOT present on disk in rabbit-cage: {inv_missing_from_disk}")

if failures == 0:
    print("PASS: Inv 18 enumeration matches on-disk hooks/ and scripts/")
    print()
    print("ALL TESTS PASSED")
    sys.exit(0)
else:
    print()
    print(f"Results: {failures} failure(s)")
    sys.exit(1)
