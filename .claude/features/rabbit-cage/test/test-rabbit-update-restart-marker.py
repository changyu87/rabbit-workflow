#!/usr/bin/env python3
"""rabbit-cage Inv 35 (#1099) — /rabbit-update install sets the restart-needed
marker contract's SessionStart banner reads.

#1096 (contract, merged) added the READ side: when the marker
`<repo_root>/.rabbit-update-restart-needed` is present, the SessionStart
update banner appends a "RESTART REQUIRED" alert and consumes the marker.
This test pins the WRITE side in rabbit-cage: after `rabbit-update.py install`
runs install.py --update, if the update CHANGED a restart-sensitive surface
(hooks under .claude/hooks/, .claude/settings*.json, or CLAUDE.md) the marker
is written; if nothing restart-sensitive changed, it is NOT written.

The marker name MUST match contract's reader byte-for-byte
(`.rabbit-update-restart-needed`).

Assertions (e2e via the real rabbit-update.py against a fake rabbit root with
a recorder install.py that mutates — or leaves untouched — restart-sensitive
surfaces):
  r0  the marker constant equals contract's reader constant.
  r1  install that CHANGES a hook file under .claude/hooks/ writes the marker.
  r2  install that CHANGES CLAUDE.md writes the marker.
  r3  install that CHANGES .claude/settings.json writes the marker.
  r4  install that changes ONLY a non-restart-sensitive file (e.g. a docs
      file) does NOT write the marker.
  r5  a FAILED install (install.py exits non-zero) does NOT write the marker
      even if surfaces appear changed (no false restart alert on failure).
"""
from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
import tempfile

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = subprocess.run(
    ["git", "-C", SCRIPT_DIR, "rev-parse", "--show-toplevel"],
    capture_output=True, text=True, check=True,
).stdout.strip()
CAGE_DIR = os.path.join(REPO_ROOT, ".claude/features/rabbit-cage")
UPDATE_PY = os.path.join(CAGE_DIR, "scripts/rabbit-update.py")
CONTRACT_RUNTIME = os.path.join(
    REPO_ROOT, ".claude/features/contract/lib/runtime.py")

# The marker name contract's SessionStart banner reads + consumes.
EXPECTED_MARKER = ".rabbit-update-restart-needed"

pass_n = 0
fail_n = 0


def ok(t, msg):
    global pass_n
    print(f"  PASS r{t}: {msg}")
    pass_n += 1


def fail_t(t, msg):
    global fail_n
    print(f"  FAIL r{t}: {msg}")
    fail_n += 1


print("test-rabbit-update-restart-marker.py")


def _write(path, content):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write(content)


def _make_fake_root(tmp):
    """Minimal rabbit root with pre-existing restart-sensitive surfaces."""
    _write(os.path.join(tmp, "CLAUDE.md"), "# original claude md\n")
    _write(os.path.join(tmp, ".claude/hooks/stop-dispatcher.py"),
           "# original hook\n")
    _write(os.path.join(tmp, ".claude/settings.json"), '{"orig": 1}\n')
    _write(os.path.join(tmp, "docs/notes.md"), "original docs\n")
    return tmp


def _recorder_install(tmp, mutations, exit_code=0):
    """Write a recorder install.py that applies `mutations` (rel_path ->
    new content) then exits with `exit_code`. The mutations run BEFORE the
    exit so a non-zero exit still leaves changed files on disk (to prove the
    failed-install case suppresses the marker)."""
    body = ["#!/usr/bin/env python3", "import sys, os"]
    for rel, content in mutations.items():
        full = "os.path.join(os.path.dirname(os.path.abspath(__file__)), %r)" % rel
        body.append(f"_p = {full}")
        body.append("os.makedirs(os.path.dirname(_p), exist_ok=True)")
        body.append(f"open(_p, 'w').write({content!r})")
    body.append(f"sys.exit({exit_code})")
    path = os.path.join(tmp, "install.py")
    with open(path, "w") as f:
        f.write("\n".join(body) + "\n")
    os.chmod(path, 0o755)


def _run_install(tmp):
    env = os.environ.copy()
    env["RABBIT_ROOT"] = tmp
    return subprocess.run(
        [sys.executable, UPDATE_PY, "install"],
        capture_output=True, text=True, env=env,
    )


def _marker_path(tmp):
    return os.path.join(tmp, EXPECTED_MARKER)


# r0 — marker constant agrees with contract's reader, byte-for-byte.
spec = importlib.util.spec_from_file_location("contract_runtime",
                                              CONTRACT_RUNTIME)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
reader_marker = getattr(mod, "_UPDATE_RESTART_MARKER", None)
if reader_marker == EXPECTED_MARKER:
    ok(0, f"contract reader marker == {EXPECTED_MARKER!r}")
else:
    fail_t(0, f"contract reader marker {reader_marker!r} "
              f"!= expected {EXPECTED_MARKER!r}")


# r1 — changed hook → marker written
with tempfile.TemporaryDirectory() as tmp:
    _make_fake_root(tmp)
    _recorder_install(tmp, {".claude/hooks/stop-dispatcher.py": "# CHANGED\n"})
    res = _run_install(tmp)
    if res.returncode == 0 and os.path.isfile(_marker_path(tmp)):
        ok(1, "changed hook → restart marker written")
    else:
        fail_t(1, f"no marker after changed hook: rc={res.returncode} "
                  f"stderr={res.stderr.strip()!r}")

# r2 — changed CLAUDE.md → marker written
with tempfile.TemporaryDirectory() as tmp:
    _make_fake_root(tmp)
    _recorder_install(tmp, {"CLAUDE.md": "# CHANGED claude md\n"})
    res = _run_install(tmp)
    if res.returncode == 0 and os.path.isfile(_marker_path(tmp)):
        ok(2, "changed CLAUDE.md → restart marker written")
    else:
        fail_t(2, f"no marker after changed CLAUDE.md: rc={res.returncode} "
                  f"stderr={res.stderr.strip()!r}")

# r3 — changed settings.json → marker written
with tempfile.TemporaryDirectory() as tmp:
    _make_fake_root(tmp)
    _recorder_install(tmp, {".claude/settings.json": '{"changed": 2}\n'})
    res = _run_install(tmp)
    if res.returncode == 0 and os.path.isfile(_marker_path(tmp)):
        ok(3, "changed settings.json → restart marker written")
    else:
        fail_t(3, f"no marker after changed settings.json: rc={res.returncode} "
                  f"stderr={res.stderr.strip()!r}")

# r4 — only a non-restart-sensitive file changed → NO marker
with tempfile.TemporaryDirectory() as tmp:
    _make_fake_root(tmp)
    _recorder_install(tmp, {"docs/notes.md": "CHANGED docs only\n"})
    res = _run_install(tmp)
    if res.returncode == 0 and not os.path.isfile(_marker_path(tmp)):
        ok(4, "only docs changed → NO restart marker")
    else:
        fail_t(4, f"marker wrongly written for non-sensitive change: "
                  f"rc={res.returncode} marker={os.path.isfile(_marker_path(tmp))}")

# r5 — failed install → NO marker even if surfaces appear changed
with tempfile.TemporaryDirectory() as tmp:
    _make_fake_root(tmp)
    _recorder_install(
        tmp, {".claude/hooks/stop-dispatcher.py": "# CHANGED\n"}, exit_code=1)
    res = _run_install(tmp)
    if res.returncode != 0 and not os.path.isfile(_marker_path(tmp)):
        ok(5, "failed install → NO restart marker")
    else:
        fail_t(5, f"marker wrongly written on failed install: "
                  f"rc={res.returncode} marker={os.path.isfile(_marker_path(tmp))}")

print()
print(f"Results: {pass_n} passed, {fail_n} failed")
sys.exit(0 if fail_n == 0 else 1)
