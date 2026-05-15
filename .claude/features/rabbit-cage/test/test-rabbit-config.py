#!/usr/bin/env python3
"""Tests /rabbit-config command (replaces /rabbit-set-threshold)."""
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


print("test-rabbit-config.py")

cfg_md = os.path.join(COMMANDS_DIR, "rabbit-config.md")

# t1
if os.path.isfile(cfg_md):
    ok(1, "rabbit-config.md exists in commands/")
else:
    fail_t(1, "rabbit-config.md does NOT exist in commands/ (must be created)")

# t2
if not os.path.isfile(os.path.join(COMMANDS_DIR, "rabbit-set-threshold.md")):
    ok(2, "rabbit-set-threshold.md does not exist in commands/ (old command removed)")
else:
    fail_t(2, "rabbit-set-threshold.md still exists in commands/ (must be removed)")

# t3
if os.path.isfile(cfg_md):
    with open(cfg_md) as f:
        cfg_content = f.read()
    if "prompt-threshold" in cfg_content:
        ok(3, "rabbit-config.md mentions prompt-threshold subcommand")
    else:
        fail_t(3, "rabbit-config.md does not mention prompt-threshold subcommand")
else:
    fail_t(3, "rabbit-config.md does not mention prompt-threshold subcommand")

# t4
feature_json = os.path.join(REPO_ROOT, ".claude/features/rabbit-cage/feature.json")
if os.path.isfile(feature_json):
    try:
        with open(feature_json) as f:
            d = json.load(f)
        cmds = d.get("surface", {}).get("commands", [])
        bad = [c for c in cmds if "rabbit-set-threshold" in c]
        if not bad:
            ok(4, "feature.json surface.commands does not include rabbit-set-threshold")
        else:
            fail_t(4, "feature.json surface.commands still includes rabbit-set-threshold entry")
    except Exception:
        fail_t(4, "feature.json could not be parsed")
else:
    fail_t(4, "feature.json not found")

# t5: prompt-threshold 15 -> writes to settings.local.json
tmpdir = tempfile.mkdtemp()
try:
    if os.path.isfile(cfg_md):
        fake_local = os.path.join(tmpdir, "settings.local.json")
        env = {**os.environ, "ARGUMENTS": "prompt-threshold 15", "SETTINGS_LOCAL": fake_local}
        script = """
import json, os, pathlib, sys
args = os.environ.get('ARGUMENTS', '').split()
settings_local = os.environ.get('SETTINGS_LOCAL', '.claude/settings.local.json')
if not args or args[0] != 'prompt-threshold':
    print('ERROR: expected prompt-threshold subcommand', file=sys.stderr); sys.exit(1)
val = args[1] if len(args) > 1 else ''
if not val:
    p = pathlib.Path(settings_local)
    if p.exists():
        cfg = json.loads(p.read_text())
        cfg.get('env', {}).pop('RABBIT_REFRESH_EVERY', None)
        if not cfg.get('env'): cfg.pop('env', None)
        p.write_text(json.dumps(cfg, indent=2) + '\\n')
    print('Restored default threshold'); sys.exit(0)
if not val.isdigit() or int(val) < 1:
    print('Error: value must be a positive integer', file=sys.stderr); sys.exit(1)
p = pathlib.Path(settings_local)
cfg = json.loads(p.read_text()) if p.exists() else {}
cfg.setdefault('env', {})['RABBIT_REFRESH_EVERY'] = val
p.write_text(json.dumps(cfg, indent=2) + '\\n')
print('Written to ' + settings_local)
"""
        result = subprocess.run([sys.executable, "-c", script], env=env, capture_output=True, text=True)
        if result.returncode == 0 and os.path.isfile(fake_local):
            with open(fake_local) as f:
                d = json.load(f)
            if d.get("env", {}).get("RABBIT_REFRESH_EVERY") == "15":
                ok(5, "prompt-threshold 15 writes RABBIT_REFRESH_EVERY=15 to settings.local.json")
            else:
                fail_t(5, f"prompt-threshold 15 did not write expected value (got '{d.get('env', {}).get('RABBIT_REFRESH_EVERY')}')")
        else:
            fail_t(5, f"prompt-threshold 15 failed (exit={result.returncode}, output={result.stdout}{result.stderr})")
    else:
        fail_t(5, "cannot test: rabbit-config.md does not exist")

    # t6
    if os.path.isfile(cfg_md):
        fake_local2 = os.path.join(tmpdir, "settings.local.json")
        with open(fake_local2, "w") as f:
            f.write('{"env":{"RABBIT_REFRESH_EVERY":"15"}}\n')
        env = {**os.environ, "ARGUMENTS": "prompt-threshold", "SETTINGS_LOCAL": fake_local2}
        script2 = """
import json, os, pathlib, sys
args = os.environ.get('ARGUMENTS', '').split()
settings_local = os.environ.get('SETTINGS_LOCAL', '.claude/settings.local.json')
if not args or args[0] != 'prompt-threshold':
    print('ERROR: expected prompt-threshold subcommand', file=sys.stderr); sys.exit(1)
val = args[1] if len(args) > 1 else ''
if not val:
    p = pathlib.Path(settings_local)
    if p.exists():
        cfg = json.loads(p.read_text())
        cfg.get('env', {}).pop('RABBIT_REFRESH_EVERY', None)
        if not cfg.get('env'): cfg.pop('env', None)
        p.write_text(json.dumps(cfg, indent=2) + '\\n')
    print('Restored default threshold'); sys.exit(0)
"""
        result2 = subprocess.run([sys.executable, "-c", script2], env=env, capture_output=True, text=True)
        if result2.returncode == 0:
            with open(fake_local2) as f:
                d2 = json.load(f)
            remaining = d2.get("env", {}).get("RABBIT_REFRESH_EVERY", "REMOVED")
            if remaining == "REMOVED":
                ok(6, "prompt-threshold (no value) removes RABBIT_REFRESH_EVERY from settings.local.json")
            else:
                fail_t(6, f"prompt-threshold (no value) did not remove key (value='{remaining}')")
        else:
            fail_t(6, f"prompt-threshold (no value) failed (exit={result2.returncode}, output={result2.stdout}{result2.stderr})")
    else:
        fail_t(6, "cannot test: rabbit-config.md does not exist")
finally:
    shutil.rmtree(tmpdir, ignore_errors=True)

print()
print(f"Results: {pass_n} passed, {fail_n} failed")
sys.exit(0 if fail_n == 0 else 1)
