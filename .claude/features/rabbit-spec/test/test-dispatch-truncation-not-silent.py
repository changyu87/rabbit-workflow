#!/usr/bin/env python3
"""test-dispatch-truncation-not-silent.py — rabbit-spec Inv 3(b).

The dispatcher caps the resolved file list at 50 entries. The cap itself is
fine — but the truncation MUST NOT be silent. This test builds a plugin-style
fixture and asserts:

  - With MORE than 50 resolvable files, the dispatcher emits a structured
    note to STDERR naming the dropped count (the note text contains the
    substring "dropped" and the integer count of files past the cap), while
    STDOUT stays a SINGLE prompt-file path the skill can parse.
  - With 50 OR FEWER resolvable files, NO such note is emitted (silent
    success).

Models the fixture after test-dispatch-resolves-in-plugin-layout.py: the real
dispatch script is copied into a plugin layout and build-prompt.py is stubbed
so the test is hermetic and independent of the live repo.

Version: 1.0.0
Owner: rabbit-workflow team
Deprecation criterion: when Claude Code exposes native spec-lifecycle skills
"""
import os
import re
import shutil
import subprocess
import sys
import tempfile

FEATURE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REAL_SCRIPT = os.path.join(FEATURE_DIR, "scripts/dispatch-spec-creator.py")

CAP = 50


def build_fixture(tmp, n_files):
    """Plugin layout with a code/ dir holding n_files .py files.

    Returns (target_script, glob_arg). The glob matches every file under
    code/ so the dispatcher resolves exactly n_files entries.
    """
    plugin_root = os.path.join(tmp, ".rabbit")
    spec_scripts = os.path.join(plugin_root, ".claude/features/rabbit-spec/scripts")
    contract_scripts = os.path.join(plugin_root, ".claude/features/contract/scripts")
    os.makedirs(spec_scripts)
    os.makedirs(contract_scripts)

    target_script = os.path.join(spec_scripts, "dispatch-spec-creator.py")
    shutil.copy(REAL_SCRIPT, target_script)
    os.chmod(target_script, 0o755)

    # Stub build-prompt.py — just prints its own path (a valid stdout line).
    stub = os.path.join(contract_scripts, "build-prompt.py")
    with open(stub, "w") as f:
        f.write(
            "#!/usr/bin/env python3\n"
            "import os\n"
            "print(os.path.abspath(__file__))\n"
        )
    os.chmod(stub, 0o755)

    code_dir = os.path.join(tmp, "code")
    os.makedirs(code_dir)
    for i in range(n_files):
        with open(os.path.join(code_dir, f"f{i:04d}.py"), "w") as f:
            f.write("# fixture\n")

    glob_arg = os.path.join(code_dir, "*.py")
    return target_script, glob_arg


def run(target_script, glob_arg, cwd):
    return subprocess.run(
        ["python3", target_script, "--feature-name", "foo", "--paths", glob_arg],
        cwd=cwd, capture_output=True, text=True,
    )


def main():
    errors = []

    # --- Case 1: >cap files — truncation MUST be reported, not silent. ---
    with tempfile.TemporaryDirectory() as tmp:
        n = CAP + 7  # 57 files -> 7 dropped
        target_script, glob_arg = build_fixture(tmp, n)
        outside = tempfile.mkdtemp()
        try:
            r = run(target_script, glob_arg, outside)
        finally:
            shutil.rmtree(outside, ignore_errors=True)

        if r.returncode != 0:
            errors.append(f">cap: dispatch exited {r.returncode}; stderr={r.stderr!r}")
        else:
            # stdout must remain a single parseable line (the prompt path).
            out_lines = [ln for ln in r.stdout.splitlines() if ln.strip()]
            if len(out_lines) != 1:
                errors.append(
                    f">cap: stdout must be a single prompt-file path line; "
                    f"got {len(out_lines)} lines: {r.stdout!r}"
                )
            # stderr must loudly report the dropped count (not silent).
            dropped = n - CAP
            if "dropped" not in r.stderr.lower():
                errors.append(
                    f">cap: stderr does not report dropped files (silent "
                    f"truncation); stderr={r.stderr!r}"
                )
            elif str(dropped) not in r.stderr:
                errors.append(
                    f">cap: stderr does not name the dropped count {dropped}; "
                    f"stderr={r.stderr!r}"
                )

    # --- Case 2: <=cap files — NO note emitted (silent success). ---
    with tempfile.TemporaryDirectory() as tmp:
        target_script, glob_arg = build_fixture(tmp, CAP - 3)
        outside = tempfile.mkdtemp()
        try:
            r = run(target_script, glob_arg, outside)
        finally:
            shutil.rmtree(outside, ignore_errors=True)

        if r.returncode != 0:
            errors.append(f"<=cap: dispatch exited {r.returncode}; stderr={r.stderr!r}")
        elif "dropped" in r.stderr.lower():
            errors.append(
                f"<=cap: stderr emitted a drop note when none should exist; "
                f"stderr={r.stderr!r}"
            )

    if errors:
        for e in errors:
            print(f"FAIL: {e}", file=sys.stderr)
        return 1

    print("PASS: dispatch-spec-creator.py reports the dropped-file count on "
          "stderr (>cap) and stays silent at or below the cap")
    return 0


if __name__ == "__main__":
    sys.exit(main())
