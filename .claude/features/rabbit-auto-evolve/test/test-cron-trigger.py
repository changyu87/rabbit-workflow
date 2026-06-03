#!/usr/bin/env python3
"""test-cron-trigger.py — e2e tests for scripts/install-cron.py and
scripts/uninstall-cron.py (Inv 32 / issue #414: system cron is the sole
tick scheduler).

These tests MUST NOT touch the real user crontab. Both scripts shell out to
the `crontab` binary via the `RABBIT_CRONTAB_CMD` env override; the tests
point that override at a fake `crontab` shim (a tiny Python program) whose
"crontab" is a plain file in a tempdir. The shim implements exactly the two
forms the scripts use:
  - `crontab -l`  → print the file contents (exit 1 + empty when absent, the
    real crontab behaviour for "no crontab for user")
  - `crontab -`   → overwrite the file from stdin

Scenarios:
  A) install-cron.py from empty crontab → one tick-headless entry appears.
  B) install-cron.py is idempotent → running twice yields exactly one entry.
  C) uninstall-cron.py removes the entry.
  D) uninstall-cron.py is a safe no-op when the entry is absent (and when no
     crontab file exists at all).
  E) install preserves pre-existing unrelated crontab lines.
  F) install-cron.py on a host where crontab is administratively restricted
     (the shim writes "not allowed" to stderr and exits non-zero on BOTH
     `-l` and `-`) exits 0 without crashing and prints the actionable
     restricted-host remediation message (issue #507).
"""

import os
import subprocess
import sys
import tempfile
import textwrap

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.normpath(os.path.join(HERE, "..", "scripts"))
INSTALL = os.path.join(SCRIPTS, "install-cron.py")
UNINSTALL = os.path.join(SCRIPTS, "uninstall-cron.py")

ENTRY_TOKEN = "tick-headless.py"

FAIL = 0


def fail(msg):
    global FAIL
    print(f"FAIL: {msg}", file=sys.stderr)
    FAIL = 1


def ok(msg):
    print(f"PASS: {msg}")


def make_fake_crontab(dirpath):
    """Create a fake `crontab` executable in dirpath backed by
    <dirpath>/crontab.txt. Returns the path to the shim."""
    crondata = os.path.join(dirpath, "crontab.txt")
    shim = os.path.join(dirpath, "crontab")
    with open(shim, "w") as f:
        f.write(textwrap.dedent(f"""\
            #!{sys.executable}
            import sys, os
            DATA = {crondata!r}
            args = sys.argv[1:]
            if args == ["-l"]:
                if not os.path.isfile(DATA):
                    sys.stderr.write("no crontab for testuser\\n")
                    sys.exit(1)
                with open(DATA) as fh:
                    sys.stdout.write(fh.read())
                sys.exit(0)
            if args == ["-"]:
                content = sys.stdin.read()
                with open(DATA, "w") as fh:
                    fh.write(content)
                sys.exit(0)
            sys.stderr.write("fake crontab: unsupported args %r\\n" % (args,))
            sys.exit(2)
            """))
    os.chmod(shim, 0o755)
    return shim, crondata


def make_restricted_crontab(dirpath):
    """Create a fake `crontab` executable in dirpath that simulates an
    administratively restricted host: every invocation prints the real-host
    "not allowed to use this program (crontab)" denial to stderr and exits
    non-zero, for BOTH `-l` and `-`. Returns the path to the shim."""
    shim = os.path.join(dirpath, "crontab")
    with open(shim, "w") as f:
        f.write(textwrap.dedent(f"""\
            #!{sys.executable}
            import sys
            sys.stderr.write(
                "You (testuser) are not allowed to use this program "
                "(crontab)\\n")
            sys.exit(1)
            """))
    os.chmod(shim, 0o755)
    return shim


def run(script, repo_root, shim, *args):
    env = os.environ.copy()
    env["RABBIT_CRONTAB_CMD"] = shim
    return subprocess.run(
        [sys.executable, script, *args],
        cwd=repo_root,
        capture_output=True,
        text=True,
        env=env,
    )


def read_cron(crondata):
    if not os.path.isfile(crondata):
        return ""
    with open(crondata) as f:
        return f.read()


def count_entries(crondata):
    return read_cron(crondata).count(ENTRY_TOKEN)


# ---------------------------------------------------------------------------
# Scenario A — install from empty crontab
# ---------------------------------------------------------------------------
with tempfile.TemporaryDirectory() as d:
    shim, crondata = make_fake_crontab(d)
    repo_root = os.path.join(d, "repo")
    os.makedirs(repo_root)
    proc = run(INSTALL, repo_root, shim)
    if proc.returncode != 0:
        fail(f"A: install exit {proc.returncode}; stderr={proc.stderr!r}")
    else:
        ok("A: install-cron.py exited 0 from empty crontab")
    if count_entries(crondata) != 1:
        fail(f"A: expected exactly 1 tick-headless entry, got {count_entries(crondata)}; cron={read_cron(crondata)!r}")
    else:
        ok("A: exactly one tick-headless entry installed")
    body = read_cron(crondata)
    if "*/30 * * * *" not in body:
        fail(f"A: expected '*/30 * * * *' schedule in entry; got {body!r}")
    else:
        ok("A: entry carries the */30 schedule")
    if repo_root not in body:
        fail(f"A: expected repo_root path {repo_root!r} in entry; got {body!r}")
    else:
        ok("A: entry cd's into the repo root")


# ---------------------------------------------------------------------------
# Scenario B — install is idempotent
# ---------------------------------------------------------------------------
with tempfile.TemporaryDirectory() as d:
    shim, crondata = make_fake_crontab(d)
    repo_root = os.path.join(d, "repo")
    os.makedirs(repo_root)
    p1 = run(INSTALL, repo_root, shim)
    p2 = run(INSTALL, repo_root, shim)
    if p2.returncode != 0:
        fail(f"B: second install exit {p2.returncode}; stderr={p2.stderr!r}")
    else:
        ok("B: second install-cron.py exited 0 (idempotent)")
    if count_entries(crondata) != 1:
        fail(f"B: expected exactly 1 entry after two installs, got {count_entries(crondata)}; cron={read_cron(crondata)!r}")
    else:
        ok("B: two installs yield exactly one entry (idempotent)")


# ---------------------------------------------------------------------------
# Scenario C — uninstall removes the entry
# ---------------------------------------------------------------------------
with tempfile.TemporaryDirectory() as d:
    shim, crondata = make_fake_crontab(d)
    repo_root = os.path.join(d, "repo")
    os.makedirs(repo_root)
    run(INSTALL, repo_root, shim)
    if count_entries(crondata) != 1:
        fail("C: pre-setup install did not produce one entry")
    proc = run(UNINSTALL, repo_root, shim)
    if proc.returncode != 0:
        fail(f"C: uninstall exit {proc.returncode}; stderr={proc.stderr!r}")
    else:
        ok("C: uninstall-cron.py exited 0")
    if count_entries(crondata) != 0:
        fail(f"C: expected 0 entries after uninstall, got {count_entries(crondata)}; cron={read_cron(crondata)!r}")
    else:
        ok("C: tick-headless entry removed")


# ---------------------------------------------------------------------------
# Scenario D — uninstall is a safe no-op when absent
# ---------------------------------------------------------------------------
with tempfile.TemporaryDirectory() as d:
    shim, crondata = make_fake_crontab(d)
    repo_root = os.path.join(d, "repo")
    os.makedirs(repo_root)
    # No crontab file exists at all (crontab -l exits 1).
    proc = run(UNINSTALL, repo_root, shim)
    if proc.returncode != 0:
        fail(f"D: uninstall (no crontab) exit {proc.returncode}; stderr={proc.stderr!r}")
    else:
        ok("D: uninstall-cron.py is a safe no-op when no crontab exists")
    # Run uninstall again after an install+uninstall (entry already absent).
    run(INSTALL, repo_root, shim)
    run(UNINSTALL, repo_root, shim)
    proc2 = run(UNINSTALL, repo_root, shim)
    if proc2.returncode != 0:
        fail(f"D: second uninstall exit {proc2.returncode}; stderr={proc2.stderr!r}")
    else:
        ok("D: uninstall-cron.py idempotent (safe second run)")
    if count_entries(crondata) != 0:
        fail(f"D: expected 0 entries, got {count_entries(crondata)}")


# ---------------------------------------------------------------------------
# Scenario E — install preserves unrelated crontab lines
# ---------------------------------------------------------------------------
with tempfile.TemporaryDirectory() as d:
    shim, crondata = make_fake_crontab(d)
    repo_root = os.path.join(d, "repo")
    os.makedirs(repo_root)
    with open(crondata, "w") as f:
        f.write("0 0 * * * /usr/bin/backup.sh\n")
    run(INSTALL, repo_root, shim)
    body = read_cron(crondata)
    if "/usr/bin/backup.sh" not in body:
        fail(f"E: install clobbered an unrelated crontab line; got {body!r}")
    else:
        ok("E: install preserved the unrelated backup.sh line")
    if count_entries(crondata) != 1:
        fail(f"E: expected exactly 1 tick-headless entry alongside the backup line, got {count_entries(crondata)}")
    else:
        ok("E: exactly one tick-headless entry added alongside the backup line")
    # uninstall must leave the unrelated line intact.
    run(UNINSTALL, repo_root, shim)
    body2 = read_cron(crondata)
    if "/usr/bin/backup.sh" not in body2:
        fail(f"E: uninstall removed the unrelated backup.sh line; got {body2!r}")
    else:
        ok("E: uninstall preserved the unrelated backup.sh line")


# ---------------------------------------------------------------------------
# Scenario F — restricted-host graceful fallback (issue #507)
# ---------------------------------------------------------------------------
with tempfile.TemporaryDirectory() as d:
    shim = make_restricted_crontab(d)
    repo_root = os.path.join(d, "repo")
    os.makedirs(repo_root)
    proc = run(INSTALL, repo_root, shim)
    if proc.returncode != 0:
        fail(f"F: install on restricted host exit {proc.returncode} "
             f"(expected 0); stderr={proc.stderr!r}")
    else:
        ok("F: install-cron.py exits 0 on a restricted-crontab host")
    out = proc.stdout + proc.stderr
    low = out.lower()
    if "restrict" not in low and "not allowed" not in low:
        fail(f"F: expected a restricted-host notice in output; got {out!r}")
    else:
        ok("F: output states crontab is restricted on this host")
    if "*/30" not in out:
        fail(f"F: expected the manual cron remediation (*/30 entry) in "
             f"output; got {out!r}")
    else:
        ok("F: output gives the */30 sysadmin remediation entry")
    if "start" not in low:
        fail(f"F: expected the manual `start` remediation hint in output; "
             f"got {out!r}")
    else:
        ok("F: output mentions the manual `/rabbit-auto-evolve start` path")


# ---------------------------------------------------------------------------
# --help smoke
# ---------------------------------------------------------------------------
for script, label in ((INSTALL, "install-cron.py"), (UNINSTALL, "uninstall-cron.py")):
    proc = subprocess.run(
        [sys.executable, script, "--help"],
        capture_output=True, text=True,
    )
    if proc.returncode != 0:
        fail(f"--help: {label} exit {proc.returncode}; stderr={proc.stderr!r}")
    elif "cron" not in (proc.stdout + proc.stderr).lower():
        fail(f"--help: {label} usage text missing 'cron'")
    else:
        ok(f"--help: {label} exits 0 with recognizable usage")


sys.exit(FAIL)
