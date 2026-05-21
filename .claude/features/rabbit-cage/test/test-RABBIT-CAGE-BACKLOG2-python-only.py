#!/usr/bin/env python3
"""RABBIT-CAGE-BACKLOG-2: Python-only runtime tech stack."""
import glob
import json
import os
import subprocess
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
# BUG-64: derive REPO_ROOT from git rev-parse so the test is resilient to the
# feature directory being moved or symlinked. Hard-coded `../../../..` silently
# computed the wrong root if depth ever changed.
REPO_ROOT = subprocess.run(
    ["git", "-C", SCRIPT_DIR, "rev-parse", "--show-toplevel"],
    capture_output=True, text=True, check=True,
).stdout.strip()
CAGE = os.path.join(REPO_ROOT, ".claude/features/rabbit-cage")

fail_n = 0


def passed(msg):
    print(f"  PASS: {msg}")


def failed(msg):
    global fail_n
    print(f"  FAIL: {msg}")
    fail_n += 1


print("test-RABBIT-CAGE-BACKLOG2-python-only")
print()

# 1. No .sh under hooks/
print("[1] hooks/ contains no .sh files")
sh_in_hooks = sorted(glob.glob(os.path.join(CAGE, "hooks", "*.sh")))
if not sh_in_hooks:
    passed("no .sh files in hooks/")
else:
    failed(f".sh files still present in hooks/: {' '.join(sh_in_hooks)}")

# 2. No .sh under scripts/
print("[2] scripts/ contains no .sh files")
sh_in_scripts = sorted(glob.glob(os.path.join(CAGE, "scripts", "*.sh")))
if not sh_in_scripts:
    passed("no .sh files in scripts/")
else:
    failed(f".sh files still present in scripts/: {' '.join(sh_in_scripts)}")

# 3. install.py
print("[3] install.py present at rabbit-cage root (bootstrap entry point)")
if os.path.isfile(os.path.join(CAGE, "install.py")):
    passed("install.py present (bootstrap entry point)")
else:
    failed(f"install.py missing at {CAGE}/install.py")

# 4. Expected Python runtime scripts
print("[4] Inv 18 Python script set present and executable")
expected_hooks = ["refresh.py", "scope-guard.py", "session-init.py", "sync-check.py"]
expected_scripts = ["build.py", "build-targets.py", "generate-claude-md.py",
                    "generate-claude-md-header.py", "rabbit-project.py",
                    "rabbit-project-consolidate.py", "rabbit-project-map.py",
                    "rabbit-project-set-path.py", "scope-guard-on.py",
                    "workspace-tree.py"]

for f in expected_hooks:
    p = os.path.join(CAGE, "hooks", f)
    if os.access(p, os.X_OK):
        passed(f"executable: hooks/{f}")
    else:
        failed(f"missing or non-executable: hooks/{f}")

for f in expected_scripts:
    p = os.path.join(CAGE, "scripts", f)
    if os.access(p, os.X_OK):
        passed(f"executable: scripts/{f}")
    else:
        failed(f"missing or non-executable: scripts/{f}")

# 5. shebang
print("[5] every runtime .py has python3 shebang")
for d in (os.path.join(CAGE, "hooks"), os.path.join(CAGE, "scripts")):
    for f in sorted(glob.glob(os.path.join(d, "*.py"))):
        try:
            with open(f) as fp:
                first = fp.readline().rstrip("\n")
        except Exception:
            first = ""
        rel = os.path.relpath(f, REPO_ROOT)
        if first == "#!/usr/bin/env python3":
            passed(f"shebang ok: {rel}")
        else:
            failed(f"wrong shebang in {rel}: {first}")

# 6. settings.json
print("[6] settings.json hook commands invoke .py files")
SETTINGS = os.path.join(CAGE, "settings.json")
with open(SETTINGS) as f:
    settings_text = f.read()

import re as _re
sh_matches = _re.findall(r"\.claude/hooks/[^\"']+\.sh", settings_text)
if sh_matches:
    failed("settings.json still references .sh hook paths:")
    for m in sh_matches:
        print(f"    {m}")
else:
    passed("no .sh hook paths in settings.json")

expected_hook_refs = ["session-init.py", "refresh.py", "scope-guard.py", "sync-check.py"]
for h in expected_hook_refs:
    if f".claude/hooks/{h}" in settings_text:
        passed(f"settings.json invokes .claude/hooks/{h}")
    else:
        failed(f"settings.json missing reference to .claude/hooks/{h}")

# 7. build-contract.json
print("[7] build-contract.json copy-file targets reference .py for rabbit-cage hooks")
BC = os.path.join(REPO_ROOT, ".claude/features/contract/build-contract.json")
if os.path.isfile(BC):
    with open(BC) as f:
        bc_text = f.read()
    bad = _re.findall(r'rabbit-cage/(?:hooks|scripts)/[^"]+\.sh', bc_text)
    if not bad:
        passed("no rabbit-cage .sh paths in build-contract.json hooks/scripts copy targets")
    else:
        failed("build-contract.json still references rabbit-cage .sh files:")
        for m in bad:
            print(f"    {m}")
else:
    failed(f"build-contract.json not found at {BC}")

print()
if fail_n == 0:
    print("ALL CHECKS PASSED")
    sys.exit(0)
print(f"FAILED: {fail_n} check(s)")
sys.exit(1)
