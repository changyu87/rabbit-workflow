#!/usr/bin/env python3
"""RABBIT-CAGE-BACKLOG-27 — runtime-flags display (Inv 61, Inv 62).

End-to-end coverage for two new spec behaviours:

  - Inv 61: sync-check.py emits a red [rabbit] systemMessage on every Stop
    event when .claude/settings.local.json declares permissions.defaultMode
    == "bypassPermissions". The alert is independent of the human-approval
    bypass alert (Inv 39); both may fire on the same Stop event.

  - Inv 62: session-init.py emits a status-flags block in its startup
    banner that lists every active runtime override (human-approval bypass +
    bypass-permissions mode). When no flags are active, the block is omitted
    (baseline banner unchanged).

Both producers MUST share the canonical message text per flag via a single
helper module .claude/features/rabbit-cage/hooks/_runtime_flags.py so the
two locations cannot drift (test asserts the message body is identical in
both Stop and session-start contexts).

Per Inv 44, tests MUST NOT mutate live source files — every fixture is
built inside a tempfile.mkdtemp + clean repo copy.
"""
import importlib.util
import json
import os
import shutil
import subprocess
import sys

from test_helpers import REPO_ROOT, make_git_repo

SYNC_CHECK = os.path.join(REPO_ROOT, ".claude/features/rabbit-cage/hooks/sync-check.py")
SESSION_INIT = os.path.join(REPO_ROOT, ".claude/features/rabbit-cage/hooks/session-init.py")

# BACKLOG-28: import the canonical body text from the helper module so the
# test cannot drift from the live source. The local re-declarations the
# original test used were a drift hazard — every spec wording change would
# silently pass while leaving the test asserting the stale text.
_RF_PATH = os.path.join(REPO_ROOT, ".claude/features/rabbit-cage/hooks/_runtime_flags.py")
_spec = importlib.util.spec_from_file_location("_runtime_flags_for_test", _RF_PATH)
_rf = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_rf)
BYPASS_PERMISSIONS_BODY = _rf.CANONICAL_FLAG_BODIES["bypass_permissions"]
HUMAN_APPROVAL_BODY = _rf.CANONICAL_FLAG_BODIES["human_approval"]

failures = 0
total = 0


def ok(msg):
    global total
    total += 1
    print(f"  PASS t{total}: {msg}")


def fail_t(msg):
    global total, failures
    total += 1
    failures += 1
    print(f"  FAIL t{total}: {msg}")


def run_sync(tmproot):
    env = {**os.environ, "RABBIT_ROOT": tmproot, "RABBIT_SYNC_EVERY": "1"}
    res = subprocess.run(
        [sys.executable, SYNC_CHECK], env=env, capture_output=True, text=True,
    )
    return res.stdout


def run_session_init(tmproot):
    env = {**os.environ, "RABBIT_ROOT": tmproot}
    res = subprocess.run(
        [sys.executable, SESSION_INIT], env=env, capture_output=True, text=True,
    )
    return res.stdout


def write_settings_local(tmproot, mode_value):
    """Write .claude/settings.local.json declaring the given permissions.defaultMode."""
    settings_dir = os.path.join(tmproot, ".claude")
    os.makedirs(settings_dir, exist_ok=True)
    path = os.path.join(settings_dir, "settings.local.json")
    with open(path, "w") as f:
        json.dump({"permissions": {"defaultMode": mode_value}}, f)


def parse_one_json(out):
    try:
        return json.loads(out.strip())
    except Exception:
        return None


print("test-backlog-27-runtime-flags-display.py")
print("Inv 61 + Inv 62: runtime-flags display (sync-check + session-init)")
print()

tmproots = []
try:
    # ============================================================
    # SYNC-CHECK (Inv 61) — bypass-permissions Stop alert
    # ============================================================

    # t1: bypass-permissions ACTIVE → alert appears in Stop systemMessage
    print("=== t1: bypass-permissions active → Stop alert emitted ===")
    tmproot = make_git_repo()
    tmproots.append(tmproot)
    write_settings_local(tmproot, "bypassPermissions")
    out = run_sync(tmproot)
    obj = parse_one_json(out)
    if obj is None:
        fail_t(f"expected one JSON object, got: {out!r}")
    else:
        ok("one JSON object emitted")
        msg = obj.get("systemMessage", "")
        if BYPASS_PERMISSIONS_BODY in msg:
            ok("bypass-permissions canonical message text present in systemMessage")
        else:
            fail_t(
                f"bypass-permissions message missing; expected substring "
                f"{BYPASS_PERMISSIONS_BODY!r}; got systemMessage={msg!r}"
            )
        # Red color marker
        if "\x1b[31m" in msg:
            ok("red ANSI color marker present (Inv 61 — alert color)")
        else:
            fail_t(f"red ANSI color missing from systemMessage: {msg!r}")

    # t2: bypass-permissions ABSENT → no bypass-permissions alert
    print()
    print("=== t2: bypass-permissions NOT active → no Stop alert for it ===")
    tmproot = make_git_repo()
    tmproots.append(tmproot)
    # No settings.local.json written; baseline (and no other markers).
    out = run_sync(tmproot)
    if out.strip() == "":
        ok("baseline → no JSON emitted")
    else:
        # An emission may happen for unrelated drift in the test sandbox; what
        # matters is that the bypass-permissions body is NOT in it.
        obj = parse_one_json(out)
        msg = (obj or {}).get("systemMessage", out)
        if BYPASS_PERMISSIONS_BODY in msg:
            fail_t(f"bypass-permissions alert fired without trigger: {msg!r}")
        else:
            ok("no bypass-permissions alert when settings.local.json absent")

    # t3: settings.local.json present but defaultMode is some other string
    #     → no bypass-permissions alert (check is exact-match on "bypassPermissions")
    print()
    print("=== t3: settings.local.json with non-bypass defaultMode → no alert ===")
    tmproot = make_git_repo()
    tmproots.append(tmproot)
    write_settings_local(tmproot, "default")
    out = run_sync(tmproot)
    obj = parse_one_json(out)
    msg = (obj or {}).get("systemMessage", out)
    if BYPASS_PERMISSIONS_BODY in msg:
        fail_t(f"bypass-permissions alert fired for wrong defaultMode: {msg!r}")
    else:
        ok("no bypass-permissions alert when defaultMode != 'bypassPermissions'")

    # t4: bypass-permissions + human-approval BOTH active → both alerts fire (Inv 61)
    print()
    print("=== t4: bypass-permissions + human-approval → BOTH alerts fire ===")
    tmproot = make_git_repo()
    tmproots.append(tmproot)
    write_settings_local(tmproot, "bypassPermissions")
    with open(os.path.join(tmproot, ".rabbit-human-approval-bypass"), "w") as f:
        f.write("session")
    out = run_sync(tmproot)
    obj = parse_one_json(out)
    if obj is None:
        fail_t(f"expected one JSON object, got: {out!r}")
    else:
        msg = obj.get("systemMessage", "")
        has_bp = BYPASS_PERMISSIONS_BODY in msg
        has_ha = "HUMAN APPROVAL BYPASS" in msg
        if has_bp and has_ha:
            ok("both bypass-permissions AND human-approval lines present (Inv 61)")
        else:
            fail_t(
                f"both alerts expected to coexist; has_bp={has_bp} has_ha={has_ha}; "
                f"systemMessage={msg!r}"
            )

    # t5: malformed settings.local.json → graceful (no crash, no false alert)
    print()
    print("=== t5: malformed settings.local.json → graceful, no false alert ===")
    tmproot = make_git_repo()
    tmproots.append(tmproot)
    settings_dir = os.path.join(tmproot, ".claude")
    os.makedirs(settings_dir, exist_ok=True)
    with open(os.path.join(settings_dir, "settings.local.json"), "w") as f:
        f.write("{ this is not valid json")
    out = run_sync(tmproot)
    obj = parse_one_json(out)
    msg = (obj or {}).get("systemMessage", out)
    if BYPASS_PERMISSIONS_BODY in msg:
        fail_t(f"bypass-permissions alert fired on malformed JSON: {msg!r}")
    else:
        ok("malformed settings.local.json handled gracefully (no false alert)")

    # ============================================================
    # SESSION-INIT (Inv 62) — startup status-flags block
    # ============================================================

    # t6: baseline (no flags) → status-flags block omitted entirely
    print()
    print("=== t6: baseline (no flags) → no status-flags lines in banner ===")
    tmproot = make_git_repo()
    tmproots.append(tmproot)
    claude_md = os.path.join(tmproot, "CLAUDE.md")
    with open(claude_md, "a") as f:
        f.write("\n@.claude/features/policy/philosophy.md\n")
    out = run_session_init(tmproot)
    obj = parse_one_json(out)
    if obj is None:
        fail_t(f"expected JSON output for welcome banner; got: {out!r}")
    else:
        msg = obj.get("systemMessage", "")
        if BYPASS_PERMISSIONS_BODY in msg:
            fail_t(f"bypass-permissions line should NOT appear in baseline banner: {msg!r}")
        elif HUMAN_APPROVAL_BODY in msg:
            fail_t(f"human-approval line should NOT appear in baseline banner: {msg!r}")
        else:
            ok("baseline banner contains no status-flag lines (Inv 62)")

    # t7: BOTH flags active → status-flags block lists both
    print()
    print("=== t7: both flags active → startup banner lists both ===")
    tmproot = make_git_repo()
    tmproots.append(tmproot)
    with open(os.path.join(tmproot, "CLAUDE.md"), "a") as f:
        f.write("\n@.claude/features/policy/philosophy.md\n")
    write_settings_local(tmproot, "bypassPermissions")
    with open(os.path.join(tmproot, ".rabbit-human-approval-bypass"), "w") as f:
        f.write("session")
    out = run_session_init(tmproot)
    obj = parse_one_json(out)
    if obj is None:
        fail_t(f"expected JSON output; got: {out!r}")
    else:
        msg = obj.get("systemMessage", "")
        if BYPASS_PERMISSIONS_BODY in msg:
            ok("bypass-permissions line present in startup banner")
        else:
            fail_t(f"bypass-permissions line missing from banner: {msg!r}")
        if HUMAN_APPROVAL_BODY in msg:
            ok("human-approval line present in startup banner")
        else:
            fail_t(f"human-approval line missing from banner: {msg!r}")
        # Inv 62: each flag line MUST name the canonical revoke command.
        if "/rabbit-config bypass-permissions false" in msg:
            ok("startup line names the bypass-permissions revoke command")
        else:
            fail_t(
                "bypass-permissions revoke command (/rabbit-config "
                f"bypass-permissions false) not named in banner: {msg!r}"
            )
        if "/rabbit-config human-approval true" in msg:
            ok("startup line names the human-approval revoke command")
        else:
            fail_t(
                "human-approval revoke command (/rabbit-config human-approval true) "
                f"not named in banner: {msg!r}"
            )

    # t8: only one flag active → only that line appears (no empty 'all clear')
    print()
    print("=== t8: only bypass-permissions active → only that line appears ===")
    tmproot = make_git_repo()
    tmproots.append(tmproot)
    with open(os.path.join(tmproot, "CLAUDE.md"), "a") as f:
        f.write("\n@.claude/features/policy/philosophy.md\n")
    write_settings_local(tmproot, "bypassPermissions")
    out = run_session_init(tmproot)
    obj = parse_one_json(out)
    if obj is None:
        fail_t(f"expected JSON output; got: {out!r}")
    else:
        msg = obj.get("systemMessage", "")
        if BYPASS_PERMISSIONS_BODY in msg:
            ok("bypass-permissions line present when only that flag is active")
        else:
            fail_t(f"bypass-permissions line missing: {msg!r}")
        if HUMAN_APPROVAL_BODY in msg:
            fail_t(f"human-approval line should NOT appear (flag not set): {msg!r}")
        else:
            ok("human-approval line absent (flag not set)")

    # ============================================================
    # SHARED-TEXT INVARIANT (Inv 62) — both producers emit the SAME body text
    # ============================================================

    # t9: the bypass-permissions body emitted by sync-check.py is BYTE-IDENTICAL
    #     to the body emitted by session-init.py — no drift between them.
    print()
    print("=== t9: shared canonical text — sync-check and session-init agree ===")
    tmproot_s = make_git_repo()
    tmproots.append(tmproot_s)
    write_settings_local(tmproot_s, "bypassPermissions")
    sync_out = run_sync(tmproot_s)
    sync_obj = parse_one_json(sync_out)

    tmproot_i = make_git_repo()
    tmproots.append(tmproot_i)
    with open(os.path.join(tmproot_i, "CLAUDE.md"), "a") as f:
        f.write("\n@.claude/features/policy/philosophy.md\n")
    write_settings_local(tmproot_i, "bypassPermissions")
    init_out = run_session_init(tmproot_i)
    init_obj = parse_one_json(init_out)

    sync_has = sync_obj and BYPASS_PERMISSIONS_BODY in sync_obj.get("systemMessage", "")
    init_has = init_obj and BYPASS_PERMISSIONS_BODY in init_obj.get("systemMessage", "")
    if sync_has and init_has:
        ok("both hooks emit the IDENTICAL bypass-permissions body string (no drift)")
    else:
        fail_t(
            "shared-text invariant violated: sync_has="
            f"{sync_has}, init_has={init_has}; sync_msg="
            f"{(sync_obj or {}).get('systemMessage', sync_out)!r}; "
            f"init_msg={(init_obj or {}).get('systemMessage', init_out)!r}"
        )

    # t10: the shared helper module exists at the expected path
    print()
    print("=== t10: shared helper module _runtime_flags.py exists ===")
    helper = os.path.join(
        REPO_ROOT, ".claude/features/rabbit-cage/hooks/_runtime_flags.py",
    )
    if os.path.isfile(helper):
        ok("_runtime_flags.py helper module exists at the canonical path")
    else:
        fail_t(f"helper module missing: {helper}")

    # t11: spec invariants 61 and 89 are present in spec.md
    print()
    print("=== t11: spec.md declares Inv 61 and Inv 62 ===")
    spec_path = os.path.join(REPO_ROOT, ".claude/features/rabbit-cage/docs/spec/spec.md")
    with open(spec_path) as f:
        spec_text = f.read()
    if "61. `sync-check.py`" in spec_text and "BYPASS-PERMISSIONS MODE ACTIVE" in spec_text:
        ok("spec.md declares Inv 61 (bypass-permissions Stop alert)")
    else:
        fail_t("Inv 61 (bypass-permissions Stop alert) missing or malformed in spec.md")
    if "62. `session-init.py`" in spec_text and "status-flags block" in spec_text:
        ok("spec.md declares Inv 62 (status-flags block in startup banner)")
    else:
        fail_t("Inv 62 (status-flags block) missing or malformed in spec.md")
finally:
    for d in tmproots:
        shutil.rmtree(d, ignore_errors=True)

print()
print(f"Results: {total - failures} passed, {failures} failed")
if failures == 0:
    print("ALL TESTS PASSED")
    sys.exit(0)
else:
    print(f"{failures} TEST(S) FAILED")
    sys.exit(1)
