#!/usr/bin/env python3
"""Tests rabbit-config skill structure + human-approval subcommand (BACKLOG-11).

Spec invariants covered:
- Inv 20 (inverted): commands/rabbit-config.md does NOT exist; must not be recreated.
- Inv 33: SKILL.md exists at skills/rabbit-config/SKILL.md with required frontmatter.
- Inv 34: scripts/rabbit-config.py exists, executable, stdlib only, sole impl (no shim).
- Inv 35: human-approval false writes .rabbit-human-approval-bypass with 'session';
  legacy verbs (bypass, gated, enabled, disabled) are rejected.
- Inv 36: human-approval true deletes the marker; idempotent.
- Inv 37: human-approval (no action) prints 'true' (marker absent, gate active) or
  'false' (marker present, gate bypassed).
- Inv 38: .rabbit-human-approval-bypass is gitignored.
- Inv 39: sync-check.py emits red alert while marker present (not consumed),
  priority level 4 between scope-guard-off and skills-updated.
- Inv 59: feature.json surface.skills MUST be a non-empty array containing
  'rabbit-config'.
"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = subprocess.run(
    ["git", "-C", SCRIPT_DIR, "rev-parse", "--show-toplevel"],
    capture_output=True, text=True, check=True,
).stdout.strip()

SKILL_DIR = os.path.join(REPO_ROOT, ".claude/features/rabbit-cage/skills/rabbit-config")
SKILL_MD = os.path.join(SKILL_DIR, "SKILL.md")
SKILL_PY = os.path.join(SKILL_DIR, "scripts/rabbit-config.py")
CMD_MD = os.path.join(REPO_ROOT, ".claude/features/rabbit-cage/commands/rabbit-config.md")
DEPLOYED_CMD_MD = os.path.join(REPO_ROOT, ".claude/commands/rabbit-config.md")
SYNC_CHECK = os.path.join(REPO_ROOT, ".claude/features/rabbit-cage/hooks/sync-check.py")
GITIGNORE = os.path.join(REPO_ROOT, ".gitignore")
CONTRACT = os.path.join(REPO_ROOT, ".claude/features/contract/build-contract.json")

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


def run_script(args, cwd):
    """Invoke the extracted script directly with argv."""
    return subprocess.run(
        [sys.executable, SKILL_PY] + args,
        cwd=cwd, capture_output=True, text=True,
    )


print("test-BACKLOG-11-rabbit-config-skill.py")

# ---- Structure tests ----

# t1: SKILL.md exists
if os.path.isfile(SKILL_MD):
    ok(1, "SKILL.md exists at skills/rabbit-config/SKILL.md")
else:
    fail_t(1, f"SKILL.md missing at {SKILL_MD}")

# t2: SKILL.md frontmatter declares name and lists all 5 subcommands in description
if os.path.isfile(SKILL_MD):
    with open(SKILL_MD) as f:
        skill_text = f.read()
    fm_match = re.match(r"^---\n(.*?)\n---", skill_text, re.DOTALL)
    if not fm_match:
        fail_t(2, "SKILL.md missing YAML frontmatter")
    else:
        fm = fm_match.group(1)
        name_ok = re.search(r"^name:\s*rabbit-config\s*$", fm, re.MULTILINE) is not None
        desc_match = re.search(r"^description:\s*(.+)$", fm, re.MULTILINE)
        desc = desc_match.group(1) if desc_match else ""
        needed = ["prompt-threshold", "allowed-tools", "bash-allow", "permissions", "human-approval"]
        miss = [s for s in needed if s not in desc]
        if name_ok and not miss:
            ok(2, "SKILL.md frontmatter declares name=rabbit-config and lists all 5 subcommands")
        else:
            fail_t(2, f"SKILL.md frontmatter incomplete (name_ok={name_ok}, missing in description={miss})")
else:
    fail_t(2, "SKILL.md missing — cannot check frontmatter")

# t3: scripts/rabbit-config.py exists and is executable
if os.path.isfile(SKILL_PY) and os.access(SKILL_PY, os.X_OK):
    ok(3, "scripts/rabbit-config.py exists and is executable")
else:
    fail_t(3, f"scripts/rabbit-config.py missing or not executable at {SKILL_PY}")

# t4: commands/rabbit-config.md does NOT exist (Inv 20 inverted); deployed
# .claude/commands/rabbit-config.md does NOT exist either (symlink propagation).
src_absent = not os.path.lexists(CMD_MD)
deployed_absent = not os.path.lexists(DEPLOYED_CMD_MD)
if src_absent and deployed_absent:
    ok(4, "commands/rabbit-config.md does not exist (source and deployed)")
else:
    fail_t(
        4,
        f"commands/rabbit-config.md must not exist "
        f"(source_absent={src_absent}, deployed_absent={deployed_absent})",
    )

# t5: .gitignore contains .rabbit-human-approval-bypass
if os.path.isfile(GITIGNORE):
    with open(GITIGNORE) as f:
        gi = f.read()
    if any(line.strip() == ".rabbit-human-approval-bypass" for line in gi.splitlines()):
        ok(5, ".rabbit-human-approval-bypass is gitignored")
    else:
        fail_t(5, ".rabbit-human-approval-bypass NOT present in .gitignore")
else:
    fail_t(5, ".gitignore missing")

# t6: build-contract.json registers the new SKILL.md as a copy-file target
if os.path.isfile(CONTRACT):
    with open(CONTRACT) as f:
        contract = json.load(f)
    src = ".claude/features/rabbit-cage/skills/rabbit-config/SKILL.md"
    dst = ".claude/skills/rabbit-config/SKILL.md"
    has_target = any(
        t.get("type") == "copy-file"
        and t.get("source") == src
        and t.get("destination") == dst
        for t in contract.get("targets", [])
    )
    if has_target:
        ok(6, "build-contract.json registers skills/rabbit-config/SKILL.md as copy-file target")
    else:
        fail_t(6, "build-contract.json missing copy-file target for skills/rabbit-config/SKILL.md")
else:
    fail_t(6, "build-contract.json missing")

# ---- Existing subcommands still work via the extracted script ----

if os.path.isfile(SKILL_PY):
    # t7: prompt-threshold 15 writes via the extracted script
    wd = tempfile.mkdtemp()
    try:
        os.makedirs(os.path.join(wd, ".claude"), exist_ok=True)
        res = run_script(["prompt-threshold", "15"], wd)
        local_path = os.path.join(wd, ".claude/settings.local.json")
        if res.returncode == 0 and os.path.isfile(local_path):
            with open(local_path) as f:
                d = json.load(f)
            if d.get("env", {}).get("RABBIT_REFRESH_EVERY") == "15":
                ok(7, "extracted script handles prompt-threshold 15")
            else:
                fail_t(7, f"prompt-threshold 15 wrote wrong value: {d}")
        else:
            fail_t(7, f"prompt-threshold 15 failed: rc={res.returncode} stderr={res.stderr}")
    finally:
        shutil.rmtree(wd, ignore_errors=True)

    # t8: allowed-tools add WebFetch via the extracted script
    wd = tempfile.mkdtemp()
    try:
        os.makedirs(os.path.join(wd, ".claude"), exist_ok=True)
        res = run_script(["allowed-tools", "add", "WebFetch"], wd)
        local_path = os.path.join(wd, ".claude/settings.local.json")
        if res.returncode == 0 and os.path.isfile(local_path):
            with open(local_path) as f:
                d = json.load(f)
            allow = d.get("permissions", {}).get("allow", [])
            if allow == ["WebFetch"]:
                ok(8, "extracted script handles allowed-tools add")
            else:
                fail_t(8, f"allowed-tools add wrote wrong value: {allow}")
        else:
            fail_t(8, f"allowed-tools add failed: rc={res.returncode} stderr={res.stderr}")
    finally:
        shutil.rmtree(wd, ignore_errors=True)

    # t9: bash-allow add touch via the extracted script
    wd = tempfile.mkdtemp()
    try:
        os.makedirs(os.path.join(wd, ".claude"), exist_ok=True)
        res = run_script(["bash-allow", "add", "touch"], wd)
        local_path = os.path.join(wd, ".claude/settings.local.json")
        if res.returncode == 0 and os.path.isfile(local_path):
            with open(local_path) as f:
                d = json.load(f)
            allow = d.get("permissions", {}).get("allow", [])
            if allow == ["Bash(touch:*)"]:
                ok(9, "extracted script handles bash-allow add")
            else:
                fail_t(9, f"bash-allow add wrote wrong value: {allow}")
        else:
            fail_t(9, f"bash-allow add failed: rc={res.returncode} stderr={res.stderr}")
    finally:
        shutil.rmtree(wd, ignore_errors=True)

    # ---- human-approval subcommand (true/false vocabulary, Inv 35–57) ----

    # t10: 'false' writes marker with 'session' content (Inv 35)
    wd = tempfile.mkdtemp()
    try:
        res = run_script(["human-approval", "false"], wd)
        marker = os.path.join(wd, ".rabbit-human-approval-bypass")
        if res.returncode == 0 and os.path.isfile(marker):
            with open(marker) as f:
                content = f.read()
            if content == "session":
                ok(10, "human-approval false writes marker with 'session' content")
            else:
                fail_t(10, f"marker content wrong: {content!r}")
        else:
            fail_t(10, f"'false' failed: rc={res.returncode} marker_exists={os.path.isfile(marker)} stderr={res.stderr}")
    finally:
        shutil.rmtree(wd, ignore_errors=True)

    # t11: (no action) prints 'false' when marker present (Inv 37: bypass = false)
    wd = tempfile.mkdtemp()
    try:
        marker = os.path.join(wd, ".rabbit-human-approval-bypass")
        with open(marker, "w") as f:
            f.write("session")
        res = run_script(["human-approval"], wd)
        if res.returncode == 0 and res.stdout.strip() == "false":
            ok(11, "human-approval (no action) prints 'false' when marker present (gate bypassed)")
        else:
            fail_t(11, f"expected 'false', got rc={res.returncode} stdout={res.stdout!r}")
    finally:
        shutil.rmtree(wd, ignore_errors=True)

    # t12: (no action) prints 'true' when marker absent (Inv 37: gate active = true)
    wd = tempfile.mkdtemp()
    try:
        res = run_script(["human-approval"], wd)
        if res.returncode == 0 and res.stdout.strip() == "true":
            ok(12, "human-approval (no action) prints 'true' when marker absent (gate active)")
        else:
            fail_t(12, f"expected 'true', got rc={res.returncode} stdout={res.stdout!r}")
    finally:
        shutil.rmtree(wd, ignore_errors=True)

    # t13: 'true' removes marker (Inv 36)
    wd = tempfile.mkdtemp()
    try:
        marker = os.path.join(wd, ".rabbit-human-approval-bypass")
        with open(marker, "w") as f:
            f.write("session")
        res = run_script(["human-approval", "true"], wd)
        if res.returncode == 0 and not os.path.isfile(marker):
            ok(13, "human-approval true removes the marker")
        else:
            fail_t(13, f"'true' did not remove marker: rc={res.returncode} marker_exists={os.path.isfile(marker)}")
    finally:
        shutil.rmtree(wd, ignore_errors=True)

    # t14: 'false' is idempotent (re-invoking when marker exists is no-op exit 0)
    wd = tempfile.mkdtemp()
    try:
        run_script(["human-approval", "false"], wd)
        res = run_script(["human-approval", "false"], wd)
        marker = os.path.join(wd, ".rabbit-human-approval-bypass")
        if res.returncode == 0 and os.path.isfile(marker):
            with open(marker) as f:
                content = f.read()
            if content == "session":
                ok(14, "human-approval false is idempotent")
            else:
                fail_t(14, f"idempotent 'false' changed marker content: {content!r}")
        else:
            fail_t(14, f"idempotent 'false' failed: rc={res.returncode}")
    finally:
        shutil.rmtree(wd, ignore_errors=True)

    # t15: 'true' is idempotent (no-op when marker absent, exit 0)
    wd = tempfile.mkdtemp()
    try:
        res = run_script(["human-approval", "true"], wd)
        if res.returncode == 0:
            ok(15, "human-approval true is idempotent (exit 0 when marker absent)")
        else:
            fail_t(15, f"'true' on absent marker failed: rc={res.returncode} stderr={res.stderr}")
    finally:
        shutil.rmtree(wd, ignore_errors=True)

    # t16: unknown action exits 1
    wd = tempfile.mkdtemp()
    try:
        res = run_script(["human-approval", "what"], wd)
        if res.returncode != 0:
            ok(16, "human-approval with unknown action exits non-zero")
        else:
            fail_t(16, f"unknown action did not fail: rc={res.returncode} stdout={res.stdout!r}")
    finally:
        shutil.rmtree(wd, ignore_errors=True)

    # ---- Legacy verbs rejected (Inv 35, 36: only true/false accepted) ----

    # t16a: legacy 'bypass' verb is rejected with exit 1
    wd = tempfile.mkdtemp()
    try:
        res = run_script(["human-approval", "bypass"], wd)
        marker = os.path.join(wd, ".rabbit-human-approval-bypass")
        if res.returncode != 0 and not os.path.isfile(marker):
            ok("16a", "legacy 'bypass' verb rejected (exit non-zero, marker NOT written)")
        else:
            fail_t("16a", f"legacy 'bypass' not rejected: rc={res.returncode} marker_exists={os.path.isfile(marker)}")
    finally:
        shutil.rmtree(wd, ignore_errors=True)

    # t16b: legacy 'gated' verb is rejected with exit 1
    wd = tempfile.mkdtemp()
    try:
        marker = os.path.join(wd, ".rabbit-human-approval-bypass")
        with open(marker, "w") as f:
            f.write("session")
        res = run_script(["human-approval", "gated"], wd)
        if res.returncode != 0 and os.path.isfile(marker):
            ok("16b", "legacy 'gated' verb rejected (exit non-zero, marker NOT removed)")
        else:
            fail_t("16b", f"legacy 'gated' not rejected: rc={res.returncode} marker_exists={os.path.isfile(marker)}")
    finally:
        shutil.rmtree(wd, ignore_errors=True)

    # t16c: 'enabled' (plausible alternative) is rejected with exit 1
    wd = tempfile.mkdtemp()
    try:
        res = run_script(["human-approval", "enabled"], wd)
        marker = os.path.join(wd, ".rabbit-human-approval-bypass")
        if res.returncode != 0 and not os.path.isfile(marker):
            ok("16c", "'enabled' verb rejected (only true/false accepted)")
        else:
            fail_t("16c", f"'enabled' not rejected: rc={res.returncode}")
    finally:
        shutil.rmtree(wd, ignore_errors=True)

    # t16d: 'disabled' (plausible alternative) is rejected with exit 1
    wd = tempfile.mkdtemp()
    try:
        res = run_script(["human-approval", "disabled"], wd)
        marker = os.path.join(wd, ".rabbit-human-approval-bypass")
        if res.returncode != 0 and not os.path.isfile(marker):
            ok("16d", "'disabled' verb rejected (only true/false accepted)")
        else:
            fail_t("16d", f"'disabled' not rejected: rc={res.returncode}")
    finally:
        shutil.rmtree(wd, ignore_errors=True)
else:
    for t in range(7, 17):
        fail_t(t, "scripts/rabbit-config.py missing — cannot exercise subcommand")

# ---- sync-check.py alert ----

# t17: sync-check.py emits red [rabbit] HUMAN APPROVAL BYPASS ACTIVE alert while marker present
# Build a clean minimal repo (mirrors test-RABBIT-CAGE-BACKLOG14 setup).
def make_clean_repo():
    d = tempfile.mkdtemp()
    subprocess.run(["git", "init", "-q", d], check=True)
    subprocess.run(["git", "-C", d, "config", "user.email", "t@t.t"], check=True)
    subprocess.run(["git", "-C", d, "config", "user.name", "T"], check=True)
    subprocess.run(["git", "-C", d, "checkout", "-q", "-b", "main"], capture_output=True)
    os.makedirs(os.path.join(d, ".claude/features/rabbit-cage/scripts"), exist_ok=True)
    os.makedirs(os.path.join(d, ".claude/features/policy"), exist_ok=True)
    for fname, content in [
        ("philosophy.md", "# Philosophy\n"),
        ("spec-rules.md", "# Spec Rules\n"),
        ("coding-rules.md", "# Coding Rules\n"),
    ]:
        with open(os.path.join(d, ".claude/features/policy", fname), "w") as f:
            f.write(content)
    with open(os.path.join(d, ".claude/features/rabbit-cage/policy-header.json"), "w") as f:
        json.dump({"header": "# Rabbit Workflow — test"}, f)
    for fname in ("generate-claude-md.py", "generate-claude-md-header.py"):
        shutil.copy(
            os.path.join(REPO_ROOT, ".claude/features/rabbit-cage/scripts", fname),
            os.path.join(d, ".claude/features/rabbit-cage/scripts", fname),
        )
    with open(os.path.join(d, ".claude/features/registry.json"), "w") as f:
        json.dump({"schema_version": "1.0.0", "features": {}}, f)
    env = {**os.environ, "RABBIT_ROOT": d}
    res = subprocess.run(
        [sys.executable, os.path.join(d, ".claude/features/rabbit-cage/scripts/generate-claude-md.py")],
        env=env, capture_output=True, text=True,
    )
    with open(os.path.join(d, "CLAUDE.md"), "w") as f:
        f.write(res.stdout.rstrip("\n") + "\n")
    subprocess.run(["git", "-C", d, "add", "-A"], check=True, capture_output=True)
    subprocess.run(["git", "-C", d, "commit", "-q", "-m", "init"], check=True, capture_output=True)
    return d


def run_sync(tmproot):
    env = {**os.environ, "RABBIT_ROOT": tmproot, "RABBIT_SYNC_EVERY": "1"}
    return subprocess.run(
        [sys.executable, SYNC_CHECK], env=env, capture_output=True, text=True,
    ).stdout


def extract_msg(output):
    try:
        return json.loads(output).get("systemMessage", "")
    except Exception:
        return ""


tmproots = []
try:
    # t17: marker present → human-approval alert emitted
    tmproot = make_clean_repo()
    tmproots.append(tmproot)
    open(os.path.join(tmproot, ".rabbit-human-approval-bypass"), "w").close()
    out = run_sync(tmproot)
    msg = extract_msg(out)
    if "HUMAN APPROVAL BYPASS ACTIVE" in msg and "\x1b[31m" in msg:
        ok(17, "sync-check.py emits red [rabbit] HUMAN APPROVAL BYPASS ACTIVE alert while marker present")
    else:
        fail_t(17, f"alert missing or not red: {msg!r}")

    # t18: marker is NOT consumed (persists after sync-check)
    marker = os.path.join(tmproot, ".rabbit-human-approval-bypass")
    if os.path.isfile(marker):
        ok(18, "human-approval-bypass marker NOT consumed by sync-check.py")
    else:
        fail_t(18, "human-approval-bypass marker was consumed (must persist)")

    # t19: human-approval-bypass + skills-updated BOTH emit, human-approval first
    # (BACKLOG-18: Inv 83 aggregation — no suppression; priority controls ordering)
    tmproot = make_clean_repo()
    tmproots.append(tmproot)
    open(os.path.join(tmproot, ".rabbit-human-approval-bypass"), "w").close()
    open(os.path.join(tmproot, ".rabbit-skills-updated"), "w").close()
    out = run_sync(tmproot)
    msg = extract_msg(out)
    idx_ha = msg.find("HUMAN APPROVAL BYPASS ACTIVE")
    idx_sk = msg.find("Skills updated")
    if idx_ha >= 0 and idx_sk >= 0 and idx_ha < idx_sk:
        ok(19, "human-approval and skills-updated both emit; human-approval first (priority 4 < 5)")
    else:
        fail_t(19, f"aggregation/order wrong: ha={idx_ha} sk={idx_sk} msg={msg!r}")

    # t20: scope-guard-off + human-approval-bypass BOTH emit, scope-guard first
    # (BACKLOG-18: Inv 83 aggregation — no suppression)
    tmproot = make_clean_repo()
    tmproots.append(tmproot)
    with open(os.path.join(tmproot, ".rabbit-scope-override"), "w") as f:
        f.write("session")
    open(os.path.join(tmproot, ".rabbit-human-approval-bypass"), "w").close()
    out = run_sync(tmproot)
    msg = extract_msg(out)
    idx_sc = msg.upper().find("SCOPE GUARD")
    idx_ha = msg.find("HUMAN APPROVAL BYPASS ACTIVE")
    if idx_sc >= 0 and idx_ha >= 0 and idx_sc < idx_ha:
        ok(20, "scope-guard and human-approval both emit; scope-guard first (priority 3 < 4)")
    else:
        fail_t(20, f"aggregation/order wrong: sc={idx_sc} ha={idx_ha} msg={msg!r}")

    # t21: feature.json surface.skills declares 'rabbit-config' (Inv 59)
    feature_json = os.path.join(REPO_ROOT, ".claude/features/rabbit-cage/feature.json")
    with open(feature_json) as f:
        feature_data = json.load(f)
    skills = feature_data.get("surface", {}).get("skills", [])
    if isinstance(skills, list) and len(skills) > 0 and "rabbit-config" in skills:
        ok(21, "feature.json surface.skills is non-empty and contains 'rabbit-config' (Inv 59)")
    else:
        fail_t(21, f"surface.skills must be non-empty and contain 'rabbit-config'; got {skills!r}")
finally:
    for d in tmproots:
        shutil.rmtree(d, ignore_errors=True)

print()
print(f"Results: {pass_n} passed, {fail_n} failed")
sys.exit(0 if fail_n == 0 else 1)
