#!/usr/bin/env python3
"""E2E tests for install.py. Run: python3 test/test-install.py"""

import json
import os
import subprocess
import sys
import tempfile

# Resolve repo root the same way the shell version did
REPO_ROOT = os.environ.get(
    "RABBIT_ROOT",
    subprocess.check_output(
        ["git", "-C", os.path.dirname(os.path.abspath(__file__)), "rev-parse", "--show-toplevel"],
        text=True,
    ).strip(),
)
INSTALL = os.path.join(REPO_ROOT, "install.py")

PASS = 0
FAIL = 0


def run(name, fn):
    global PASS, FAIL
    with tempfile.TemporaryDirectory() as tmpdir:
        try:
            result = fn(tmpdir)
            if result:
                print(f"PASS: {name}")
                PASS += 1
            else:
                print(f"FAIL: {name}")
                FAIL += 1
        except Exception as e:
            print(f"FAIL: {name}  ({e})")
            FAIL += 1


def _install(tmpdir, *extra_args, capture=True):
    """Run install.py with tmpdir as the target. Returns CompletedProcess.
    If the script is missing, returns a fake CompletedProcess with returncode=1."""
    cmd = [INSTALL] + list(extra_args) + [tmpdir]
    try:
        return subprocess.run(cmd, capture_output=capture)
    except FileNotFoundError:
        return subprocess.CompletedProcess(cmd, returncode=1, stdout=b"", stderr=b"")


def t1_clean_install(d):
    _install(d)
    # install.py creates .claude/ with settings.json; CLAUDE.md lives in the
    # developer's workspace, not the installed target.
    return (
        os.path.isdir(os.path.join(d, ".claude"))
        and os.path.isfile(os.path.join(d, ".claude", "settings.json"))
    )


def t2_hook_executable(d):
    _install(d)
    hook = os.path.join(d, ".claude", "hooks", "refresh.py")
    return os.path.isfile(hook) and os.access(hook, os.X_OK)


def t3_settings_content(d):
    _install(d)
    settings_path = os.path.join(d, ".claude", "settings.json")
    if not os.path.isfile(settings_path):
        return False
    with open(settings_path) as f:
        data = json.load(f)
    return data["env"]["RABBIT_REFRESH_EVERY"] == "20"


def t4_claude_imports(d):
    # install.py does not produce a root CLAUDE.md — policy files land in
    # .claude/features/policy/ for the user to import as needed.
    _install(d)
    policy_dir = os.path.join(d, ".claude", "features", "policy")
    return (
        os.path.isfile(os.path.join(policy_dir, "philosophy.md"))
        and os.path.isfile(os.path.join(policy_dir, "coding-rules.md"))
    )


def t5_existing_claude_blocked(d):
    os.makedirs(os.path.join(d, ".claude"))
    # Mirrors shell: [[ -x "$INSTALL" ]] && ! "$INSTALL" "$DIR"
    # If install script doesn't exist/isn't executable, the test returns false.
    if not os.access(INSTALL, os.X_OK):
        return False
    result = _install(d)
    return result.returncode != 0


def t6_no_arg_installs_to_pwd(d):
    try:
        result = subprocess.run([INSTALL], capture_output=True, cwd=d)
    except FileNotFoundError:
        return False
    return result.returncode == 0 and os.path.isdir(os.path.join(d, ".claude"))


def t7_hook_json_output(d):
    _install(d)
    hook = os.path.join(d, ".claude", "hooks", "refresh.py")
    if not os.path.isfile(hook):
        return False
    # Seed counter at THRESHOLD-1 so next increment hits threshold.
    counter_path = os.path.join(d, ".rabbit-prompt-counter")
    with open(counter_path, "w") as f:
        f.write("19")
    # The hook reads CLAUDE.md for @-imports. Provide a minimal one pointing
    # at a file that exists in the installed target.
    claude_md = os.path.join(d, "CLAUDE.md")
    policy_path = ".claude/features/policy/philosophy.md"
    with open(claude_md, "w") as f:
        f.write(f"# Test\n@{policy_path}\n")
    out_path = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as out_f:
            out_path = out_f.name
        env = os.environ.copy()
        env["RABBIT_ROOT"] = d
        env["RABBIT_REFRESH_EVERY"] = "20"
        with open(out_path, "w") as out_f:
            subprocess.run(["python3", hook], stdout=out_f, cwd=d, env=env)
        with open(out_path) as f:
            data = json.load(f)
        return "additionalContext" in data
    finally:
        if out_path and os.path.exists(out_path):
            os.unlink(out_path)


def _extract_pyblock(d):
    """Extract the python3 -c block from rabbit-config.md."""
    cmd_path = os.path.join(d, ".claude", "commands", "rabbit-config.md")
    with open(cmd_path) as f:
        lines = f.readlines()
    # Find lines between 'python3 -c "' and the closing '"`'
    in_block = False
    block_lines = []
    for line in lines:
        if not in_block:
            if 'python3 -c "' in line:
                in_block = True
        else:
            if line.rstrip() == '"`':
                break
            block_lines.append(line)
    return "".join(block_lines)


def t8a_threshold_invalid_rejected(d):
    _install(d)
    try:
        pyblock = _extract_pyblock(d)
    except FileNotFoundError:
        return False
    env = os.environ.copy()
    env["ARGUMENTS"] = "prompt-threshold abc"
    result = subprocess.run(
        ["python3", "-c", pyblock],
        capture_output=True,
        cwd=d,
        env=env,
    )
    return result.returncode != 0


def t8b_threshold_valid_writes_json(d):
    _install(d)
    try:
        pyblock = _extract_pyblock(d)
    except FileNotFoundError:
        return False
    env = os.environ.copy()
    env["ARGUMENTS"] = "prompt-threshold 15"
    subprocess.run(["python3", "-c", pyblock], capture_output=True, cwd=d, env=env)
    local_json = os.path.join(d, ".claude", "settings.local.json")
    try:
        with open(local_json) as f:
            data = json.load(f)
        return data["env"]["RABBIT_REFRESH_EVERY"] == "15"
    except FileNotFoundError:
        return False


def t9_no_settings_local_installed(d):
    _install(d)
    return not os.path.isfile(os.path.join(d, ".claude", "settings.local.json"))


def t10_default_strips_specs_and_plans(d):
    _install(d)
    import glob
    specs = glob.glob(os.path.join(d, ".claude", "docs", "specs", "*.md"))
    plans = glob.glob(os.path.join(d, ".claude", "docs", "plans", "*.md"))
    return len(specs) == 0 and len(plans) == 0


def t11_default_no_archive_no_test_dir(d):
    _install(d)
    return not os.path.isdir(os.path.join(d, "archive")) and not os.path.isdir(os.path.join(d, "test"))


def t12_all_keeps_specs_and_plans_if_present(d):
    import glob
    _install(d, "--all")
    src_specs = glob.glob(os.path.join(REPO_ROOT, ".claude", "docs", "specs", "*.md"))
    if src_specs:
        dst_specs = glob.glob(os.path.join(d, ".claude", "docs", "specs", "*.md"))
        return len(dst_specs) > 0
    return True


def t13_all_includes_archive_and_test_when_present(d):
    _install(d, "--all")
    if os.path.isdir(os.path.join(REPO_ROOT, "archive")):
        if not os.path.isdir(os.path.join(d, "archive")):
            return False
    if os.path.isdir(os.path.join(REPO_ROOT, "test")):
        if not os.path.isdir(os.path.join(d, "test")):
            return False
    return True


def t14_unknown_flag_rejected(d):
    try:
        result = subprocess.run([INSTALL, "--bogus", d], capture_output=True)
    except FileNotFoundError:
        # install.sh missing → nonzero, which means the "reject" condition is met
        return True
    return result.returncode != 0


def t15_all_works_with_target_first_then_flag(d):
    try:
        result = subprocess.run([INSTALL, d, "--all"], capture_output=True)
    except FileNotFoundError:
        return False
    return result.returncode == 0 and os.path.isdir(os.path.join(d, ".claude"))


# ── run all ───────────────────────────────────────────────────────────────────

run("1: clean install — .claude/ and settings.json present",           t1_clean_install)
run("2: hook refresh.py is executable",                                 t2_hook_executable)
run("3: settings.json has RABBIT_REFRESH_EVERY=20",                    t3_settings_content)
run("4: policy feature files installed",                                t4_claude_imports)
run("5: existing .claude/ blocks install",                              t5_existing_claude_blocked)
run("6: no arg installs to $PWD",                                       t6_no_arg_installs_to_pwd)
run("7: hook emits valid JSON at threshold",                            t7_hook_json_output)
run("8a: threshold rejects invalid arg",                                t8a_threshold_invalid_rejected)
run("8b: threshold writes correct JSON",                                t8b_threshold_valid_writes_json)
run("9: settings.local.json not installed",                             t9_no_settings_local_installed)
run("10: default install strips docs/specs/*.md and docs/plans/*.md",  t10_default_strips_specs_and_plans)
run("11: default install does NOT bring archive/ or test/",             t11_default_no_archive_no_test_dir)
run("12: --all keeps docs/specs/ and docs/plans/",                     t12_all_keeps_specs_and_plans_if_present)
run("13: --all includes archive/ and test/ when source has them",      t13_all_includes_archive_and_test_when_present)
run("14: unknown flag rejected",                                        t14_unknown_flag_rejected)
run("15: --all works after target arg",                                 t15_all_works_with_target_first_then_flag)

print()
print(f"{PASS} passed, {FAIL} failed")
sys.exit(0 if FAIL == 0 else 1)
