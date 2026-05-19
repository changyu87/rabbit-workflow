#!/usr/bin/env python3
"""Tests /rabbit-config help subcommand (Inv 81-83).

Spec invariants covered:
- Inv 81: `/rabbit-config help` exits 0, writes only to stdout, modifies no file,
  prints illustrated usage naming every other subcommand AND `help` itself,
  with at least one concrete invocation example per subcommand. Extra args
  after `help` are ignored. Handler exists in scripts/rabbit-config.py and is
  registered in the subcommand dispatch table.
- Inv 82: `help` is advertised in BOTH (a) SKILL.md frontmatter `description`
  and (b) the in-script `USAGE` string.
- Inv 83: The illustrated `help` output is distinct from the terse error
  `USAGE` string: it adds per-subcommand purpose lines and at least one
  concrete invocation example per subcommand.
"""
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

# Every "other" subcommand the help must enumerate.
OTHER_SUBCMDS = [
    "prompt-threshold",
    "allowed-tools",
    "bash-allow",
    "permissions",
    "human-approval",
    "bypass-permissions",
]
# The full set including help itself.
ALL_SUBCMDS = OTHER_SUBCMDS + ["help"]

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
    return subprocess.run(
        [sys.executable, SKILL_PY] + args,
        cwd=cwd, capture_output=True, text=True,
    )


print("test-RABBIT-CAGE-rabbit-config-help.py")

# --- Sanity: source files exist ---
if not os.path.isfile(SKILL_PY):
    print(f"  FATAL: missing {SKILL_PY}")
    sys.exit(1)
if not os.path.isfile(SKILL_MD):
    print(f"  FATAL: missing {SKILL_MD}")
    sys.exit(1)

# Snapshot disk state of cwd before/after help invocation (t4 file-write check).
def snapshot(d):
    out = {}
    for root, _, files in os.walk(d):
        for fn in files:
            full = os.path.join(root, fn)
            try:
                st = os.stat(full)
                out[full] = (st.st_size, st.st_mtime_ns)
            except FileNotFoundError:
                pass
    return out


# ---- t1: help exits 0 ----
wd = tempfile.mkdtemp()
try:
    res = run_script(["help"], wd)
    if res.returncode == 0:
        ok(1, "rabbit-config help exits 0")
    else:
        fail_t(1, f"rabbit-config help exited rc={res.returncode} stderr={res.stderr!r}")
finally:
    shutil.rmtree(wd, ignore_errors=True)

# ---- t2: help names every subcommand including 'help' itself ----
wd = tempfile.mkdtemp()
try:
    res = run_script(["help"], wd)
    out = res.stdout
    missing = [s for s in ALL_SUBCMDS if s not in out]
    if not missing:
        ok(2, "help output names every subcommand (including 'help')")
    else:
        fail_t(2, f"help output missing subcommands: {missing}\nstdout={out!r}")
finally:
    shutil.rmtree(wd, ignore_errors=True)

# ---- t3: at least one concrete `/rabbit-config <subcmd>` example per subcommand ----
wd = tempfile.mkdtemp()
try:
    res = run_script(["help"], wd)
    out = res.stdout
    missing_examples = []
    for sub in OTHER_SUBCMDS:
        # Look for a line containing `/rabbit-config <sub>` followed by space
        # or end-of-line (i.e., used as a real example, not just enumeration).
        pat = re.compile(rf"/rabbit-config\s+{re.escape(sub)}(\s|$)")
        if not pat.search(out):
            missing_examples.append(sub)
    if not missing_examples:
        ok(3, "help output contains a concrete /rabbit-config <subcmd> example per subcommand")
    else:
        fail_t(3, f"help output missing concrete example for: {missing_examples}\nstdout={out!r}")
finally:
    shutil.rmtree(wd, ignore_errors=True)

# ---- t4: extra args after 'help' are ignored: exit 0 and same content ----
wd = tempfile.mkdtemp()
try:
    res1 = run_script(["help"], wd)
    res2 = run_script(["help", "foo", "bar"], wd)
    if res2.returncode == 0 and res1.stdout == res2.stdout:
        ok(4, "extra args after 'help' are ignored (exit 0, identical stdout)")
    else:
        fail_t(
            4,
            f"extra args changed behavior: rc1={res1.returncode} rc2={res2.returncode} "
            f"same_stdout={res1.stdout == res2.stdout}"
        )
finally:
    shutil.rmtree(wd, ignore_errors=True)

# ---- t5: help writes no files and writes nothing to stderr ----
wd = tempfile.mkdtemp()
try:
    # Seed a sentinel file so we can verify nothing else appears.
    sentinel = os.path.join(wd, "sentinel")
    with open(sentinel, "w") as f:
        f.write("x")
    before = snapshot(wd)
    res = run_script(["help"], wd)
    after = snapshot(wd)
    if before == after and res.stderr == "":
        ok(5, "help modifies no file and writes nothing to stderr")
    else:
        fail_t(
            5,
            f"help modified files or stderr: before==after={before == after} "
            f"stderr={res.stderr!r}"
        )
finally:
    shutil.rmtree(wd, ignore_errors=True)

# ---- t6: help output is NOT byte-identical to the script's USAGE string (Inv 83) ----
# Import USAGE from the script module to compare.
import importlib.util
spec = importlib.util.spec_from_file_location("rabbit_config_mod", SKILL_PY)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
USAGE = getattr(mod, "USAGE", None)

wd = tempfile.mkdtemp()
try:
    res = run_script(["help"], wd)
    help_out = res.stdout
    if USAGE is None:
        fail_t(6, "USAGE constant not exported by rabbit-config.py")
    elif help_out.rstrip("\n") != USAGE.rstrip("\n"):
        ok(6, "help output is distinct from terse USAGE string (Inv 83)")
    else:
        fail_t(6, "help output is byte-identical to USAGE — Inv 83 violation")
finally:
    shutil.rmtree(wd, ignore_errors=True)

# ---- t7: USAGE string itself names 'help' (Inv 82b) ----
if USAGE is not None and "help" in USAGE:
    # More strict: USAGE references /rabbit-config help (so error path names it).
    if re.search(r"/rabbit-config\s+help\b", USAGE):
        ok(7, "USAGE string names /rabbit-config help (Inv 82b)")
    else:
        fail_t(7, f"USAGE contains 'help' substring but not as a subcommand line: USAGE={USAGE!r}")
elif USAGE is None:
    fail_t(7, "USAGE not exported")
else:
    fail_t(7, "USAGE string does not name 'help' — Inv 82b violation")

# ---- t8: SKILL.md frontmatter description names 'help' (Inv 82a) ----
with open(SKILL_MD) as f:
    skill_text = f.read()
fm_match = re.match(r"^---\n(.*?)\n---", skill_text, re.DOTALL)
if not fm_match:
    fail_t(8, "SKILL.md missing YAML frontmatter")
else:
    fm = fm_match.group(1)
    desc_match = re.search(r"^description:\s*(.+)$", fm, re.MULTILINE)
    if not desc_match:
        fail_t(8, "SKILL.md frontmatter missing 'description' field")
    else:
        desc = desc_match.group(1)
        if "help" in desc:
            ok(8, "SKILL.md frontmatter description names 'help' (Inv 82a)")
        else:
            fail_t(8, f"SKILL.md frontmatter description omits 'help': {desc!r}")

# ---- t9: unknown subcommand path still names 'help' in its error USAGE output (Inv 82b) ----
wd = tempfile.mkdtemp()
try:
    res = run_script(["bogus-subcommand"], wd)
    # The error path prints USAGE to stderr (per existing main()), so 'help'
    # should appear in stderr.
    combined = (res.stdout or "") + (res.stderr or "")
    if res.returncode != 0 and "help" in combined:
        ok(9, "unknown subcommand error path names 'help' (Inv 82b)")
    else:
        fail_t(
            9,
            f"unknown subcommand path missing 'help' or returned 0: "
            f"rc={res.returncode} combined={combined!r}"
        )
finally:
    shutil.rmtree(wd, ignore_errors=True)

# ---- t10: dispatch table actually registers 'help' (Inv 81 last clause) ----
# Static check: source contains 'help' key in the dispatch dict.
with open(SKILL_PY) as f:
    src = f.read()
if re.search(r"['\"]help['\"]\s*:\s*cmd_help\b", src):
    ok(10, "dispatch table registers 'help' -> cmd_help (Inv 81)")
else:
    fail_t(10, "dispatch table does not register 'help' -> cmd_help — Inv 81 violation")

print()
print(f"Results: {pass_n} passed, {fail_n} failed")
sys.exit(0 if fail_n == 0 else 1)
