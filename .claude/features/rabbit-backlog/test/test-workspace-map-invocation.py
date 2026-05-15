#!/usr/bin/env python3
# test-workspace-map-invocation.py — verify that file-backlog-item.py delegates
# storage path resolution to workspace-map.py (contract) rather than hardcoding
# the path by convention.

import subprocess
import sys
import json
import os
import shutil
import tempfile
from pathlib import Path

REPO_ROOT = Path(subprocess.check_output(
    ["git", "-C", str(Path(__file__).resolve().parent), "rev-parse", "--show-toplevel"],
    text=True
).strip())
FEATURE_DIR = REPO_ROOT / ".claude" / "features" / "rabbit-backlog"
SCRIPTS_DIR = FEATURE_DIR / "scripts"
FILE_BACKLOG = SCRIPTS_DIR / "file-backlog-item.py"
CONTRACT_SCRIPTS = REPO_ROOT / ".claude" / "features" / "contract" / "scripts"
WORKSPACE_MAP = CONTRACT_SCRIPTS / "workspace-map.py"

passed = 0
failed = 0


def ok(label):
    global passed
    print(f"  PASS  {label}")
    passed += 1


def fail_t(label, detail=""):
    global failed
    msg = f"  FAIL  {label}"
    if detail:
        msg += f" -- {detail}"
    print(msg)
    failed += 1


print("=== test-workspace-map-invocation.py: workspace-map.py delegation ===")
print()

# t_wm1: workspace-map.py exists at the declared contract path
if WORKSPACE_MAP.is_file():
    ok(f"t_wm1: workspace-map.py exists at contract path: {WORKSPACE_MAP}")
else:
    fail_t(f"t_wm1: workspace-map.py exists at contract path: {WORKSPACE_MAP}",
           f"file not found: {WORKSPACE_MAP}")

# t_wm2: workspace-map.py is executable
if os.access(WORKSPACE_MAP, os.X_OK):
    ok("t_wm2: workspace-map.py is executable")
else:
    fail_t("t_wm2: workspace-map.py is executable",
           f"not executable (or does not exist): {WORKSPACE_MAP}")

# t_wm3: file-backlog-item.py invokes workspace-map.py when resolving storage path.
#
# Strategy: create an isolated git repo, inject a stub workspace-map.py via PATH
# that records its invocation, run file-backlog-item.py, then assert the stub
# was called.

ISO_REPO = Path(tempfile.mkdtemp())
SENTINEL_FILE = Path(tempfile.mktemp())
STUB_DIR = Path(tempfile.mkdtemp())
tmpdirs = [ISO_REPO, STUB_DIR]

try:
    subprocess.run(["git", "-C", str(ISO_REPO), "init", "--quiet"], check=True)
    subprocess.run(["git", "-C", str(ISO_REPO), "config", "user.email", "test@rabbit"], check=True)
    subprocess.run(["git", "-C", str(ISO_REPO), "config", "user.name", "rabbit-test"], check=True)
    subprocess.run(["git", "-C", str(ISO_REPO), "commit", "--allow-empty", "-m", "init", "--quiet"], check=True)
    # Ensure 'main' branch for branch guard compatibility.
    b = subprocess.check_output(
        ["git", "-C", str(ISO_REPO), "branch", "--show-current"],
        text=True
    ).strip()
    if b != "main":
        subprocess.run(["git", "-C", str(ISO_REPO), "branch", "-m", b, "main"], capture_output=True)

    # Install find-feature.py so file-backlog-item.py can validate the feature.
    FIND_FEATURE_SRC = CONTRACT_SCRIPTS / "find-feature.py"
    ISO_CONTRACT_SCRIPTS = ISO_REPO / ".claude" / "features" / "contract" / "scripts"
    ISO_CONTRACT_SCRIPTS.mkdir(parents=True, exist_ok=True)
    shutil.copy2(FIND_FEATURE_SRC, ISO_CONTRACT_SCRIPTS / "find-feature.py")
    os.chmod(ISO_CONTRACT_SCRIPTS / "find-feature.py", 0o755)

    # Create feature.json for test-feature so find-feature.py can discover it.
    (ISO_REPO / ".claude" / "features" / "test-feature").mkdir(parents=True, exist_ok=True)
    (ISO_REPO / ".claude" / "features" / "test-feature" / "feature.json").write_text(json.dumps(
        {"name": "test-feature", "version": "1.0.0", "owner": "test", "tdd_state": "test-green", "summary": "test"}
    ))

    # Create stub workspace-map.py
    EXPECTED_OUTPUT = str(ISO_REPO / ".claude" / "backlogs" / "test-feature")
    stub_script = f"""#!/usr/bin/env python3
# Stub: record invocation and output the expected backlog path.
import sys
with open("{SENTINEL_FILE}", "w") as f:
    f.write("called\\n")
print("{EXPECTED_OUTPUT}")
"""
    (STUB_DIR / "workspace-map.py").write_text(stub_script)
    os.chmod(STUB_DIR / "workspace-map.py", 0o755)

    # Remove sentinel before test
    if SENTINEL_FILE.exists():
        SENTINEL_FILE.unlink()

    # Copy file-backlog-item.py into ISO_REPO so dirname resolves there.
    ISO_SCRIPTS_DIR = ISO_REPO / "scripts"
    ISO_SCRIPTS_DIR.mkdir(exist_ok=True)
    shutil.copy2(FILE_BACKLOG, ISO_SCRIPTS_DIR / "file-backlog-item.py")
    os.chmod(ISO_SCRIPTS_DIR / "file-backlog-item.py", 0o755)

    if FILE_BACKLOG.is_file() and os.access(FILE_BACKLOG, os.X_OK):
        env = os.environ.copy()
        env["PATH"] = f"{STUB_DIR}:{CONTRACT_SCRIPTS}:{env.get('PATH', '')}"
        env["RABBIT_ROOT"] = str(ISO_REPO)
        subprocess.run(
            [sys.executable, str(ISO_SCRIPTS_DIR / "file-backlog-item.py"),
             "--related-feature", "test-feature",
             "--title", "Workspace map delegation test"],
            capture_output=True,
            text=True,
            cwd=str(ISO_REPO),
            env=env
        )

        if SENTINEL_FILE.exists():
            ok("t_wm3: file-backlog-item.py invokes workspace-map.py for path resolution")
        else:
            fail_t("t_wm3: file-backlog-item.py invokes workspace-map.py for path resolution",
                   "workspace-map.py stub was NOT called — script may hardcode path by convention")
    else:
        fail_t("t_wm3: file-backlog-item.py invokes workspace-map.py for path resolution",
               "file-backlog-item.py not found or not executable")

    # t_wm4: file-backlog-item.py uses the path returned by workspace-map.py,
    # not a hardcoded .claude/backlogs/<feature> path.
    ISO_REPO2 = Path(tempfile.mkdtemp())
    STUB_DIR2 = Path(tempfile.mkdtemp())
    CUSTOM_DIR = ISO_REPO2 / "custom-backlog-store"
    SENTINEL_FILE2 = Path(tempfile.mktemp())
    tmpdirs.extend([ISO_REPO2, STUB_DIR2])

    subprocess.run(["git", "-C", str(ISO_REPO2), "init", "--quiet"], check=True)
    subprocess.run(["git", "-C", str(ISO_REPO2), "config", "user.email", "test@rabbit"], check=True)
    subprocess.run(["git", "-C", str(ISO_REPO2), "config", "user.name", "rabbit-test"], check=True)
    subprocess.run(["git", "-C", str(ISO_REPO2), "commit", "--allow-empty", "-m", "init", "--quiet"], check=True)
    b2 = subprocess.check_output(
        ["git", "-C", str(ISO_REPO2), "branch", "--show-current"],
        text=True
    ).strip()
    if b2 != "main":
        subprocess.run(["git", "-C", str(ISO_REPO2), "branch", "-m", b2, "main"], capture_output=True)

    ISO_CONTRACT_SCRIPTS2 = ISO_REPO2 / ".claude" / "features" / "contract" / "scripts"
    ISO_CONTRACT_SCRIPTS2.mkdir(parents=True, exist_ok=True)
    shutil.copy2(FIND_FEATURE_SRC, ISO_CONTRACT_SCRIPTS2 / "find-feature.py")
    os.chmod(ISO_CONTRACT_SCRIPTS2 / "find-feature.py", 0o755)
    (ISO_REPO2 / ".claude" / "features" / "test-feature").mkdir(parents=True, exist_ok=True)
    (ISO_REPO2 / ".claude" / "features" / "test-feature" / "feature.json").write_text(json.dumps(
        {"name": "test-feature", "version": "1.0.0", "owner": "test", "tdd_state": "test-green", "summary": "test"}
    ))

    stub_script2 = f"""#!/usr/bin/env python3
import sys
with open("{SENTINEL_FILE2}", "w") as f:
    f.write("called\\n")
print("{CUSTOM_DIR}")
"""
    (STUB_DIR2 / "workspace-map.py").write_text(stub_script2)
    os.chmod(STUB_DIR2 / "workspace-map.py", 0o755)

    ISO_SCRIPTS_DIR2 = ISO_REPO2 / "scripts"
    ISO_SCRIPTS_DIR2.mkdir(exist_ok=True)
    shutil.copy2(FILE_BACKLOG, ISO_SCRIPTS_DIR2 / "file-backlog-item.py")
    os.chmod(ISO_SCRIPTS_DIR2 / "file-backlog-item.py", 0o755)

    if FILE_BACKLOG.is_file() and os.access(FILE_BACKLOG, os.X_OK):
        env2 = os.environ.copy()
        env2["PATH"] = f"{STUB_DIR2}:{CONTRACT_SCRIPTS}:{env2.get('PATH', '')}"
        env2["RABBIT_ROOT"] = str(ISO_REPO2)
        subprocess.run(
            [sys.executable, str(ISO_SCRIPTS_DIR2 / "file-backlog-item.py"),
             "--related-feature", "test-feature",
             "--title", "Custom path test"],
            capture_output=True,
            text=True,
            cwd=str(ISO_REPO2),
            env=env2
        )

        # Item must appear in CUSTOM_DIR, not in the conventional .claude/backlogs/ path
        CONVENTIONAL = ISO_REPO2 / ".claude" / "backlogs" / "test-feature"
        custom_items = list(CUSTOM_DIR.rglob("item.json")) if CUSTOM_DIR.exists() else []

        if custom_items and not CONVENTIONAL.is_dir():
            ok("t_wm4: item created at path returned by workspace-map.py (not hardcoded conventional path)")
        elif CONVENTIONAL.is_dir():
            fail_t("t_wm4: item created at path returned by workspace-map.py (not hardcoded conventional path)",
                   f"item was created at conventional path {CONVENTIONAL} — path is hardcoded, not delegated")
        else:
            fail_t("t_wm4: item created at path returned by workspace-map.py (not hardcoded conventional path)",
                   f"item not found at custom path {CUSTOM_DIR} and conventional path {CONVENTIONAL} does not exist either")
    else:
        fail_t("t_wm4: item created at path returned by workspace-map.py (not hardcoded conventional path)",
               "file-backlog-item.py not found or not executable")

finally:
    for d in tmpdirs:
        shutil.rmtree(d, ignore_errors=True)
    for f in [SENTINEL_FILE]:
        if f.exists():
            f.unlink()

print()
print(f"Results: {passed} passed, {failed} failed")
sys.exit(0 if failed == 0 else 1)
