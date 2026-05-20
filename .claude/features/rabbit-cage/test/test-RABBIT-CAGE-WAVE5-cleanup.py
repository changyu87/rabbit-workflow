#!/usr/bin/env python3
"""rabbit-cage WAVE5 cleanup tests: 5 bug-fixes + 5 backlog items.

Bugs (assertion tightening): BUG-55, BUG-64, BUG-70, BUG-76, BUG-86
Backlogs (impl): BACKLOG-7, BACKLOG-12, BACKLOG-13, BACKLOG-16, BACKLOG-17
"""
import json
import os
import re
import subprocess
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = subprocess.run(
    ["git", "-C", SCRIPT_DIR, "rev-parse", "--show-toplevel"],
    capture_output=True, text=True, check=True,
).stdout.strip()

TEST_DIR = os.path.join(REPO_ROOT, ".claude/features/rabbit-cage/test")
HOOKS_DIR = os.path.join(REPO_ROOT, ".claude/features/rabbit-cage/hooks")
SETTINGS_JSON = os.path.join(REPO_ROOT, ".claude/features/rabbit-cage/settings.json")
SKILL_MD = os.path.join(REPO_ROOT, ".claude/features/rabbit-cage/skills/rabbit-config/SKILL.md")
SPEC_MD = os.path.join(REPO_ROOT, ".claude/features/rabbit-cage/docs/spec/spec.md")
GITIGNORE = os.path.join(REPO_ROOT, ".gitignore")

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


print("test-RABBIT-CAGE-WAVE5-cleanup.py")
print()

# ---- BUG-55: tightened scope-guard centralized substring checks ----
centr = read(os.path.join(TEST_DIR, "test-scope-guard-centralized.py"))

# t1 — assertion must reference the literal path-prefix '.claude/bugs' (not
#       just the bare substring 'bugs', which would also match unrelated
#       comments). BUG-87 dropped the trailing slash from the prefix literal
#       so the assertion accepts either form.
if ".claude/bugs" in centr:
    ok(1, "BUG-55: test-scope-guard-centralized.py asserts literal '.claude/bugs' path-prefix substring")
else:
    fail_t(1, "BUG-55: test-scope-guard-centralized.py t1 still uses weak 'bugs' substring (not tightened to '.claude/bugs')")

# t2 — same for backlogs.
if ".claude/backlogs" in centr:
    ok(2, "BUG-55: test-scope-guard-centralized.py asserts literal '.claude/backlogs' path-prefix substring")
else:
    fail_t(2, "BUG-55: test-scope-guard-centralized.py t2 still uses weak 'backlogs' substring (not tightened to '.claude/backlogs')")

# ---- BUG-64: hard-coded ../../../../ depth replaced by git rev-parse ----
bk2 = read(os.path.join(TEST_DIR, "test-RABBIT-CAGE-BACKLOG2-python-only.py"))

# t3 — assertion targets the os.path.join(..., '../../../..') idiom (the bug
# fingerprint). A bare '../../../..' in a comment is acceptable; only the
# active code path counts.
if 'os.path.join(SCRIPT_DIR, "../../../..")' not in bk2 \
        and "git" in bk2 and "rev-parse" in bk2:
    ok(3, "BUG-64: test-RABBIT-CAGE-BACKLOG2-python-only.py uses git rev-parse (no ../../../.. join)")
else:
    fail_t(3, "BUG-64: test-RABBIT-CAGE-BACKLOG2-python-only.py still uses hard-coded ../../../.. depth")

# ---- BUG-70: tightened t19 assertion in test-rabbit-config-permissions.py ----
perms_test = read(os.path.join(TEST_DIR, "test-rabbit-config-permissions.py"))

# t4 — assertion explicitly checks the ' to .claude/settings.local.json' phrase.
if " to .claude/settings.local.json" in perms_test:
    ok(4, "BUG-70: test-rabbit-config-permissions.py t19 asserts ' to .claude/settings.local.json' explicitly")
else:
    fail_t(4, "BUG-70: test-rabbit-config-permissions.py t19 not tightened to assert ' to .claude/settings.local.json'")

# ---- BUG-76: regex broadened in test-RABBIT-CAGE-19-confirm-token-override.py t1 ----
ct19 = read(os.path.join(TEST_DIR, "test-RABBIT-CAGE-19-confirm-token-override.py"))

# t5 — t1 must use a regex/keyword pattern, not the exact 'only a human creates this file' string.
if "only.*human.*creat" in ct19 or re.search(r"r['\"]only.*human", ct19):
    ok(5, "BUG-76: test-RABBIT-CAGE-19 t1 uses regex/keyword check (not exact substring)")
else:
    fail_t(5, "BUG-76: test-RABBIT-CAGE-19 t1 still uses overly specific 'only a human creates this file' substring")

# ---- BUG-86: schema-level feature.json assertion in test-rabbit-config.py ----
rc_test = read(os.path.join(TEST_DIR, "test-rabbit-config.py"))

# t6 — assertion must explicitly check cmds == [] (schema), not loose substring.
if "cmds == []" in rc_test:
    ok(6, "BUG-86: test-rabbit-config.py t4 asserts surface.commands == [] (schema-level)")
else:
    fail_t(6, "BUG-86: test-rabbit-config.py t4 still uses loose substring check (no 'cmds == []' assertion)")

# ---- BACKLOG-7: refresh.py / session-init.py break multi-file lists into newlines ----
# BACKLOG-19: the per-file lines are now emitted via rabbit_subline(...) calls
# (one per @-import) rather than a literal "\n  · " join. Assert that each
# hook produces per-file lines via the rabbit_subline renderer.
refresh_py = read(os.path.join(HOOKS_DIR, "refresh.py"))
sess_init = read(os.path.join(HOOKS_DIR, "session-init.py"))

# t7 — refresh.py: per-file lines via rabbit_subline.
if "rabbit_subline" in refresh_py and "imports" in refresh_py:
    ok(7, "BACKLOG-7/19: refresh.py emits per-file lines via rabbit_subline()")
else:
    fail_t(7, "BACKLOG-7/19: refresh.py does not emit per-file lines via rabbit_subline()")

# t8 — session-init.py likewise.
if "rabbit_subline" in sess_init and "imports" in sess_init:
    ok(8, "BACKLOG-7/19: session-init.py emits per-file lines via rabbit_subline()")
else:
    fail_t(8, "BACKLOG-7/19: session-init.py does not emit per-file lines via rabbit_subline()")

# ---- BACKLOG-12: bypassPermissions in settings.json + SKILL.md doc ----
settings = json.loads(read(SETTINGS_JSON))
skill = read(SKILL_MD)

# t9 — INVERTED for BACKLOG-12 reopening: bypass mode is now per-user (Inv 69
# rewritten), so the shared settings.json MUST NOT declare permissions.defaultMode.
# Operators opt in via /rabbit-config bypass-permissions true → settings.local.json.
if "defaultMode" not in settings.get("permissions", {}):
    ok(9, "BACKLOG-12 (reopened): settings.json no longer declares permissions.defaultMode (now per-user via settings.local.json)")
else:
    fail_t(9, "BACKLOG-12 (reopened): settings.json still declares permissions.defaultMode (must be removed; bypass mode is per-user)")

# t10 — SKILL.md documents skipDangerousModePermissionPrompt user-local option.
if "skipDangerousModePermissionPrompt" in skill and "settings.local.json" in skill:
    ok(10, "BACKLOG-12: SKILL.md documents skipDangerousModePermissionPrompt in settings.local.json")
else:
    fail_t(10, "BACKLOG-12: SKILL.md does not document skipDangerousModePermissionPrompt")

# ---- BACKLOG-13: shared test helper module ----
helpers_py = os.path.join(TEST_DIR, "test_helpers.py")

# t11
if os.path.isfile(helpers_py):
    helpers_src = read(helpers_py)
    if "def make_clean_repo" in helpers_src:
        ok(11, "BACKLOG-13: test/test_helpers.py exists with make_clean_repo()")
    else:
        fail_t(11, "BACKLOG-13: test_helpers.py exists but lacks make_clean_repo()")
else:
    fail_t(11, "BACKLOG-13: test/test_helpers.py missing")

# t12 — at least one previously-duplicating test file imports from test_helpers.
adopters = [
    "test-RABBIT-CAGE-21-plugin-change-alert.py",
    "test-RABBIT-CAGE-BACKLOG-18-aggregation.py",
    "test-BACKLOG-11-rabbit-config-skill.py",
    "test-RABBIT-CAGE-18-scope-alert-messages.py",
    "test-RABBIT-CAGE-BACKLOG10-override.py",
    "test-RABBIT-CAGE-BUG123.py",
]
adopt_count = 0
for f in adopters:
    try:
        if "from test_helpers import" in read(os.path.join(TEST_DIR, f)) or \
           "import test_helpers" in read(os.path.join(TEST_DIR, f)):
            adopt_count += 1
    except Exception:
        pass
if adopt_count >= 1:
    ok(12, f"BACKLOG-13: {adopt_count}/{len(adopters)} duplicating test file(s) now import test_helpers")
else:
    fail_t(12, "BACKLOG-13: no test file imports test_helpers (helper not yet adopted)")

# ---- BACKLOG-16: spec invariant + test asserting runtime markers are gitignored ----
spec = read(SPEC_MD)
gi = read(GITIGNORE)

REQUIRED_MARKERS = [
    ".rabbit-prompt-counter",
    ".rabbit-sync-counter",
    ".rabbit-scope-active",
    ".rabbit-scope-override",
    ".rabbit-scope-override-used",
    ".rabbit-skills-updated",
    ".rabbit-human-approval-bypass",
]

# t13 — every required marker is in .gitignore (the actual contract).
missing_gi = [m for m in REQUIRED_MARKERS if m not in gi]
if not missing_gi:
    ok(13, "BACKLOG-16: every runtime marker listed in .gitignore")
else:
    fail_t(13, f"BACKLOG-16: gitignore missing markers: {missing_gi}")

# t14 — spec.md declares the gitignore-invariant for runtime markers.
# Look for an explicit invariant mentioning that runtime markers MUST be gitignored.
# Accept either an "Inv N." entry or a clear inline mandate.
if re.search(r"(runtime|all)\s+marker.*gitignore", spec, re.IGNORECASE) or \
   re.search(r"gitignore.*runtime.*marker", spec, re.IGNORECASE) or \
   "MUST be gitignored" in spec:
    ok(14, "BACKLOG-16: spec.md declares an invariant requiring runtime markers be gitignored")
else:
    fail_t(14, "BACKLOG-16: spec.md has no invariant mandating runtime markers be gitignored")

# ---- BACKLOG-17: hooks log subprocess failures to stderr (no bare swallow) ----
sync_check = read(os.path.join(HOOKS_DIR, "sync-check.py"))
scope_guard = read(os.path.join(HOOKS_DIR, "scope-guard.py"))

# Count `except Exception: pass` patterns (the silent-swallow anti-pattern).
def count_bare_swallow(src):
    # Match `except Exception:` immediately followed by a `pass`-only block.
    return len(re.findall(r"except\s+Exception:\s*\n\s*pass\b", src))


# Helper: find at least one except-handler whose body logs to stderr (directly
# or via a helper named _log_exc/log_exc/log_error/etc.). BACKLOG-28: the
# per-hook _log_exc was centralised into _runtime_flags.log_exc — accept both
# the original private name and the shared helper.
def has_stderr_logging_handler(src):
    return bool(
        re.search(
            r"except\s+\w[^\n]*:\s*\n\s*[^\n]*"
            r"(file=sys\.stderr|sys\.stderr\.write|logging\.|_log_exc\(|\blog_exc\()",
            src,
        )
    )


# t15 — sync-check.py replaces silent swallows with explicit stderr logging.
if has_stderr_logging_handler(sync_check):
    ok(15, "BACKLOG-17: sync-check.py logs exceptions to stderr from within except handlers")
else:
    fail_t(15, "BACKLOG-17: sync-check.py has no except-handler that writes to stderr")

# t16 — session-init.py likewise.
if has_stderr_logging_handler(sess_init):
    ok(16, "BACKLOG-17: session-init.py logs exceptions to stderr from within except handlers")
else:
    fail_t(16, "BACKLOG-17: session-init.py still has only bare exception swallow")

print()
print(f"Results: {pass_n} passed, {fail_n} failed")
sys.exit(0 if fail_n == 0 else 1)
