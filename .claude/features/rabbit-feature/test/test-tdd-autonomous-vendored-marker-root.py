#!/usr/bin/env python3
"""test-tdd-autonomous-vendored-marker-root.py — #1072 (e2e).

Coordinates with #1048 (contract Inv 68). #1048 made the READER
(contract.lib.runtime._repo_markers_root) resolve a marker-file configurable's
repo-root marker (.rabbit-tdd-autonomous) at the GIT TOPLEVEL — dirname(RABBIT_ROOT)
when vendored, RABBIT_ROOT unchanged when standalone.

#1072 fixes the WRITE side so it lands at the SAME place the reader looks:

  VENDORED  — RABBIT_ROOT is the `.rabbit` install dir whose parent is the git
              toplevel. The config command MUST write .rabbit-tdd-autonomous at
              the git toplevel (parent of `.rabbit`), NOT inside `.rabbit`.
  STANDALONE — RABBIT_ROOT IS the repo root; toplevel == repo_root; the marker
              lands at RABBIT_ROOT (behavior unchanged).

These two e2e cases run the REAL script as a subprocess against a temp layout
mirroring each install mode. The vendored case is the regression for #1072.

Version: 1.0.0
Owner: rabbit-workflow team
Deprecation criterion: when the per-feature config command is superseded by a
    native rabbit CLI configuration mechanism.
"""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
FEATURE = REPO / ".claude/features/rabbit-feature"
FEATURE_FJ = FEATURE / "feature.json"
SCRIPT = FEATURE / "scripts/rabbit-tdd-autonomous-config.py"
CONTRACT = REPO / ".claude/features/contract"

MARKER = ".rabbit-tdd-autonomous"

PASS = 0
FAIL = 0


def ok(msg: str) -> None:
    global PASS
    print(f"  ok   {msg}")
    PASS += 1


def ko(msg: str) -> None:
    global FAIL
    print(f"  FAIL {msg}")
    FAIL += 1


def _populate_rabbit_root(rabbit_root: Path) -> None:
    """Lay down the live rabbit-feature feature.json + a symlink to the live
    contract feature under <rabbit_root>/.claude/features so the thin wrapper's
    `from lib.config_dispatch import dispatch_config` and feature.json read
    both resolve against RABBIT_ROOT (the framework root)."""
    feats = rabbit_root / ".claude" / "features"
    (feats / "rabbit-feature").mkdir(parents=True)
    (feats / "rabbit-feature" / "feature.json").write_text(FEATURE_FJ.read_text())
    os.symlink(CONTRACT, feats / "contract")


def _run(rabbit_root: Path, *args: str) -> subprocess.CompletedProcess:
    env = dict(os.environ)
    env["RABBIT_ROOT"] = str(rabbit_root)
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        capture_output=True, text=True, env=env,
    )


def main() -> int:
    if not SCRIPT.is_file():
        ko(f"script missing: {SCRIPT}")
        print()
        print(f"summary: {PASS} passed, {FAIL} failed")
        return 1

    # ---- VENDORED: RABBIT_ROOT is a `.rabbit` dir whose parent is the git
    # toplevel. The marker MUST land at the toplevel (parent of `.rabbit`), and
    # MUST NOT land inside `.rabbit`.
    with tempfile.TemporaryDirectory() as tmp:
        toplevel = Path(tmp)
        rabbit_root = toplevel / ".rabbit"
        rabbit_root.mkdir()
        # A sibling entry under the toplevel so detect_mode sees a real
        # vendored layout (parent contains an entry other than ".rabbit").
        (toplevel / ".claude").mkdir()
        _populate_rabbit_root(rabbit_root)

        toplevel_marker = toplevel / MARKER
        inside_marker = rabbit_root / MARKER

        r = _run(rabbit_root, "tdd-autonomous", "true")
        if r.returncode == 0:
            ok("vendored: tdd-autonomous true exits 0")
        else:
            ko(f"vendored: tdd-autonomous true rc={r.returncode} err={r.stderr}")
        if toplevel_marker.exists():
            ok(f"vendored: {MARKER} written at git toplevel (parent of .rabbit)")
        else:
            ko(f"vendored: {MARKER} NOT at git toplevel: {toplevel_marker}")
        if not inside_marker.exists():
            ok(f"vendored: {MARKER} NOT written inside .rabbit")
        else:
            ko(f"vendored: {MARKER} wrongly written inside .rabbit: {inside_marker}")

        # round-trip: false deletes the toplevel marker.
        r = _run(rabbit_root, "tdd-autonomous", "false")
        if r.returncode == 0 and not toplevel_marker.exists():
            ok(f"vendored: tdd-autonomous false deletes toplevel {MARKER}")
        else:
            ko(f"vendored: false failed rc={r.returncode} "
               f"exists={toplevel_marker.exists()} err={r.stderr}")

    # ---- STANDALONE: RABBIT_ROOT IS the repo root (not a `.rabbit` dir).
    # toplevel == repo_root; the marker lands at RABBIT_ROOT (unchanged).
    with tempfile.TemporaryDirectory() as tmp:
        repo_root = Path(tmp)
        _populate_rabbit_root(repo_root)
        marker = repo_root / MARKER

        r = _run(repo_root, "tdd-autonomous", "true")
        if r.returncode == 0 and marker.exists():
            ok(f"standalone: {MARKER} written at repo root (unchanged)")
        else:
            ko(f"standalone: true failed rc={r.returncode} "
               f"exists={marker.exists()} err={r.stderr}")

    print()
    print(f"summary: {PASS} passed, {FAIL} failed")
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
