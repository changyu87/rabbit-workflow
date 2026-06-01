#!/usr/bin/env python3
"""test-dispatch-ignores-git-toplevel.py — rabbit-spec Inv 3(e).

Asserts dispatch-spec-create.py is immune to a misleading nested git
repository. Builds a plugin layout under a tmp dir, initializes a nested
git repo at the user-project level (above the .rabbit root), and invokes
the dispatcher from inside that nested git checkout. The dispatcher MUST
resolve repo_root via Path(__file__).parents[4] (the rabbit root), NOT
via `git rev-parse --show-toplevel` (which would yield the user-project
root and a non-existent build-prompt.py path).

Version: 1.0.0
Owner: rabbit-workflow team
Deprecation criterion: when Claude Code exposes native spec-lifecycle skills
"""
import os
import shutil
import subprocess
import sys
import tempfile

FEATURE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REAL_SCRIPT = os.path.join(FEATURE_DIR, "scripts/dispatch-spec-create.py")


def build_fixture(tmp):
    # User project root is `tmp`; the plugin lives under tmp/.rabbit/.
    plugin_root = os.path.join(tmp, ".rabbit")
    spec_scripts = os.path.join(plugin_root, ".claude/features/rabbit-spec/scripts")
    contract_scripts = os.path.join(plugin_root, ".claude/features/contract/scripts")
    os.makedirs(spec_scripts)
    os.makedirs(contract_scripts)

    target_script = os.path.join(spec_scripts, "dispatch-spec-create.py")
    shutil.copy(REAL_SCRIPT, target_script)
    os.chmod(target_script, 0o755)

    # Stub build-prompt.py — prints its own absolute path.
    stub = os.path.join(contract_scripts, "build-prompt.py")
    with open(stub, "w") as f:
        f.write(
            "#!/usr/bin/env python3\n"
            "import os, sys\n"
            "print(os.path.abspath(__file__))\n"
        )
    os.chmod(stub, 0o755)

    # Init a git repo at the USER PROJECT root (tmp), NOT at the plugin root.
    # A correctly-implemented dispatcher must ignore this and still resolve
    # repo_root to plugin_root via Path(__file__).parents[4].
    subprocess.run(["git", "init", "-q", tmp], check=True,
                   capture_output=True, text=True)

    return plugin_root, target_script, stub


def main():
    with tempfile.TemporaryDirectory() as tmp:
        # Resolve symlinks (e.g. /tmp -> /private/tmp on macOS, or autofs
        # paths on Linux) so the absolute paths we compare against the
        # dispatcher's output match the script's Path(__file__).resolve().
        tmp = os.path.realpath(tmp)
        plugin_root, target_script, expected_build_prompt = build_fixture(tmp)

        # Invoke the dispatcher from INSIDE the nested git checkout
        # (user-project root), where `git rev-parse --show-toplevel`
        # would return tmp — not plugin_root.
        r = subprocess.run(
            ["python3", target_script, "--feature-name", "foo"],
            cwd=tmp, capture_output=True, text=True,
        )

        if r.returncode != 0:
            print(f"FAIL: dispatch exited {r.returncode} inside nested git; "
                  f"stderr={r.stderr!r}", file=sys.stderr)
            return 1

        resolved = r.stdout.strip()
        if resolved != expected_build_prompt:
            print(f"FAIL: dispatch resolved build-prompt.py to {resolved!r}; "
                  f"expected plugin-layout path {expected_build_prompt!r} "
                  f"(git rev-parse must NOT influence resolution)",
                  file=sys.stderr)
            return 1

    print("PASS: dispatch-spec-create.py ignores misleading nested git toplevel")
    return 0


if __name__ == "__main__":
    sys.exit(main())
