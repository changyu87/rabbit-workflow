#!/usr/bin/env python3
"""test-dispatch-creator-multi-feature.py — rabbit-spec Inv 3 (#922).

End-to-end guard that scripts/dispatch-spec-creator.py is the per-feature input
assembler an orchestrator runs once per feature. A decompose/feature pipeline
seeds N features in parallel by invoking this assembler N times — once per
feature name — and dispatching rabbit-spec-creator against each assembled
prompt. This test exercises the assembler for THREE distinct feature names and
asserts each call:
  - exits 0,
  - prints a single prompt-file path on stdout,
  - and the prompt files are distinct per feature.

Hermetic with respect to the live build-prompt.py: it uses the real dev-workspace
layout (invoked from an outside cwd) so repo_root resolution via
Path(__file__).resolve().parents[4] is also exercised.

Version: 1.0.0
Owner: rabbit-workflow team
Deprecation criterion: when Claude Code exposes native spec-lifecycle skills
"""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path

FEATURE_DIR = Path(__file__).resolve().parents[1]
SCRIPT = FEATURE_DIR / "scripts" / "dispatch-spec-creator.py"


def main() -> int:
    if not os.access(SCRIPT, os.X_OK):
        print(f"FAIL: assembler not executable: {SCRIPT}", file=sys.stderr)
        return 1

    outside = tempfile.mkdtemp()
    errors: list[str] = []
    produced: list[str] = []
    try:
        for fname in ("alpha-feature", "beta-feature", "gamma-feature"):
            r = subprocess.run(
                [sys.executable, str(SCRIPT), "--feature-name", fname, "--paths", ""],
                cwd=outside, capture_output=True, text=True,
            )
            if r.returncode != 0:
                errors.append(
                    f"{fname}: exit {r.returncode}; stderr={r.stderr!r}"
                )
                continue
            out_lines = [ln for ln in r.stdout.splitlines() if ln.strip()]
            if len(out_lines) != 1:
                errors.append(
                    f"{fname}: stdout must be a single prompt-file path; "
                    f"got {len(out_lines)} lines: {r.stdout!r}"
                )
                continue
            path = out_lines[0]
            if not os.path.isfile(path):
                errors.append(f"{fname}: prompt path {path!r} is not a file")
                continue
            produced.append(path)
    finally:
        import shutil
        shutil.rmtree(outside, ignore_errors=True)

    if len(set(produced)) != len(produced):
        errors.append(
            f"per-feature prompt files must be distinct; got {produced}"
        )

    if errors:
        for e in errors:
            print(f"FAIL: {e}", file=sys.stderr)
        return 1

    print("PASS: dispatch-spec-creator.py assembles a distinct per-feature "
          "prompt for each of N feature names")
    return 0


if __name__ == "__main__":
    sys.exit(main())
