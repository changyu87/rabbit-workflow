#!/usr/bin/env python3
"""Wave-4 rabbit-cage bug cleanup tests.

Covers the cleanup of the open RABBIT-CAGE-BUG-19/32/35/36/39/41/42/44/45/46/
47/48/49/51/53/57/58/59/61/66/69/71/72/77/80/81/82/83 bug set in one TDD
cycle. Each `t<N>` block names the bug it pins.
"""
import json
import os
import re
import subprocess
import sys
import tempfile
import textwrap

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = subprocess.run(
    ["git", "-C", SCRIPT_DIR, "rev-parse", "--show-toplevel"],
    capture_output=True, text=True, check=True,
).stdout.strip()

CAGE = os.path.join(REPO_ROOT, ".claude/features/rabbit-cage")
HOOKS = os.path.join(CAGE, "hooks")
SCRIPTS = os.path.join(CAGE, "scripts")
TEST_DIR = os.path.join(CAGE, "test")
SKILL_DIR = os.path.join(CAGE, "skills/rabbit-config")

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


def read_bytes(p):
    with open(p, "rb") as f:
        return f.read()


print("test-RABBIT-CAGE-WAVE4-bug-cleanup.py")

# ---------------------------------------------------------------------------
# BUG-19: SKILL.md + rabbit-config.py docstring must not name a slash-command shim.
# ---------------------------------------------------------------------------
skill_md = read(os.path.join(SKILL_DIR, "SKILL.md"))
cfg_py = read(os.path.join(SKILL_DIR, "scripts/rabbit-config.py"))

if "commands/rabbit-config.md" not in skill_md:
    ok(1, "SKILL.md does not reference commands/rabbit-config.md (BUG-19)")
else:
    fail_t(1, "SKILL.md still references commands/rabbit-config.md (BUG-19)")

if "commands/rabbit-config.md" not in cfg_py:
    ok(2, "rabbit-config.py docstring does not reference commands/rabbit-config.md (BUG-19)")
else:
    fail_t(2, "rabbit-config.py docstring still references commands/rabbit-config.md (BUG-19)")

# ---------------------------------------------------------------------------
# BUG-32: workspace-tree.py contains no double-UTF-8 mojibake; decodes cleanly.
# ---------------------------------------------------------------------------
ws_bytes = read_bytes(os.path.join(SCRIPTS, "workspace-tree.py"))
mojibake_marker = b"\xc3\xa2\xc2\x94"  # double-encoded prefix of box-drawing chars
if mojibake_marker not in ws_bytes:
    ok(3, "workspace-tree.py contains no double-UTF-8 mojibake (BUG-32)")
else:
    fail_t(3, "workspace-tree.py still contains double-UTF-8 mojibake bytes (BUG-32)")

try:
    ws_bytes.decode("utf-8")
    ok(4, "workspace-tree.py decodes cleanly as UTF-8 (BUG-32)")
except UnicodeDecodeError:
    fail_t(4, "workspace-tree.py does not decode as UTF-8 (BUG-32)")

# ---------------------------------------------------------------------------
# BUG-35: README.md does not reference dead .sh scripts or removed features.
# ---------------------------------------------------------------------------
readme = read(os.path.join(CAGE, "README.md"))
dead = ("file-bug.sh", "feature-scaffolder", "rabbit-breeder",
        "new-feature.sh", "breeder/spec.md")
remaining = [d for d in dead if d in readme]
if not remaining:
    ok(5, "README.md does not reference dead .sh scripts / removed features (BUG-35)")
else:
    fail_t(5, f"README.md still references: {remaining} (BUG-35)")

# ---------------------------------------------------------------------------
# BUG-36: test-hook-rename.py removed; run.py wires all live test files.
# ---------------------------------------------------------------------------
if not os.path.exists(os.path.join(TEST_DIR, "test-hook-rename.py")):
    ok(6, "stale test-hook-rename.py removed (BUG-36)")
else:
    fail_t(6, "test-hook-rename.py still present (BUG-36)")

run_py = read(os.path.join(TEST_DIR, "run.py"))
all_tests = sorted(
    name for name in os.listdir(TEST_DIR)
    if name.startswith("test-") and name.endswith(".py")
)
missing = [name for name in all_tests if f'"{name}"' not in run_py]
if not missing:
    ok(7, "run.py wires every test-*.py file (BUG-36)")
else:
    fail_t(7, f"run.py missing entries for: {missing} (BUG-36)")

# ---------------------------------------------------------------------------
# BUG-39: No test file creates generate-skills-dir.sh in a temp tree.
# ---------------------------------------------------------------------------
sh_creators = []
for name in all_tests:
    body = read(os.path.join(TEST_DIR, name))
    if 'generate-skills-dir.sh' in body and ('open(' in body or 'write_text' in body):
        # Only flag if there is an actual write (not a comment naming the file).
        if re.search(r"open\([^)]*generate-skills-dir\.sh", body):
            sh_creators.append(name)
if not sh_creators:
    ok(8, "no test creates a generate-skills-dir.sh stub (BUG-39)")
else:
    fail_t(8, f"tests still create generate-skills-dir.sh: {sh_creators} (BUG-39)")

# ---------------------------------------------------------------------------
# BUG-41: contract.md does not list rabbit-config.md under provides.commands.
# ---------------------------------------------------------------------------
contract = read(os.path.join(CAGE, "docs/spec/contract.md"))
if 'commands/rabbit-config.md' not in contract:
    ok(9, "contract.md no longer lists commands/rabbit-config.md (BUG-41)")
else:
    fail_t(9, "contract.md still lists commands/rabbit-config.md (BUG-41)")

# ---------------------------------------------------------------------------
# BUG-42: install.py docstring no longer claims to copy
# .claude/docs/specs/.claude/docs/plans on --all.
# ---------------------------------------------------------------------------
install_py = read(os.path.join(CAGE, "install.py"))
if "stripped" in install_py.lower() and "docs/specs" in install_py:
    ok(10, "install.py docstring describes --all behaviour correctly (BUG-42)")
else:
    fail_t(10, "install.py docstring does not describe --all behaviour correctly (BUG-42)")

# ---------------------------------------------------------------------------
# BUG-44 / BUG-81: build-targets.py only logs [built] on actual copies, and
# writes the skills marker for any destination under .claude/skills/.
# ---------------------------------------------------------------------------
bt_py = read(os.path.join(SCRIPTS, "build.py"))
if "[no-op]" in bt_py and "content_changed" in bt_py:
    ok(11, "build.py prints [no-op] for unchanged copies (BUG-44)")
else:
    fail_t(11, "build.py still prints [built] unconditionally (BUG-44)")

if re.search(r"\.claude/skills/\(\[\^/\]\+\)/", bt_py) and "SKILL\\.md" not in bt_py.split(".rabbit-skills-updated")[-1]:
    ok(12, "build.py marker write covers any skills/<name>/ destination (BUG-81)")
else:
    # Fallback check: the regex must not restrict to /SKILL.md$.
    if re.search(r"\.claude/skills/\(\[\^/\]\+\)/'", bt_py) is None and "SKILL\\.md$" in bt_py:
        fail_t(12, "build.py marker still restricted to SKILL.md target (BUG-81)")
    else:
        ok(12, "build.py marker write widened beyond SKILL.md (BUG-81)")

# ---------------------------------------------------------------------------
# BUG-45: rabbit-project-consolidate.py exits non-zero on warnings.
# ---------------------------------------------------------------------------
tmpd = tempfile.mkdtemp()
try:
    pmap = os.path.join(tmpd, "project-map.json")
    reg = os.path.join(tmpd, "registry.json")
    with open(pmap, "w") as f:
        json.dump({"source_map": {"src/a": "ghost-feature"}}, f)
    with open(reg, "w") as f:
        json.dump({"features": {}}, f)
    rc = subprocess.call(
        [sys.executable, os.path.join(SCRIPTS, "rabbit-project-consolidate.py"),
         pmap, reg, "proj"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    if rc == 1:
        ok(13, "rabbit-project-consolidate.py exits 1 on warnings (BUG-45)")
    else:
        fail_t(13, f"rabbit-project-consolidate.py exited {rc} on warnings (BUG-45)")
finally:
    import shutil
    shutil.rmtree(tmpd, ignore_errors=True)

# ---------------------------------------------------------------------------
# BUG-46: workspace-tree.py annotations do not reference dead .sh files.
# ---------------------------------------------------------------------------
ws_text = ws_bytes.decode("utf-8")
dead_sh = ("file-bug.sh", "bug-status.sh", "list-bugs.sh",
           "file-backlog-item.py")  # last one references removed rabbit-backlog feature
hits = [s for s in dead_sh if s in ws_text]
if not hits:
    ok(14, "workspace-tree.py annotations do not reference dead scripts (BUG-46)")
else:
    fail_t(14, f"workspace-tree.py still references dead scripts: {hits} (BUG-46)")

# ---------------------------------------------------------------------------
# BUG-47: sync-check.py uses narrow exceptions for generate failures.
# ---------------------------------------------------------------------------
sc_py = read(os.path.join(HOOKS, "sync-check.py"))
# Find the block that runs generate_script and check the except clause.
m = re.search(r"subprocess\.check_output\([\s\S]+?generate_script[\s\S]+?\)\.decode\(\)\s*\n\s*except\s+([^:\n]+):", sc_py)
if m and "Exception" != m.group(1).strip() and "FileNotFoundError" in m.group(1):
    ok(15, "sync-check.py uses narrow exceptions for generate failures (BUG-47)")
else:
    fail_t(15, f"sync-check.py still uses broad/bare except for generate failures (BUG-47); got: {m.group(1) if m else 'no match'}")

# ---------------------------------------------------------------------------
# BUG-48: most-used scripts (session-init, sync-check, scope-guard) emit help.
# ---------------------------------------------------------------------------
for t, script in [(16, "hooks/session-init.py"),
                  (17, "hooks/sync-check.py"),
                  (18, "hooks/scope-guard.py")]:
    res = subprocess.run(
        [sys.executable, os.path.join(CAGE, script), "--help"],
        capture_output=True, text=True, input="",
    )
    if res.returncode == 0 and len(res.stdout.strip()) > 0:
        ok(t, f"{script} responds to --help (BUG-48)")
    else:
        fail_t(t, f"{script} --help missing or non-zero exit (BUG-48); stdout={res.stdout!r}")

# ---------------------------------------------------------------------------
# BUG-51: feature.json surface has no 'scripts' field (spec-defined keys only).
# ---------------------------------------------------------------------------
fj = json.loads(read(os.path.join(CAGE, "feature.json")))
if "scripts" not in fj.get("surface", {}):
    ok(19, "feature.json surface.scripts removed (BUG-51)")
else:
    fail_t(19, "feature.json still has surface.scripts (BUG-51)")

# ---------------------------------------------------------------------------
# BUG-53 (post-BUG-97 revert): rabbit-config.py human-approval false is
# idempotent — no rewrite when the marker exists. (Subcommand restored to
# 'human-approval' with the original semantics: 'false' writes/keeps the
# marker (bypass ACTIVE); 'true' removes (gate ACTIVE).)
# ---------------------------------------------------------------------------
tmpd2 = tempfile.mkdtemp()
try:
    marker = os.path.join(tmpd2, ".rabbit-human-approval-bypass")
    with open(marker, "w") as f:
        f.write("INITIAL-SENTINEL")
    initial_mtime = os.stat(marker).st_mtime
    import time as _t
    _t.sleep(0.05)
    res = subprocess.run(
        [sys.executable, os.path.join(SKILL_DIR, "scripts/rabbit-config.py"),
         "human-approval", "false"],
        cwd=tmpd2, capture_output=True, text=True,
    )
    after = read(marker)
    if after == "INITIAL-SENTINEL" and "already" in res.stdout.lower():
        ok(20, "human-approval false is idempotent — marker not rewritten (BUG-53)")
    else:
        fail_t(20, f"human-approval false rewrote marker (BUG-53); content={after!r}, out={res.stdout!r}")
finally:
    import shutil
    shutil.rmtree(tmpd2, ignore_errors=True)

# ---------------------------------------------------------------------------
# BUG-54: helper scripts emit usage + exit 2 on missing argv.
# ---------------------------------------------------------------------------
for t, script in [(21, "scripts/rabbit-project-consolidate.py")]:
    res = subprocess.run(
        [sys.executable, os.path.join(CAGE, script)],
        capture_output=True, text=True,
    )
    if res.returncode == 2 and ("usage" in res.stderr.lower() or "usage" in res.stdout.lower()):
        ok(t, f"{script} exits 2 with usage on missing argv (BUG-54)")
    else:
        fail_t(t, f"{script} missing-argv handling wrong (rc={res.returncode}, err={res.stderr!r})")

# ---------------------------------------------------------------------------
# BUG-57: scope-guard.py normalizes paths through realpath.
# ---------------------------------------------------------------------------
sg_py = read(os.path.join(HOOKS, "scope-guard.py"))
if "realpath" in sg_py:
    ok(23, "scope-guard.py uses realpath for REPO_ROOT/abspath (BUG-57)")
else:
    fail_t(23, "scope-guard.py does not normalize with realpath (BUG-57)")

# ---------------------------------------------------------------------------
# BUG-58: scope-guard-on.py does not use .parent*4 fallback.
# ---------------------------------------------------------------------------
sgo_py = read(os.path.join(SCRIPTS, "scope-guard-on.py"))
# Only count non-comment lines (allow the bug to be named in a comment).
sgo_code = "\n".join(ln for ln in sgo_py.splitlines() if not ln.strip().startswith("#"))
if ".parent.parent.parent.parent" not in sgo_code:
    ok(24, "scope-guard-on.py does not use brittle .parent*4 chain (BUG-58)")
else:
    fail_t(24, "scope-guard-on.py still uses brittle .parent*4 chain (BUG-58)")

# ---------------------------------------------------------------------------
# BUG-59: session-init.py and refresh.py do not use lstrip('./') on import paths.
# ---------------------------------------------------------------------------
si_py = read(os.path.join(HOOKS, "session-init.py"))
rf_py = read(os.path.join(HOOKS, "refresh.py"))


def _strip_comments(text):
    return "\n".join(ln for ln in text.splitlines() if not ln.strip().startswith("#"))


si_code = _strip_comments(si_py)
rf_code = _strip_comments(rf_py)
if "lstrip(\"./\")" not in si_code and "lstrip('./')" not in si_code:
    ok(25, "session-init.py does not use lstrip('./') in code (BUG-59)")
else:
    fail_t(25, "session-init.py still uses lstrip('./') in code (BUG-59)")
if "lstrip(\"./\")" not in rf_code and "lstrip('./')" not in rf_code:
    ok(26, "refresh.py does not use lstrip('./') in code (BUG-59)")
else:
    fail_t(26, "refresh.py still uses lstrip('./') in code (BUG-59)")

# Behavioural check: an @-import like '.claude/foo.md' must resolve under
# root + .claude/foo.md, not root + claude/foo.md (the lstrip bug).
tmpd3 = tempfile.mkdtemp()
try:
    os.makedirs(os.path.join(tmpd3, ".claude/features/policy"))
    target_file = os.path.join(tmpd3, ".claude/leading-dot-import.md")
    with open(target_file, "w") as f:
        f.write("SENTINEL-DOTPATH-CONTENT\n")
    with open(os.path.join(tmpd3, "CLAUDE.md"), "w") as f:
        f.write("# header\n\n@.claude/leading-dot-import.md\n")
    env = {**os.environ, "RABBIT_ROOT": tmpd3}
    res = subprocess.run(
        [sys.executable, os.path.join(HOOKS, "session-init.py")],
        capture_output=True, text=True, env=env, input="",
    )
    if "SENTINEL-DOTPATH-CONTENT" in res.stdout:
        ok(27, "session-init.py resolves @.claude/* import paths correctly (BUG-59)")
    else:
        fail_t(27, f"session-init.py did not load @.claude/* import (BUG-59); stdout={res.stdout[:200]!r}")
finally:
    import shutil
    shutil.rmtree(tmpd3, ignore_errors=True)

# ---------------------------------------------------------------------------
# BUG-61: install.py cleans up partial .claude/ on failure.
# ---------------------------------------------------------------------------
if "shutil.rmtree(target_claude" in install_py:
    ok(28, "install.py rolls back partial .claude/ on build failure (BUG-61)")
else:
    fail_t(28, "install.py does not roll back partial .claude/ on build failure (BUG-61)")

# ---------------------------------------------------------------------------
# BUG-66: rabbit-config.py allowed-tools / bash-allow remove-of-absent does
# not write a {"permissions":{"allow":[]}} empty structure to disk.
# ---------------------------------------------------------------------------
tmpd4 = tempfile.mkdtemp()
try:
    os.makedirs(os.path.join(tmpd4, ".claude"))
    res = subprocess.run(
        [sys.executable, os.path.join(SKILL_DIR, "scripts/rabbit-config.py"),
         "allowed-tools", "remove", "DoesNotExist"],
        cwd=tmpd4, capture_output=True, text=True,
    )
    local = os.path.join(tmpd4, ".claude/settings.local.json")
    if not os.path.isfile(local):
        ok(29, "allowed-tools remove-of-absent does not create settings.local.json (BUG-66)")
    else:
        content = read(local)
        # An empty {} is acceptable; a {"permissions": {"allow": []}} stub is not.
        if "permissions" not in content:
            ok(29, "allowed-tools remove-of-absent does not write 'permissions' stub (BUG-66)")
        else:
            fail_t(29, f"allowed-tools remove-of-absent wrote 'permissions' stub (BUG-66); content={content!r}")
finally:
    import shutil
    shutil.rmtree(tmpd4, ignore_errors=True)

# ---------------------------------------------------------------------------
# BUG-69 retired (RABBIT-CAGE-BACKLOG-25 part 4): the legacy `updated_note`
# field has been dropped from rabbit-cage feature.json — maintenance cadence
# for the `updated` field belongs in a repo-level contributor note, not in
# per-feature feature.json payloads. The absence of the field is enforced by
# Inv 93 and the housekeeping test (test-RABBIT-CAGE-BACKLOG-28-housekeeping.py).
# ---------------------------------------------------------------------------
if "updated_note" not in fj:
    ok(30, "feature.json no longer carries the legacy 'updated_note' field (Inv 93)")
else:
    fail_t(30, "feature.json still carries the deprecated 'updated_note' field — drop per Inv 93")

# ---------------------------------------------------------------------------
# BUG-71 retired (RABBIT-CAGE-BACKLOG-26): new-feature.py moved into the
# rabbit-feature feature. The scaffolded-contract.md structure check is
# covered at .claude/features/rabbit-feature/test/test-new-feature.py.
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# BUG-72: scope-guard heredoc regex handles indented closing delimiter.
# Functional check: an indented heredoc body containing '>foo' should not
# extract 'foo' as a write target.
# ---------------------------------------------------------------------------
from importlib.util import spec_from_file_location, module_from_spec
spec = spec_from_file_location("scope_guard_mod", os.path.join(HOOKS, "scope-guard.py"))
sg_mod = module_from_spec(spec)
spec.loader.exec_module(sg_mod)

indented_cmd = (
    "cat <<-EOF\n"
    "\t> /etc/passwd\n"
    "\tEOF\n"
)
targets = sg_mod.extract_bash_targets(indented_cmd)
if "/etc/passwd" not in targets:
    ok(32, "scope-guard heredoc regex strips <<- indented heredoc body (BUG-72)")
else:
    fail_t(32, f"scope-guard still mis-extracts indented heredoc body: {targets} (BUG-72)")

# ---------------------------------------------------------------------------
# BUG-77: rabbit-config.py listing path does not create settings.local.json.
# ---------------------------------------------------------------------------
tmpd6 = tempfile.mkdtemp()
try:
    os.makedirs(os.path.join(tmpd6, ".claude"))
    subprocess.run(
        [sys.executable, os.path.join(SKILL_DIR, "scripts/rabbit-config.py"),
         "allowed-tools"],
        cwd=tmpd6, capture_output=True, text=True,
    )
    subprocess.run(
        [sys.executable, os.path.join(SKILL_DIR, "scripts/rabbit-config.py"),
         "bash-allow"],
        cwd=tmpd6, capture_output=True, text=True,
    )
    local = os.path.join(tmpd6, ".claude/settings.local.json")
    if not os.path.isfile(local):
        ok(33, "list operations do not create settings.local.json (BUG-77)")
    else:
        fail_t(33, "list operations created settings.local.json (BUG-77)")
finally:
    import shutil
    shutil.rmtree(tmpd6, ignore_errors=True)

# ---------------------------------------------------------------------------
# BUG-80: refresh.py inline rabbit-policy-start/end detection removed.
# ---------------------------------------------------------------------------
if "rabbit-policy-start" not in rf_code and "rabbit-policy-end" not in rf_code:
    ok(34, "refresh.py inline policy-marker detection removed from code (BUG-80)")
else:
    fail_t(34, "refresh.py still contains dead inline policy-marker detection (BUG-80)")

# ---------------------------------------------------------------------------
# BUG-82: validate-all.py default root resolution — obsolete after BACKLOG-24.
# The script was deleted (BACKLOG-24 — feature-audit now owned by
# rabbit-feature-audit skill in rabbit-feature). The BUG-82 invariant is
# preserved here as an absence assertion so the deletion is verified.
# ---------------------------------------------------------------------------
if not os.path.exists(os.path.join(SCRIPTS, "validate-all.py")):
    ok(35, "validate-all.py removed (BACKLOG-24 supersedes BUG-82)")
else:
    fail_t(35, "validate-all.py should be deleted (BACKLOG-24)")

# ---------------------------------------------------------------------------
# BUG-83: scope-guard.py imports sys only once.
# ---------------------------------------------------------------------------
sys_imports = re.findall(r"(?m)^\s*import\s+sys\b", sg_py)
if len(sys_imports) == 1:
    ok(36, "scope-guard.py imports sys exactly once (BUG-83)")
else:
    fail_t(36, f"scope-guard.py imports sys {len(sys_imports)} times (BUG-83)")

# ---------------------------------------------------------------------------
# BUG-49: no .pyc files committed to git under rabbit-cage.
# ---------------------------------------------------------------------------
ls = subprocess.run(
    ["git", "-C", REPO_ROOT, "ls-files", ".claude/features/rabbit-cage"],
    capture_output=True, text=True,
)
tracked_pyc = [p for p in ls.stdout.splitlines() if p.endswith(".pyc")]
if not tracked_pyc:
    ok(37, "no .pyc files tracked under rabbit-cage (BUG-49)")
else:
    fail_t(37, f"tracked .pyc files: {tracked_pyc} (BUG-49)")

print()
print(f"Results: {pass_n} passed, {fail_n} failed")
sys.exit(0 if fail_n == 0 else 1)
