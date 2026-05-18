#!/usr/bin/env python3
"""Tests /rabbit-config permission subcommands (allowed-tools, bash-allow)."""
import json
import os
import shutil
import subprocess
import sys
import tempfile

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = subprocess.run(
    ["git", "-C", SCRIPT_DIR, "rev-parse", "--show-toplevel"],
    capture_output=True, text=True, check=True,
).stdout.strip()
COMMANDS_DIR = os.path.join(REPO_ROOT, ".claude/features/rabbit-cage/commands")
CONFIG_MD = os.path.join(COMMANDS_DIR, "rabbit-config.md")
# Inv 25 (updated): logic lives in the extracted script, not inline in CONFIG_MD.
CONFIG_PY = os.path.join(REPO_ROOT, ".claude/features/rabbit-cage/skills/rabbit-config/scripts/rabbit-config.py")

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


def run_config(argstr, wd):
    """Invoke the extracted script directly, splitting argstr into argv."""
    args = argstr.split() if argstr else []
    res = subprocess.run([sys.executable, CONFIG_PY] + args, cwd=wd,
                         capture_output=True, text=True)
    return res.returncode, res.stdout, res.stderr


def setup_workspace():
    wd = tempfile.mkdtemp()
    os.makedirs(os.path.join(wd, ".claude"), exist_ok=True)
    # settings.json is the build-managed copy of features/rabbit-cage/settings.json;
    # permission subcommands must NOT touch it. Pre-populate with a sentinel to
    # detect any accidental writes.
    with open(os.path.join(wd, ".claude/settings.json"), "w") as f:
        f.write('{"sentinel": "DO-NOT-TOUCH"}')
    return wd


def read_perm_allow(wd):
    p = os.path.join(wd, ".claude/settings.local.json")
    if not os.path.isfile(p):
        return "[]"
    with open(p) as f:
        d = json.load(f)
    return json.dumps(d.get("permissions", {}).get("allow", []))


def read_settings_json(wd):
    p = os.path.join(wd, ".claude/settings.json")
    if not os.path.isfile(p):
        return None
    with open(p) as f:
        return f.read()


print("test-rabbit-config-permissions.py")

# t1
wd = setup_workspace()
rc, out, err = run_config("allowed-tools add WebFetch", wd)
allow = read_perm_allow(wd)
if rc == 0 and allow == '["WebFetch"]':
    ok(1, "allowed-tools add WebFetch creates permissions.allow with WebFetch")
else:
    fail_t(1, f"allowed-tools add failed (rc={rc}, allow={allow}, out={out}{err})")
shutil.rmtree(wd, ignore_errors=True)

# t2
wd = setup_workspace()
run_config("allowed-tools add WebFetch", wd)
run_config("allowed-tools add WebFetch", wd)
allow = read_perm_allow(wd)
if allow == '["WebFetch"]':
    ok(2, "allowed-tools add is idempotent (no duplicate WebFetch)")
else:
    fail_t(2, f"allowed-tools add not idempotent (allow={allow})")
shutil.rmtree(wd, ignore_errors=True)

# t3
wd = setup_workspace()
run_config("allowed-tools add Edit", wd)
run_config("allowed-tools add Write", wd)
run_config("allowed-tools remove Edit", wd)
allow = read_perm_allow(wd)
if allow == '["Write"]':
    ok(3, "allowed-tools remove Edit leaves only Write")
else:
    fail_t(3, f"allowed-tools remove failed (allow={allow})")
shutil.rmtree(wd, ignore_errors=True)

# t4
wd = setup_workspace()
rc, _, _ = run_config("allowed-tools remove DoesNotExist", wd)
allow = read_perm_allow(wd)
if rc == 0 and allow == "[]":
    ok(4, "allowed-tools remove of absent entry is no-op")
else:
    fail_t(4, f"allowed-tools remove of absent entry failed (rc={rc}, allow={allow})")
shutil.rmtree(wd, ignore_errors=True)

# t5
wd = setup_workspace()
run_config("allowed-tools add Edit", wd)
run_config("allowed-tools add Write", wd)
_, list5, _ = run_config("allowed-tools", wd)
lines = list5.splitlines()
if "Edit" in lines and "Write" in lines:
    ok(5, "allowed-tools (no action) lists entries one per line")
else:
    fail_t(5, f"allowed-tools list missing entries (got: {list5})")
shutil.rmtree(wd, ignore_errors=True)

# t6
wd = setup_workspace()
rc, out, err = run_config("bash-allow add touch", wd)
allow = read_perm_allow(wd)
if rc == 0 and allow == '["Bash(touch:*)"]':
    ok(6, "bash-allow add touch writes Bash(touch:*) to permissions.allow")
else:
    fail_t(6, f"bash-allow add failed (rc={rc}, allow={allow}, out={out}{err})")
shutil.rmtree(wd, ignore_errors=True)

# t7
wd = setup_workspace()
run_config("bash-allow add cat", wd)
run_config("bash-allow add cat", wd)
allow = read_perm_allow(wd)
if allow == '["Bash(cat:*)"]':
    ok(7, "bash-allow add is idempotent")
else:
    fail_t(7, f"bash-allow add not idempotent (allow={allow})")
shutil.rmtree(wd, ignore_errors=True)

# t8
wd = setup_workspace()
run_config("bash-allow add touch", wd)
run_config("bash-allow add cat", wd)
run_config("bash-allow remove touch", wd)
allow = read_perm_allow(wd)
if allow == '["Bash(cat:*)"]':
    ok(8, "bash-allow remove touch leaves only Bash(cat:*)")
else:
    fail_t(8, f"bash-allow remove failed (allow={allow})")
shutil.rmtree(wd, ignore_errors=True)

# t9
wd = setup_workspace()
for c in ("touch", "echo", "ls", "python"):
    run_config(f"bash-allow add {c}", wd)
_, list9, _ = run_config("bash-allow", wd)
lines = list9.splitlines()
miss = [c for c in ("touch", "echo", "ls", "python") if c not in lines]
if not miss:
    ok(9, "bash-allow (no action) lists touch/echo/ls/python")
else:
    fail_t(9, f"bash-allow list missing: {' '.join(miss)} (got: {list9})")
shutil.rmtree(wd, ignore_errors=True)

# t10
wd = setup_workspace()
rc, _, _ = run_config("bash-allow add bad(name", wd)
allow = read_perm_allow(wd)
if rc != 0 and allow == "[]":
    ok(10, "bash-allow add rejects command containing parens")
else:
    fail_t(10, f"bash-allow add accepted invalid command (rc={rc}, allow={allow})")
shutil.rmtree(wd, ignore_errors=True)

# t11
wd = setup_workspace()
rc, _, _ = run_config("allowed-tools add Bash(touch:*)", wd)
allow = read_perm_allow(wd)
if rc != 0 and allow == "[]":
    ok(11, "allowed-tools add rejects Bash(...) inputs")
else:
    fail_t(11, f"allowed-tools add accepted Bash(...) input (rc={rc}, allow={allow})")
shutil.rmtree(wd, ignore_errors=True)

# t12
wd = setup_workspace()
rc, _, _ = run_config("allowed-tools whatever Foo", wd)
allow = read_perm_allow(wd)
if rc != 0 and allow == "[]":
    ok(12, "allowed-tools rejects unknown action")
else:
    fail_t(12, f"allowed-tools accepted unknown action (rc={rc}, allow={allow})")
shutil.rmtree(wd, ignore_errors=True)

# t13: target file is settings.local.json (Inv 50)
wd = setup_workspace()
run_config("bash-allow add touch", wd)
local_present = os.path.isfile(os.path.join(wd, ".claude/settings.local.json"))
settings_unchanged = read_settings_json(wd) == '{"sentinel": "DO-NOT-TOUCH"}'
if local_present and settings_unchanged:
    ok(13, "permission subcommands write to settings.local.json, never to settings.json")
else:
    fail_t(13, f"wrong target file (local_present={local_present}, settings_unchanged={settings_unchanged})")
shutil.rmtree(wd, ignore_errors=True)

# t14
spec_md = os.path.join(REPO_ROOT, ".claude/features/rabbit-cage/docs/spec/spec.md")
with open(spec_md) as f:
    spec_content = f.read()
if "allowed-tools" in spec_content and "bash-allow" in spec_content:
    ok(14, "spec.md declares allowed-tools and bash-allow subcommands")
else:
    fail_t(14, "spec.md missing allowed-tools and/or bash-allow declaration")

# t15
contract_md = os.path.join(REPO_ROOT, ".claude/features/rabbit-cage/docs/spec/contract.md")
with open(contract_md) as f:
    contract_content = f.read()
if "allowed-tools" in contract_content and "bash-allow" in contract_content:
    ok(15, "contract.md subcommands list includes allowed-tools and bash-allow")
else:
    fail_t(15, "contract.md missing allowed-tools and/or bash-allow in subcommands list")

# t16
wd = setup_workspace()
rc, _, _ = run_config("bash-allow add", wd)
allow = read_perm_allow(wd)
if rc != 0 and allow == "[]":
    ok(16, "bash-allow add with no value rejected")
else:
    fail_t(16, f"bash-allow add with no value accepted (rc={rc}, allow={allow})")
shutil.rmtree(wd, ignore_errors=True)

# t17: allowed-tools add also writes to settings.local.json, not settings.json (Inv 43)
wd = setup_workspace()
run_config("allowed-tools add WebFetch", wd)
local_present = os.path.isfile(os.path.join(wd, ".claude/settings.local.json"))
settings_unchanged = read_settings_json(wd) == '{"sentinel": "DO-NOT-TOUCH"}'
if local_present and settings_unchanged:
    ok(17, "allowed-tools add writes to settings.local.json, leaves settings.json untouched")
else:
    fail_t(17, f"allowed-tools wrong target (local_present={local_present}, settings_unchanged={settings_unchanged})")
shutil.rmtree(wd, ignore_errors=True)

# t18: list operations read from settings.local.json only (Inv 47)
wd = setup_workspace()
# Seed settings.json with permissions that MUST NOT appear in the list output.
with open(os.path.join(wd, ".claude/settings.json"), "w") as f:
    f.write('{"permissions": {"allow": ["GhostTool", "Bash(ghost:*)"]}}')
_, list_at, _ = run_config("allowed-tools", wd)
_, list_ba, _ = run_config("bash-allow", wd)
if "GhostTool" not in list_at.splitlines() and "ghost" not in list_ba.splitlines():
    ok(18, "list operations do not read permissions from settings.json")
else:
    fail_t(18, f"list operations leaked from settings.json (allowed-tools={list_at!r}, bash-allow={list_ba!r})")
shutil.rmtree(wd, ignore_errors=True)

# t19: confirmation strings reference settings.local.json (Common rules: Output)
# BUG-70: tightened to assert the literal ' to .claude/settings.local.json' phrase
# rather than the weaker "settings.local.json present + .claude/settings.json absent" pair.
# The tighter form guards against future rewordings that drop the path prefix.
wd = setup_workspace()
_, out_at, _ = run_config("allowed-tools add WebFetch", wd)
_, out_ba, _ = run_config("bash-allow add touch", wd)
needle = " to .claude/settings.local.json"
if needle in out_at and needle in out_ba:
    ok(19, "add confirmation strings include literal ' to .claude/settings.local.json'")
else:
    fail_t(19, f"confirmation strings missing '{needle}' (allowed-tools out={out_at!r}, bash-allow out={out_ba!r})")
shutil.rmtree(wd, ignore_errors=True)

# t20: USAGE text (now in CONFIG_PY; CONFIG_MD is a shim per Inv 25) references
# settings.local.json for allowed-tools and bash-allow (Inv 50 prose).
with open(CONFIG_PY) as f:
    py = f.read()
# Strict: the literal phrase 'permissions.allow in settings.json' is the bug fingerprint
# and must not appear (would mean the USAGE text still names the wrong file).
if "permissions.allow in settings.json" not in py and "permissions.allow in settings.local.json" in py:
    ok(20, "USAGE text references settings.local.json (not settings.json) for permission subcommands")
else:
    fail_t(20, "USAGE text still mentions 'permissions.allow in settings.json' or omits 'settings.local.json'")

print()
print(f"Results: {pass_n} passed, {fail_n} failed")
sys.exit(0 if fail_n == 0 else 1)
