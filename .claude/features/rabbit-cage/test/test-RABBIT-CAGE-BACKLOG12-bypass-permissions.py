#!/usr/bin/env python3
"""Tests for /rabbit-config bypass-permissions subcommand (BACKLOG-12 reopening).

Bypass mode is now a per-user opt-in via the new subcommand; the shared
settings.json source and its build copy MUST NOT declare permissions.defaultMode.

Covers Inv 53 (six subcommands), Inv 69 (rewritten), Inv 71-74.
"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = subprocess.run(
    ["git", "-C", SCRIPT_DIR, "rev-parse", "--show-toplevel"],
    capture_output=True, text=True, check=True,
).stdout.strip()

CONFIG_PY = os.path.join(REPO_ROOT, ".claude/features/rabbit-cage/skills/rabbit-config/scripts/rabbit-config.py")
SETTINGS_SRC = os.path.join(REPO_ROOT, ".claude/features/rabbit-cage/settings.json")
SETTINGS_BUILD = os.path.join(REPO_ROOT, ".claude/settings.json")
SKILL_MD = os.path.join(REPO_ROOT, ".claude/features/rabbit-cage/skills/rabbit-config/SKILL.md")
SPEC_MD = os.path.join(REPO_ROOT, ".claude/features/rabbit-cage/docs/spec/spec.md")
CONTRACT_MD = os.path.join(REPO_ROOT, ".claude/features/rabbit-cage/docs/spec/contract.md")

pass_n = 0
fail_n = 0


def ok(t, msg):
    global pass_n
    print(f"  PASS t{t}: {msg}")
    pass_n += 1


def fail_t(t, msg):
    global fail_n
    print(f"  FAIL t{t}: {msg}")
    fail_n += 1


def read(p):
    with open(p) as f:
        return f.read()


def run_config(argstr, wd):
    args = argstr.split() if argstr else []
    res = subprocess.run([sys.executable, CONFIG_PY] + args, cwd=wd,
                         capture_output=True, text=True)
    return res.returncode, res.stdout, res.stderr


def setup_workspace():
    wd = tempfile.mkdtemp(prefix="cage-bypass-")
    os.makedirs(os.path.join(wd, ".claude"), exist_ok=True)
    # Sentinel detects accidental writes to the shared settings.json (build copy).
    with open(os.path.join(wd, ".claude/settings.json"), "w") as f:
        f.write('{"sentinel": "DO-NOT-TOUCH"}')
    return wd


def read_local(wd):
    p = os.path.join(wd, ".claude/settings.local.json")
    if not os.path.isfile(p):
        return None
    with open(p) as f:
        return json.load(f)


print("test-RABBIT-CAGE-BACKLOG12-bypass-permissions.py")
print()

# ---- t1: settings.json source has no permissions.defaultMode key ----
src_settings = json.loads(read(SETTINGS_SRC))
if "defaultMode" not in src_settings.get("permissions", {}):
    ok(1, "settings.json (source) has no permissions.defaultMode key")
else:
    fail_t(1, "settings.json (source) still declares permissions.defaultMode")

# ---- t2: .claude/settings.json (build copy) has no permissions.defaultMode key ----
build_settings = json.loads(read(SETTINGS_BUILD))
if "defaultMode" not in build_settings.get("permissions", {}):
    ok(2, ".claude/settings.json (build copy) has no permissions.defaultMode key")
else:
    fail_t(2, ".claude/settings.json (build copy) still declares permissions.defaultMode")

# ---- t3: bypass-permissions (no arg) on empty workspace prints 'false', exit 0 ----
wd = setup_workspace()
rc, out, err = run_config("bypass-permissions", wd)
local_exists = os.path.isfile(os.path.join(wd, ".claude/settings.local.json"))
if rc == 0 and out.strip() == "false" and not local_exists:
    ok(3, "bypass-permissions (no arg) on empty workspace prints 'false', exit 0, no write")
else:
    fail_t(3, f"bypass-permissions no-arg unexpected (rc={rc}, out={out!r}, err={err!r}, local_exists={local_exists})")
shutil.rmtree(wd, ignore_errors=True)

# ---- t4: bypass-permissions true writes {permissions:{defaultMode:bypassPermissions}} ----
wd = setup_workspace()
rc, out, err = run_config("bypass-permissions true", wd)
local = read_local(wd)
if rc == 0 and local is not None and local.get("permissions", {}).get("defaultMode") == "bypassPermissions":
    ok(4, "bypass-permissions true writes permissions.defaultMode=bypassPermissions to settings.local.json")
else:
    fail_t(4, f"bypass-permissions true did not write expected key (rc={rc}, local={local}, out={out!r}, err={err!r})")
shutil.rmtree(wd, ignore_errors=True)

# ---- t5: bypass-permissions true is idempotent (second invocation does not rewrite) ----
wd = setup_workspace()
run_config("bypass-permissions true", wd)
local_path = os.path.join(wd, ".claude/settings.local.json")
mtime_before = os.path.getmtime(local_path)
content_before = read(local_path)
time.sleep(0.05)
rc, out, err = run_config("bypass-permissions true", wd)
mtime_after = os.path.getmtime(local_path)
content_after = read(local_path)
if rc == 0 and content_before == content_after and mtime_before == mtime_after:
    ok(5, "bypass-permissions true is idempotent (mtime + content unchanged on repeat invocation)")
else:
    fail_t(5, f"bypass-permissions true rewrote file on repeat (rc={rc}, mtime_eq={mtime_before == mtime_after}, content_eq={content_before == content_after}, out={out!r})")
shutil.rmtree(wd, ignore_errors=True)

# ---- t6: bypass-permissions false removes ONLY defaultMode, leaves other permissions sub-keys intact ----
wd = setup_workspace()
# Seed a settings.local.json that has both defaultMode and other permissions sub-keys.
seed = {
    "permissions": {
        "defaultMode": "bypassPermissions",
        "allow": ["WebFetch", "Bash(touch:*)"],
        "skipDangerousModePermissionPrompt": True,
    }
}
with open(os.path.join(wd, ".claude/settings.local.json"), "w") as f:
    json.dump(seed, f, indent=2)
rc, out, err = run_config("bypass-permissions false", wd)
local = read_local(wd)
perms = local.get("permissions", {}) if local else {}
if (
    rc == 0
    and "defaultMode" not in perms
    and perms.get("allow") == ["WebFetch", "Bash(touch:*)"]
    and perms.get("skipDangerousModePermissionPrompt") is True
):
    ok(6, "bypass-permissions false removes only defaultMode, leaves allow + skipDangerousModePermissionPrompt intact")
else:
    fail_t(6, f"bypass-permissions false did not preserve other permissions sub-keys (rc={rc}, perms={perms}, out={out!r}, err={err!r})")
shutil.rmtree(wd, ignore_errors=True)

# ---- t7: bypass-permissions false when key already absent → no-op, exit 0 ----
wd = setup_workspace()
rc, out, err = run_config("bypass-permissions false", wd)
if rc == 0:
    ok(7, "bypass-permissions false when key absent exits 0 (idempotent no-op)")
else:
    fail_t(7, f"bypass-permissions false on absent key did not exit 0 (rc={rc}, out={out!r}, err={err!r})")
shutil.rmtree(wd, ignore_errors=True)

# ---- t8: bypass-permissions false leaves file as valid JSON when permissions becomes empty ----
wd = setup_workspace()
# Seed: only defaultMode under permissions → after removal, permissions == {} and should also be removed.
seed = {"permissions": {"defaultMode": "bypassPermissions"}}
with open(os.path.join(wd, ".claude/settings.local.json"), "w") as f:
    json.dump(seed, f, indent=2)
rc, out, err = run_config("bypass-permissions false", wd)
local_path = os.path.join(wd, ".claude/settings.local.json")
try:
    with open(local_path) as f:
        loaded = json.load(f)
    valid_json = True
except Exception:
    loaded = None
    valid_json = False
# permissions key should also be removed (became empty).
if rc == 0 and valid_json and "permissions" not in loaded:
    ok(8, "bypass-permissions false leaves valid JSON and removes empty permissions key")
else:
    fail_t(8, f"bypass-permissions false left invalid JSON or kept empty permissions (rc={rc}, valid_json={valid_json}, loaded={loaded}, out={out!r})")
shutil.rmtree(wd, ignore_errors=True)

# ---- t9: bypass-permissions xyz (invalid) → exit non-zero, no file modified ----
wd = setup_workspace()
rc, out, err = run_config("bypass-permissions xyz", wd)
local_exists = os.path.isfile(os.path.join(wd, ".claude/settings.local.json"))
if rc != 0 and not local_exists:
    ok(9, "bypass-permissions xyz exits non-zero and writes no file")
else:
    fail_t(9, f"bypass-permissions xyz did not reject (rc={rc}, local_exists={local_exists}, out={out!r}, err={err!r})")
shutil.rmtree(wd, ignore_errors=True)

# ---- t10: bypass-permissions true writes ONLY to settings.local.json, never to .claude/settings.json ----
wd = setup_workspace()
run_config("bypass-permissions true", wd)
local_present = os.path.isfile(os.path.join(wd, ".claude/settings.local.json"))
settings_content = read(os.path.join(wd, ".claude/settings.json"))
if local_present and settings_content == '{"sentinel": "DO-NOT-TOUCH"}':
    ok(10, "bypass-permissions true writes to settings.local.json, leaves settings.json untouched (sentinel intact)")
else:
    fail_t(10, f"bypass-permissions true wrote wrong target (local_present={local_present}, settings_content={settings_content!r})")
shutil.rmtree(wd, ignore_errors=True)

# ---- t11: SKILL.md body contains literal substring '/rabbit-config bypass-permissions' ----
skill = read(SKILL_MD)
if "/rabbit-config bypass-permissions" in skill:
    ok(11, "SKILL.md body documents '/rabbit-config bypass-permissions'")
else:
    fail_t(11, "SKILL.md body missing '/rabbit-config bypass-permissions'")

# ---- t12: SKILL.md frontmatter description field contains 'bypass-permissions' (Inv 53) ----
# Extract frontmatter block between leading '---' delimiters.
m = re.match(r"^---\n(.*?\n)---\n", skill, re.DOTALL)
if m:
    frontmatter = m.group(1)
    desc_match = re.search(r"^description:\s*(.+?)(?:\n[a-zA-Z_]+:|\Z)", frontmatter, re.DOTALL | re.MULTILINE)
    desc = desc_match.group(1) if desc_match else ""
    if "bypass-permissions" in desc:
        ok(12, "SKILL.md frontmatter description names bypass-permissions (Inv 53)")
    else:
        fail_t(12, f"SKILL.md frontmatter description missing 'bypass-permissions' (desc={desc!r})")
else:
    fail_t(12, "SKILL.md has no YAML frontmatter")

# ---- t13: spec.md asserts shared settings.json MUST NOT declare permissions.defaultMode ----
spec = read(SPEC_MD)
if "MUST NOT declare permissions.defaultMode" in spec or "MUST NOT declare\n    `permissions.defaultMode`" in spec:
    ok(13, "spec.md asserts shared settings.json MUST NOT declare permissions.defaultMode")
else:
    fail_t(13, "spec.md missing prohibition that shared settings.json MUST NOT declare permissions.defaultMode")

# ---- t14: contract.md provides.skills subcommands list contains entry starting with 'bypass-permissions' ----
contract = read(CONTRACT_MD)
# Extract the JSON block (first triple-backtick json block).
jm = re.search(r"```json\n(.*?)\n```", contract, re.DOTALL)
if jm:
    contract_json = json.loads(jm.group(1))
    skills = contract_json.get("provides", {}).get("skills", [])
    subcommands = skills[0].get("subcommands", []) if skills else []
    if any(sc.startswith("bypass-permissions") for sc in subcommands):
        ok(14, "contract.md provides.skills[0].subcommands includes a bypass-permissions entry")
    else:
        fail_t(14, f"contract.md subcommands list missing bypass-permissions entry (got: {subcommands})")
else:
    fail_t(14, "contract.md has no JSON code block")

print()
print(f"Results: {pass_n} passed, {fail_n} failed")
sys.exit(0 if fail_n == 0 else 1)
