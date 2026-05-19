#!/usr/bin/env python3
# E2E test for Wave-5 cleanup (BUGs 20, 21, 23, 24, 25, 26, 27, 30, 32, 33, 34,
# 36, 38/39, 40, 41, 42, 43, 44, 45, 47, 48, 49, 50).
#
# Each test inspects the SOURCE artifact (script, spec, contract, SKILL.md, or
# test file) for the deterministic invariant declared by the bug fix. Tests
# avoid coupling to the implementation by checking the surface behaviour or
# textual contract the user-visible artifact must expose.

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = subprocess.check_output(
    ['git', 'rev-parse', '--show-toplevel'], cwd=SCRIPT_DIR
).decode().strip()

FEATURE_DIR = os.path.join(REPO_ROOT, '.claude/features/tdd-subagent')
DISPATCH_PY = os.path.join(FEATURE_DIR, 'scripts/dispatch-tdd-subagent.py')
TDD_STEP_PY = os.path.join(FEATURE_DIR, 'scripts/tdd-step.py')
TDD_DRIFT_PY = os.path.join(FEATURE_DIR, 'scripts/tdd-drift-check.py')
SPEC_PATH = os.path.join(FEATURE_DIR, 'docs/spec/spec.md')
CONTRACT_PATH = os.path.join(FEATURE_DIR, 'docs/spec/contract.md')
SKILL_PATH = os.path.join(REPO_ROOT, '.claude/features/rabbit-feature/skills/rabbit-feature-touch/SKILL.md')
FEATURE_JSON = os.path.join(FEATURE_DIR, 'feature.json')
TEST_TDD_STEP_PY = os.path.join(FEATURE_DIR, 'test/test-tdd-step.py')

PASS = 0
FAIL = 0


def ok(msg):
    global PASS
    print(f"  ok   {msg}")
    PASS += 1


def ko(msg):
    global FAIL
    print(f"  FAIL {msg}")
    FAIL += 1


def _read(p):
    with open(p, 'r', encoding='utf-8') as f:
        return f.read()


def _run_dispatch(extra_args=None):
    args = [
        sys.executable, DISPATCH_PY,
        '--scope', 'tdd-subagent',
        '--spec', SPEC_PATH,
        '--human-approval-gate', 'false',
    ]
    if extra_args:
        args.extend(extra_args)
    res = subprocess.run(args, capture_output=True, text=True, check=False)
    return res


# ---- BUG-20: contract.md must not mention deleted --bug/--backlog flags ----
def t_bug20_contract_no_legacy_flags():
    txt = _read(CONTRACT_PATH)
    if '--bug ' in txt or '--backlog ' in txt or '--bug <' in txt or '--backlog <' in txt:
        ko("bug20: contract.md still references --bug/--backlog dispatch flags")
    else:
        ok("bug20: contract.md does not reference deleted --bug/--backlog flags")
    # Positive: it should mention the replacement
    if '--linked-item' in txt:
        ok("bug20: contract.md mentions --linked-item replacement")
    else:
        ko("bug20: contract.md missing --linked-item description")


# ---- BUG-23: --spec-no-change-reason must be recorded in feature.json ----
def t_bug23_spec_no_change_reason_persisted():
    tmp = tempfile.mkdtemp()
    try:
        d = os.path.join(tmp, 'feat')
        os.makedirs(os.path.join(d, 'test'), exist_ok=True)
        with open(os.path.join(d, 'feature.json'), 'w') as f:
            json.dump({
                "name": "t-bug23", "version": "0.1.0",
                "tdd_state": "spec-update", "updated": "2026-05-08",
            }, f)
        # transition spec-update -> test-red with --spec-no-change-reason
        res = subprocess.run(
            [sys.executable, TDD_STEP_PY, 'transition', d, 'test-red',
             '--spec-no-change-reason', 'bug-fix only, spec unchanged'],
            capture_output=True, text=True, check=False,
        )
        if res.returncode != 0:
            ko(f"bug23: transition failed: {res.stderr}")
            return
        with open(os.path.join(d, 'feature.json')) as f:
            data = json.load(f)
        if data.get('spec_no_change_reason') == 'bug-fix only, spec unchanged':
            ok("bug23: --spec-no-change-reason persisted in feature.json")
        else:
            ko(f"bug23: spec_no_change_reason not stored (got {data.get('spec_no_change_reason')!r})")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ---- BUG-24: sync_deployed_skills documented in spec OR removed ----
def t_bug24_sync_deployed_skills_documented_or_absent():
    src = _read(TDD_STEP_PY)
    has_fn = 'def sync_deployed_skills' in src
    spec = _read(SPEC_PATH)
    spec_mentions = 'sync_deployed_skills' in spec or 'sync deployed skills' in spec.lower()
    if not has_fn:
        ok("bug24: sync_deployed_skills removed from tdd-step.py")
    elif spec_mentions:
        ok("bug24: sync_deployed_skills hook documented in spec")
    else:
        ko("bug24: sync_deployed_skills exists but is undocumented in spec")


# ---- BUG-25: dispatch-tdd-subagent.py validates --spec file exists ----
def t_bug25_dispatch_validates_spec_file():
    res = subprocess.run(
        [sys.executable, DISPATCH_PY,
         '--scope', 'tdd-subagent',
         '--spec', '/nonexistent/spec/path.md',
         '--human-approval-gate', 'false'],
        capture_output=True, text=True, check=False,
    )
    if res.returncode != 0 and ('spec' in res.stderr.lower() or 'not found' in res.stderr.lower() or 'does not exist' in res.stderr.lower()):
        ok("bug25: missing --spec file causes non-zero exit with clear error")
    else:
        ko(f"bug25: missing --spec file not validated (rc={res.returncode}, stderr={res.stderr!r})")


# ---- BUG-26: dispatch-tdd-subagent.py exit 2 on missing find-feature ----
def t_bug26_missing_feature_exits_2():
    # A scope name that won't be found
    res = subprocess.run(
        [sys.executable, DISPATCH_PY,
         '--scope', 'nonexistent-feature-xyz-12345',
         '--spec', SPEC_PATH,
         '--human-approval-gate', 'false'],
        capture_output=True, text=True, check=False,
    )
    # spec exists at minimum so other check passes; only find-feature fails
    if res.returncode == 2:
        ok("bug26: missing feature returns exit 2 (invocation error)")
    else:
        ko(f"bug26: missing feature returned {res.returncode} (expected 2)")


# ---- BUG-27: STEP 4 TEST-WRITE commit ordering vs TEST-RED verification ----
def t_bug27_test_write_commit_clarified():
    prompt = _run_dispatch().stdout
    if not prompt:
        ko("bug27: dispatch returned no prompt")
        return
    # Find STEP 4 body
    m4 = re.search(r"STEP\s+4\s+[-—]\s+TEST-WRITE\s*\n[═=]+\s*\n(.*?)(?=\n[═=]{5,})", prompt, re.DOTALL)
    if not m4:
        ko("bug27: STEP 4 section not found")
        return
    body = m4.group(1)
    # Look for either reordering note (commit AFTER fail), OR an explicit note
    # that the commit precedes the run but STEP 5 verifies failure.
    has_clarification = bool(re.search(
        r"(STEP\s+5|TEST-RED).*verif",
        body, re.IGNORECASE | re.DOTALL,
    )) or bool(re.search(
        r"after.*(fail|TEST-RED)",
        body, re.IGNORECASE | re.DOTALL,
    ))
    if has_clarification:
        ok("bug27: STEP 4 TEST-WRITE clarifies commit vs TEST-RED ordering")
    else:
        ko("bug27: STEP 4 TEST-WRITE lacks clarification about commit-before-verify")


# ---- BUG-47: tdd-report schema clearly instructs substitution ----
def t_bug47_tdd_report_substitution_note():
    prompt = _run_dispatch().stdout
    if not prompt:
        ko("bug47: dispatch returned no prompt")
        return
    m8 = re.search(r"STEP\s+8\s+[-—]\s+TEST-GREEN\s*\n[═=]+\s*\n(.*?)(?=\n[═=]{5,})", prompt, re.DOTALL)
    if not m8:
        ko("bug47: STEP 8 not found")
        return
    body = m8.group(1)
    # The body must instruct substitution clearly with explicit "do not copy
    # literally" or equivalent. Looking ONLY for unambiguous warnings.
    has_explicit_warning = (
        re.search(r"(do not|don't)\s+copy", body, re.IGNORECASE) is not None
        or re.search(r"substitute\s+(actual|real)\s+values", body, re.IGNORECASE) is not None
        or re.search(r"replace\s+(the\s+)?(placeholder|<.*?>)", body, re.IGNORECASE) is not None
    )
    if has_explicit_warning:
        ok("bug47: STEP 8 explicitly instructs substitution (not literal copy)")
    else:
        ko("bug47: STEP 8 missing explicit substitution warning")


# ---- BUG-21: Step 2 HUMAN-APPROVAL uses === banner style ----
def t_bug21_human_approval_banner_uniform():
    # We need to test the GATED form (the bypass form is uniformly Skipped).
    # Run dispatch WITHOUT --human-approval-gate (default true).
    res = subprocess.run(
        [sys.executable, DISPATCH_PY,
         '--scope', 'tdd-subagent',
         '--spec', SPEC_PATH],
        capture_output=True, text=True, check=False,
    )
    if res.returncode != 0:
        ko(f"bug21: dispatch failed: {res.stderr}")
        return
    prompt = res.stdout
    # Look for STEP 2 — HUMAN-APPROVAL with === banner (== or ══ block above and below header).
    if re.search(r"[═=]{5,}\s*\nSTEP\s+2\s+[-—]\s+HUMAN-APPROVAL\s*\n[═=]{5,}", prompt):
        ok("bug21: STEP 2 HUMAN-APPROVAL uses === banner format")
    else:
        ko("bug21: STEP 2 HUMAN-APPROVAL does not use === banner format")


# ---- BUG-30: t8 message clarity ----
def t_bug30_t8_message_clear():
    src = _read(TEST_TDD_STEP_PY)
    # Find t8 function definition
    m = re.search(r"def t8\(\):\s*\n(.*?)(?=\ndef\s)", src, re.DOTALL)
    if not m:
        ko("bug30: t8 function not found")
        return
    body = m.group(1)
    # "no exit" was the misleading wording. It should describe terminal correctly.
    # Acceptable: contains "terminal" and does NOT say "no exit" or "exitable"
    if 'no exit' in body.lower() or 'exitable' in body.lower():
        ko("bug30: t8 still uses misleading 'no exit' / 'exitable' wording")
    else:
        ok("bug30: t8 wording no longer uses misleading 'no exit' phrasing")


# ---- BUG-32: tdd-step.py uses Unicode literals or ASCII (no hex \xe2 escapes) ----
def t_bug32_no_hex_byte_escapes():
    src = _read(TDD_STEP_PY)
    # Look for the literal sequence \xe2 in raw source (hex escape syntax).
    # If a Unicode literal (━) is used instead, \xe2 won't appear in source.
    if r'\xe2' in src or r'\x94' in src or r'\x81' in src:
        ko("bug32: tdd-step.py still uses non-portable \\xNN hex escapes for box-drawing")
    else:
        ok("bug32: tdd-step.py uses Unicode literals or ASCII (no hex escapes)")


# ---- BUG-33: write_state uses tempfile + atomic rename ----
def t_bug33_write_state_atomic():
    src = _read(TDD_STEP_PY)
    # Look for an atomic rename pattern (os.replace) after writing to a temp file.
    # The function `write_state` must reference both tempfile/.tmp and os.replace/rename.
    m = re.search(r"def write_state\(.*?\):\s*\n(.*?)(?=\n(?:def|class)\s)", src, re.DOTALL)
    if not m:
        ko("bug33: write_state function not found")
        return
    body = m.group(1)
    if ('os.replace' in body or 'os.rename' in body) and ('.tmp' in body or 'tempfile' in body or 'NamedTemporaryFile' in body):
        ok("bug33: write_state writes to temp file then atomically renames")
    else:
        ko("bug33: write_state lacks atomic tempfile+rename pattern")


# ---- BUG-34: tdd-drift-check.py executability check removed or justified ----
def t_bug34_drift_check_no_executability_check():
    src = _read(TDD_DRIFT_PY)
    # The script uses `python3 runner` so executable bit is irrelevant.
    # Check that the os.X_OK guard was removed.
    if 'os.X_OK' in src:
        ko("bug34: tdd-drift-check.py still checks os.X_OK; the script runs `python3 runner` which doesn't need it")
    else:
        ok("bug34: tdd-drift-check.py no longer checks executability")


# ---- BUG-36: SKILL.md B/B mode jq dependency declared OR replaced ----
def t_bug36_no_undeclared_jq():
    src = _read(SKILL_PATH)
    has_jq = bool(re.search(r"\bjq\s+-r\b", src))
    if not has_jq:
        ok("bug36: SKILL.md does not use undeclared jq (replaced or removed)")
        return
    # If jq still used, must have a "Dependencies" note in SKILL.md mentioning jq.
    if re.search(r"(depend|requires).*jq", src, re.IGNORECASE):
        ok("bug36: SKILL.md uses jq AND declares it as a dependency")
    else:
        ko("bug36: SKILL.md uses jq but jq is undeclared (add note or replace with python3 -c)")


# ---- BUG-38/39: dispatch-tdd-subagent.py invariant logic deduplicated ----
def t_bug38_dispatch_no_duplicated_logic():
    src = _read(DISPATCH_PY)
    # The original concern: linked-items close-call block emitted line-by-line
    # in two places. After dedup, the template literal that constructs the
    # f-string (`--status close \\`) must appear in exactly ONE source
    # location (a helper function used by both primary and secondary call
    # sites). Comment-only mentions in the module docstring don't count.
    code_lines = [
        ln for ln in src.splitlines()
        if ln.strip().startswith(('"', "'", 'f"', "f'"))
    ]
    code_src = "\n".join(code_lines)
    count = code_src.count("--status close")
    if count == 1:
        ok(f"bug38: close-call template literal appears once in code (deduplicated)")
    else:
        ko(f"bug38: close-call template literal appears {count} times in code (expected 1)")


# ---- BUG-40: t8 function name accurate ----
def t_bug40_t8_name_or_docstring_accurate():
    src = _read(TEST_TDD_STEP_PY)
    m = re.search(r"#\s*t8:\s*(.*)", src)
    if not m:
        # If t8 was renamed entirely, accept any test referencing terminal state
        if 'terminal' in src.lower():
            ok("bug40: t8-equivalent test for terminal state exists")
        else:
            ko("bug40: no test for terminal state found")
        return
    comment = m.group(1)
    # Comment should mention terminal correctly, not be misleading
    if 'terminal' in comment.lower() and 'cannot' in comment.lower():
        ok(f"bug40: t8 comment is accurate: {comment.strip()!r}")
    else:
        ko(f"bug40: t8 comment may be misleading: {comment.strip()!r}")


# ---- BUG-41: tests reference dispatch-tdd-subagent.py (not .sh) ----
def t_bug41_no_sh_dispatch_refs():
    test_dir = os.path.join(FEATURE_DIR, 'test')
    bad = []
    self_name = os.path.basename(__file__)
    for name in os.listdir(test_dir):
        if not name.endswith('.py') or name == self_name:
            continue
        with open(os.path.join(test_dir, name)) as f:
            txt = f.read()
        if 'dispatch-tdd-subagent.sh' in txt:
            bad.append(name)
    if bad:
        ko(f"bug41: tests still reference dispatch-tdd-subagent.sh: {bad}")
    else:
        ok("bug41: no test references dispatch-tdd-subagent.sh")


# ---- BUG-42: t9 walks past test-green correctly with new cycle restart ----
def t_bug42_t9_walks_validly():
    src = _read(TEST_TDD_STEP_PY)
    m = re.search(r"def t9\(\):\s*\n(.*?)(?=\ndef\s)", src, re.DOTALL)
    if not m:
        ko("bug42: t9 not found")
        return
    body = m.group(1)
    # t9 walks: spec -> spec-update -> test-red -> impl -> test-green -> deprecated.
    # After BUG-51 fix, test-green -> deprecated remains valid (cycle restart adds
    # test-green -> spec-update as ALTERNATE). The walk should still succeed.
    if "'deprecated'" in body or '"deprecated"' in body:
        ok("bug42: t9 still walks the canonical forward path through deprecated")
    else:
        ko("bug42: t9 lost the canonical walk")


# ---- BUG-43: tdd-step.py main validates unknown cmd values ----
def t_bug43_unknown_cmd_rejected():
    res = subprocess.run(
        [sys.executable, TDD_STEP_PY, 'bogus-cmd', 'arg'],
        capture_output=True, text=True, check=False,
    )
    if res.returncode != 0 and 'unknown' in res.stderr.lower():
        ok("bug43: unknown subcommand rejected with clear error")
    else:
        ko(f"bug43: unknown subcommand not rejected (rc={res.returncode}, stderr={res.stderr!r})")


# ---- BUG-44: dispatch-tdd-subagent.py supports --help ----
def t_bug44_dispatch_supports_help():
    res = subprocess.run(
        [sys.executable, DISPATCH_PY, '--help'],
        capture_output=True, text=True, check=False,
    )
    # --help should exit 0 and print a usage line
    if res.returncode == 0 and ('usage' in res.stdout.lower() or 'usage' in res.stderr.lower() or '--scope' in res.stdout):
        ok("bug44: dispatch-tdd-subagent.py --help works")
    else:
        ko(f"bug44: --help did not work (rc={res.returncode})")


# ---- BUG-45: feature.json has status: active ----
def t_bug45_feature_json_status():
    with open(FEATURE_JSON) as f:
        data = json.load(f)
    if data.get('status') == 'active':
        ok("bug45: feature.json has status: active")
    else:
        ko(f"bug45: feature.json missing status field (got {data.get('status')!r})")


# ---- BUG-48: _post_test_green_hooks guards rabbit-project-consolidate ----
def t_bug48_post_hook_guarded():
    src = _read(TDD_STEP_PY)
    m = re.search(r"def _post_test_green_hooks\(.*?\):\s*\n(.*?)(?=\n(?:def|class)\s)", src, re.DOTALL)
    if not m:
        ko("bug48: _post_test_green_hooks not found")
        return
    body = m.group(1)
    # rabbit-project.py call must be inside try/except OR conditional on existing path
    # The current code IS guarded by os.path.isfile(project_map) AND os.path.isfile(onboard_py)
    # AND wrapped in try/except. Look for try/except around the subprocess call.
    if 'rabbit-project.py' not in body:
        ok("bug48: rabbit-project.py call removed from _post_test_green_hooks")
        return
    # Find the subprocess call to onboard_py and ensure it's within try/except
    if re.search(r"try:.*?subprocess.*?onboard_py.*?except", body, re.DOTALL) or \
       re.search(r"try:.*?onboard_py.*?subprocess.*?except", body, re.DOTALL):
        ok("bug48: rabbit-project.py call guarded by try/except")
    else:
        ko("bug48: rabbit-project.py call lacks try/except guard")


# ---- BUG-49: auto-close uses real SHA via git rev-parse HEAD ----
def t_bug49_auto_close_uses_real_sha():
    src = _read(TDD_STEP_PY)
    m = re.search(r"def auto_close_backlog\(.*?\):\s*\n(.*?)(?=\n(?:def|class)\s)", src, re.DOTALL)
    if not m:
        ko("bug49: auto_close_backlog function not found")
        return
    body = m.group(1)
    # Look for either a direct git rev-parse HEAD invocation or a call to a
    # helper that performs it (e.g., _head_sha). Both deliver a real SHA.
    uses_real_sha = ('rev-parse' in body) or ('_head_sha' in body)
    has_literal_HEAD = bool(re.search(
        r'--fix-commits["\']?\s*,\s*["\']HEAD["\']', body
    ))
    if uses_real_sha and not has_literal_HEAD:
        ok("bug49: auto_close_backlog computes real SHA (not literal 'HEAD')")
    elif has_literal_HEAD:
        ko("bug49: auto_close_backlog still passes literal 'HEAD' as fix_commits")
    else:
        ko("bug49: auto_close_backlog doesn't compute a real SHA")


# ---- BUG-50: SKILL.md Step 5 dispatch separates bash from Agent() pseudocode ----
def t_bug50_skill_step5_separates_bash_and_agent():
    src = _read(SKILL_PATH)
    # Look at the "Step 5 — Dispatch TDD Subagents" section
    m = re.search(r"###\s+Step\s+5\s+[-—]\s+Dispatch.*?(?=###\s+Step|\Z)", src, re.DOTALL)
    if not m:
        ko("bug50: Step 5 section not found in SKILL.md")
        return
    section = m.group(0)
    # Count fenced bash blocks and inspect content
    bash_blocks = re.findall(r"```bash\s*\n(.*?)```", section, re.DOTALL)
    # Find any block containing Agent(...) and ensure it's NOT in a bash fence
    has_agent = bool(re.search(r"Agent\(model", section))
    agent_in_bash = any('Agent(model' in b for b in bash_blocks)
    if has_agent and not agent_in_bash:
        ok("bug50: Step 5 Agent() pseudocode is separated from bash fence")
    elif not has_agent:
        ok("bug50: Step 5 no longer mixes Agent() pseudocode")
    else:
        ko("bug50: Step 5 still mixes Agent() pseudocode inside bash fence")


# ---- Run -------------------------------------------------------------------

print("running tdd-subagent Wave-5 cleanup tests")
t_bug20_contract_no_legacy_flags()
t_bug21_human_approval_banner_uniform()
t_bug23_spec_no_change_reason_persisted()
t_bug24_sync_deployed_skills_documented_or_absent()
t_bug25_dispatch_validates_spec_file()
t_bug26_missing_feature_exits_2()
t_bug27_test_write_commit_clarified()
t_bug30_t8_message_clear()
t_bug32_no_hex_byte_escapes()
t_bug33_write_state_atomic()
t_bug34_drift_check_no_executability_check()
t_bug36_no_undeclared_jq()
t_bug38_dispatch_no_duplicated_logic()
t_bug40_t8_name_or_docstring_accurate()
t_bug41_no_sh_dispatch_refs()
t_bug42_t9_walks_validly()
t_bug43_unknown_cmd_rejected()
t_bug44_dispatch_supports_help()
t_bug45_feature_json_status()
t_bug47_tdd_report_substitution_note()
t_bug48_post_hook_guarded()
t_bug49_auto_close_uses_real_sha()
t_bug50_skill_step5_separates_bash_and_agent()
print()
print(f"summary: {PASS} passed, {FAIL} failed")
sys.exit(0 if FAIL == 0 else 1)
