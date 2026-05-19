#!/usr/bin/env python3
"""E2E tests for rabbit-cage Wave 2 Invariants 61-65.

Inv 61: session-init.py implements R1 branch enforcement (on-main path
        creates session/YYYYMMDD-HHMMSS branch + green systemMessage; off-main
        path is a no-op).
Inv 62: sync-check.py surface-drift alert MUST be RED (\\x1b[31m).
Inv 63: sync-check.py first-run/drift additionalContext MUST either expand
        @-imports OR contain a clear note that @-imports are not auto-followed.
Inv 64: rabbit-cage tests MUST NOT mutate live source files in
        .claude/features/rabbit-cage/ without restoring them.
Inv 65: scope-guard.py MUST DENY (exit 2) when active per-feature or global
        scope marker names an unresolvable feature.

Every test uses isolated temporary directories — no live source mutation.
"""
import hashlib
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

SESSION_INIT = os.path.join(REPO_ROOT, ".claude/features/rabbit-cage/hooks/session-init.py")
SYNC_CHECK = os.path.join(REPO_ROOT, ".claude/features/rabbit-cage/hooks/sync-check.py")
SCOPE_GUARD = os.path.join(REPO_ROOT, ".claude/features/rabbit-cage/hooks/scope-guard.py")
HOOK_ENFORCEMENT = os.path.join(REPO_ROOT, ".claude/features/rabbit-cage/test/test-hook-enforcement.py")
TEAM_WIDE = os.path.join(REPO_ROOT, ".claude/features/rabbit-cage/test/test-team-wide-permissions.py")

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


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def make_repo(initial_branch="main"):
    """Create an isolated git repo with minimal CLAUDE.md fixture."""
    d = tempfile.mkdtemp(prefix="rabbit-cage-wave2-")
    subprocess.run(["git", "init", "-q", d], check=True)
    subprocess.run(["git", "-C", d, "config", "user.email", "test@test.com"], check=True)
    subprocess.run(["git", "-C", d, "config", "user.name", "Test"], check=True)
    subprocess.run(["git", "-C", d, "checkout", "-q", "-b", initial_branch], capture_output=True)
    with open(os.path.join(d, "placeholder"), "w") as f:
        f.write("x\n")
    with open(os.path.join(d, "CLAUDE.md"), "w") as f:
        f.write("# Test\n@.claude/features/policy/philosophy.md\n")
    os.makedirs(os.path.join(d, ".claude", "features", "policy"), exist_ok=True)
    with open(os.path.join(d, ".claude/features/policy/philosophy.md"), "w") as f:
        f.write("# Philosophy\nMachine First.\n")
    subprocess.run(["git", "-C", d, "add", "-A"], check=True, capture_output=True)
    subprocess.run(["git", "-C", d, "commit", "-q", "-m", "init"], check=True, capture_output=True)
    return d


print("test-RABBIT-CAGE-WAVE2-inv61-65.py")
print()

tmproots = []

try:
    # ====================================================================
    # Inv 61 — session-init.py R1 branch enforcement
    # ====================================================================
    print("=== Inv 61: session-init.py R1 branch enforcement ===")

    # t1: on main → creates session/YYYYMMDD-HHMMSS branch
    repo_main = make_repo(initial_branch="main")
    tmproots.append(repo_main)
    env = {**os.environ, "RABBIT_ROOT": repo_main}
    res = subprocess.run([sys.executable, SESSION_INIT], env=env, cwd=repo_main,
                         capture_output=True, text=True)
    branch = subprocess.run(
        ["git", "-C", repo_main, "branch", "--show-current"],
        capture_output=True, text=True,
    ).stdout.strip()
    if re.match(r"^session/\d{8}-\d{6}$", branch):
        ok(f"on main → created branch matching session/YYYYMMDD-HHMMSS ({branch})")
    else:
        fail_t(f"on main → expected session/YYYYMMDD-HHMMSS branch, got '{branch}' (Inv 61)")

    # t2: emitted JSON contains green [rabbit] systemMessage naming the branch
    sys_msg_found = False
    branch_named = False
    try:
        # session-init.py may emit multiple JSON objects; scan all
        for line in res.stdout.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                d = json.loads(line)
            except Exception:
                continue
            msg = d.get("systemMessage", "")
            if "\x1b[32m" in msg and "[🐇 rabbit 🐇]" in msg:
                sys_msg_found = True
                if branch in msg or "R1" in msg or "session/" in msg:
                    branch_named = True
    except Exception:
        pass
    if sys_msg_found and branch_named:
        ok("on main → emitted green [rabbit] systemMessage naming the new branch (Inv 61)")
    else:
        fail_t(f"on main → missing green [rabbit] systemMessage naming branch; stdout={res.stdout!r}, stderr={res.stderr!r} (Inv 61)")

    # t3: off-main → no branch change
    repo_feat = make_repo(initial_branch="feature/keep")
    tmproots.append(repo_feat)
    env = {**os.environ, "RABBIT_ROOT": repo_feat}
    subprocess.run([sys.executable, SESSION_INIT], env=env, cwd=repo_feat,
                   capture_output=True, text=True)
    branch_after = subprocess.run(
        ["git", "-C", repo_feat, "branch", "--show-current"],
        capture_output=True, text=True,
    ).stdout.strip()
    if branch_after == "feature/keep":
        ok("off-main → no-op, branch unchanged (Inv 61)")
    else:
        fail_t(f"off-main → expected 'feature/keep', got '{branch_after}' (Inv 61)")

    # ====================================================================
    # Inv 62 — surface-drift alert color is RED (sourced from the print
    # registry, BACKLOG-19). Verify the registry entry has color=red.
    # ====================================================================
    print()
    print("=== Inv 62: surface-drift alert is RED (via rabbit-print-messages.json) ===")
    registry_path = os.path.join(
        REPO_ROOT, ".claude/features/contract/schemas/rabbit-print-messages.json",
    )
    try:
        with open(registry_path) as f:
            registry = json.load(f)
        surface_color = registry.get("messages", {}).get("surface-drift", {}).get("color")
        if surface_color == "red":
            ok("rabbit-print-messages.json declares surface-drift color=red (Inv 62)")
        else:
            fail_t(f"surface-drift color is {surface_color!r}, expected 'red' (Inv 62)")
    except Exception as e:
        fail_t(f"could not load rabbit-print-messages.json: {e}")

    # ====================================================================
    # Inv 63 — sync-check.py additionalContext expands @-imports OR contains note.
    # BACKLOG-19: first-run path removed; the drift path is the only emitter
    # of additionalContext, so we corrupt an existing CLAUDE.md to force drift.
    # ====================================================================
    print()
    print("=== Inv 63: sync-check.py additionalContext handles @-imports (drift path) ===")
    tmp_drift = tempfile.mkdtemp(prefix="rabbit-cage-wave2-drift-")
    tmproots.append(tmp_drift)
    subprocess.run(["git", "init", "-q", tmp_drift], check=True)
    subprocess.run(["git", "-C", tmp_drift, "config", "user.email", "t@t"], check=True)
    subprocess.run(["git", "-C", tmp_drift, "config", "user.name", "t"], check=True)
    os.makedirs(os.path.join(tmp_drift, ".claude/features/rabbit-cage/scripts"), exist_ok=True)
    os.makedirs(os.path.join(tmp_drift, ".claude/features/policy"), exist_ok=True)
    for fname, content in [
        ("philosophy.md", "# Philosophy\nMachine First.\n"),
        ("spec-rules.md", "# Spec Rules\nSpec.\n"),
        ("coding-rules.md", "# Coding Rules\nCode.\n"),
    ]:
        with open(os.path.join(tmp_drift, ".claude/features/policy", fname), "w") as f:
            f.write(content)
    with open(os.path.join(tmp_drift, ".claude/features/rabbit-cage/policy-header.json"), "w") as f:
        json.dump({"header": "# Rabbit Workflow — test header"}, f)
    for fname in ("generate-claude-md.py", "generate-claude-md-header.py"):
        shutil.copy(
            os.path.join(REPO_ROOT, ".claude/features/rabbit-cage/scripts", fname),
            os.path.join(tmp_drift, ".claude/features/rabbit-cage/scripts", fname),
        )
    # Force the drift path: write a stale CLAUDE.md.
    with open(os.path.join(tmp_drift, "CLAUDE.md"), "w") as f:
        f.write("STALE CONTENT — will be regenerated\n")
    env = {**os.environ, "RABBIT_ROOT": tmp_drift, "RABBIT_SYNC_EVERY": "1"}
    res = subprocess.run([sys.executable, SYNC_CHECK], env=env,
                         capture_output=True, text=True)
    addl_ctx = ""
    try:
        d = json.loads(res.stdout)
        addl_ctx = d.get("additionalContext", "")
    except Exception:
        pass

    if addl_ctx:
        bare_at_lines = [
            ln for ln in addl_ctx.splitlines()
            if re.match(r"^@\S+", ln.strip())
        ]
        has_warning = bool(
            re.search(r"NOTE.*@.?import|not\s+(auto-)?resolv|not\s+(auto-)?follow|load.*referenced",
                       addl_ctx, re.IGNORECASE)
        )
        if not bare_at_lines:
            ok("additionalContext contains no bare unresolved @-import lines (Inv 63 — expansion path)")
        elif has_warning:
            ok("additionalContext contains bare @-imports BUT also includes a warning note (Inv 63 — note path)")
        else:
            fail_t(f"additionalContext contains bare @-import lines without a warning note: {bare_at_lines!r} (Inv 63 violation)")
    else:
        fail_t(f"sync-check.py drift did NOT emit additionalContext; stdout={res.stdout!r} (Inv 63 cannot be checked)")

    # ====================================================================
    # Inv 64 — tests do not mutate live source files
    # ====================================================================
    print()
    print("=== Inv 64: rabbit-cage tests do not mutate live source files ===")

    # Snapshot key live source files before running the historically-mutating tests
    # twice, then assert byte-identical.
    targets = {
        "settings.json": os.path.join(REPO_ROOT, ".claude/features/rabbit-cage/settings.json"),
        "feature.json": os.path.join(REPO_ROOT, ".claude/features/rabbit-cage/feature.json"),
    }
    pre = {k: sha256_file(p) for k, p in targets.items() if os.path.isfile(p)}

    # Run test-hook-enforcement.py and test-team-wide-permissions.py (the two
    # offenders identified in BUG-40). Use a separate work dir so cwd is not
    # polluted.
    work = tempfile.mkdtemp(prefix="rabbit-cage-wave2-work-")
    tmproots.append(work)
    for label, path in (("test-hook-enforcement.py", HOOK_ENFORCEMENT),
                        ("test-team-wide-permissions.py", TEAM_WIDE)):
        if os.path.isfile(path):
            subprocess.run([sys.executable, path], cwd=work,
                           capture_output=True, text=True)

    post = {k: sha256_file(p) for k, p in targets.items() if os.path.isfile(p)}
    drifted = [k for k in pre if pre[k] != post.get(k)]
    if not drifted:
        ok("test-hook-enforcement.py and test-team-wide-permissions.py left live source files byte-identical (Inv 64)")
    else:
        fail_t(f"live source files mutated by tests (Inv 64 violation): {drifted}")

    # ====================================================================
    # Inv 65 — scope-guard DENIES writes for unresolvable scope markers
    # ====================================================================
    print()
    print("=== Inv 65: scope-guard.py DENIES writes for unresolvable scope marker ===")

    # Setup: create an isolated repo mirror with the scope-guard wired up.
    # Simpler approach: create a per-feature marker for a name that
    # find-feature.py cannot resolve, then attempt a write. Because the test
    # must not mutate live state, we create the marker file in a tmp repo and
    # invoke scope-guard.py with RABBIT_ROOT pointing to it.
    # But scope-guard.py derives REPO_ROOT from `git rev-parse --show-toplevel`
    # at import time and from its own __file__, NOT from RABBIT_ROOT.
    # So we must copy scope-guard.py + find-feature.py into a tmp git repo and
    # invoke from there.
    tmp_sg = tempfile.mkdtemp(prefix="rabbit-cage-wave2-sg-")
    tmproots.append(tmp_sg)
    subprocess.run(["git", "init", "-q", tmp_sg], check=True)
    subprocess.run(["git", "-C", tmp_sg, "config", "user.email", "t@t"], check=True)
    subprocess.run(["git", "-C", tmp_sg, "config", "user.name", "t"], check=True)
    # Wire minimal scope-guard + find-feature path layout.
    sg_dir = os.path.join(tmp_sg, ".claude/features/rabbit-cage/hooks")
    ff_dir = os.path.join(tmp_sg, ".claude/features/contract/scripts")
    os.makedirs(sg_dir, exist_ok=True)
    os.makedirs(ff_dir, exist_ok=True)
    shutil.copy(SCOPE_GUARD, os.path.join(sg_dir, "scope-guard.py"))
    src_ff = os.path.join(REPO_ROOT, ".claude/features/contract/scripts/find-feature.py")
    if os.path.isfile(src_ff):
        shutil.copy(src_ff, os.path.join(ff_dir, "find-feature.py"))
    # Create one real feature so find-feature can be exercised.
    real_dir = os.path.join(tmp_sg, ".claude/features/realfeat")
    os.makedirs(real_dir, exist_ok=True)
    with open(os.path.join(real_dir, "feature.json"), "w") as f:
        json.dump({"name": "realfeat", "tdd_state": "test-red"}, f)
    # Initial commit
    with open(os.path.join(tmp_sg, "placeholder"), "w") as f:
        f.write("x\n")
    subprocess.run(["git", "-C", tmp_sg, "add", "-A"], check=True, capture_output=True)
    subprocess.run(["git", "-C", tmp_sg, "commit", "-q", "-m", "init"], check=True, capture_output=True)

    sg_path = os.path.join(sg_dir, "scope-guard.py")

    # t-65a: per-feature marker for nonexistent feature → DENY
    marker_path = os.path.join(tmp_sg, ".rabbit-scope-active-nonexistent")
    open(marker_path, "a").close()
    target_path = os.path.join(tmp_sg, ".claude/features/realfeat/somefile.txt")
    payload = json.dumps({
        "tool_name": "Write",
        "tool_input": {"file_path": target_path},
    })
    res = subprocess.run([sys.executable, sg_path], input=payload,
                         capture_output=True, text=True, cwd=tmp_sg)
    deny_msg = res.stderr
    os.unlink(marker_path)

    if res.returncode == 2:
        ok("scope-guard exits 2 (DENY) for write when per-feature marker names unresolvable feature (Inv 65)")
    else:
        fail_t(f"scope-guard exited {res.returncode} (expected 2/DENY) for unresolvable per-feature marker; stderr={deny_msg!r} (Inv 65 violation)")

    if "nonexistent" in deny_msg:
        ok("DENY message names the unresolvable feature 'nonexistent' (Inv 65)")
    else:
        fail_t(f"DENY message does NOT name 'nonexistent'; stderr={deny_msg!r} (Inv 65)")

    # t-65b: global marker pointing to nonexistent feature → DENY
    marker_path = os.path.join(tmp_sg, ".rabbit-scope-active")
    with open(marker_path, "w") as f:
        f.write("nonexistent")
    target_path = os.path.join(tmp_sg, ".claude/features/realfeat/somefile.txt")
    payload = json.dumps({
        "tool_name": "Write",
        "tool_input": {"file_path": target_path},
    })
    res2 = subprocess.run([sys.executable, sg_path], input=payload,
                          capture_output=True, text=True, cwd=tmp_sg)
    os.unlink(marker_path)

    # Spec says either marker form must DENY when unresolvable. Global marker
    # currently flows through the walk_up_find path and may ALLOW silently if
    # find_feature_path returns None.
    if res2.returncode == 2 and "nonexistent" in res2.stderr:
        ok("scope-guard exits 2 (DENY) for write when global marker names unresolvable feature (Inv 65)")
    else:
        fail_t(f"global marker unresolvable-feature did NOT DENY: rc={res2.returncode}, stderr={res2.stderr!r} (Inv 65 violation)")

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
