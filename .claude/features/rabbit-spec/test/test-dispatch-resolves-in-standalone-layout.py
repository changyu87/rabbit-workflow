#!/usr/bin/env python3
"""test-dispatch-resolves-in-standalone-layout.py — rabbit-spec Inv 3(e).

Asserts dispatch-spec-create.py resolves <repo_root> via
Path(__file__).resolve().parents[4] when invoked against the real
dev-workspace layout from an arbitrary outside cwd. The resolved
build-prompt.py path MUST point at the dev-workspace location, NOT
at anything derived from cwd.

Version: 1.0.0
Owner: rabbit-workflow team
Deprecation criterion: when Claude Code exposes native spec-lifecycle skills
"""
import os
import subprocess
import sys
import tempfile

FEATURE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT = os.path.join(FEATURE_DIR, "scripts/dispatch-spec-create.py")
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(FEATURE_DIR)))
EXPECTED_BUILD_PROMPT = os.path.join(
    REPO_ROOT, ".claude/features/contract/scripts/build-prompt.py"
)


def main():
    if not os.path.isfile(EXPECTED_BUILD_PROMPT):
        print(f"FAIL: pre-condition: expected build-prompt.py at "
              f"{EXPECTED_BUILD_PROMPT!r}", file=sys.stderr)
        return 1

    outside_cwd = tempfile.mkdtemp()
    try:
        r = subprocess.run(
            ["python3", SCRIPT, "--feature-name", "test-bar", "--paths", ""],
            cwd=outside_cwd, capture_output=True, text=True,
        )
    finally:
        import shutil
        shutil.rmtree(outside_cwd, ignore_errors=True)

    if r.returncode != 0:
        print(f"FAIL: standalone-layout dispatch exited {r.returncode} "
              f"from outside cwd; stderr={r.stderr!r}", file=sys.stderr)
        return 1

    # The dispatcher's stdout is the prompt-file path written by
    # build-prompt.py. We don't get the build-prompt path directly, but the
    # output file MUST exist on disk — and it MUST be under <REPO_ROOT>/.rabbit/
    # (per build-prompt.py's contract). If repo_root were misresolved, either
    # the dispatch would fail OR the output would land elsewhere.
    out = r.stdout.strip()
    if not os.path.isfile(out):
        print(f"FAIL: dispatch stdout {out!r} is not an existing file",
              file=sys.stderr)
        return 1

    expected_prefix = os.path.join(REPO_ROOT, ".rabbit/prompts/")
    if not os.path.abspath(out).startswith(expected_prefix):
        print(f"FAIL: dispatch wrote prompt to {out!r}; expected to live "
              f"under {expected_prefix!r} (proves repo_root resolved to the "
              f"rabbit root, not cwd)", file=sys.stderr)
        return 1

    print("PASS: dispatch-spec-create.py resolves repo_root via __file__ "
          "from outside cwd in standalone layout")
    return 0


if __name__ == "__main__":
    sys.exit(main())
