#!/usr/bin/env python3
"""test-dispatch-resolves-in-plugin-layout.py — rabbit-spec Inv 3(e).

Asserts dispatch-spec-create.py resolves <repo_root> via
Path(__file__).resolve().parents[4] when invoked from a plugin layout
(under <user_project>/.rabbit/.claude/features/rabbit-spec/scripts/).
The resolution MUST point at the rabbit root (<user_project>/.rabbit),
not at the user-project root.

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
    # Plugin layout: <tmp>/.rabbit/.claude/features/{rabbit-spec/scripts,contract/scripts}/
    plugin_root = os.path.join(tmp, ".rabbit")
    spec_scripts = os.path.join(plugin_root, ".claude/features/rabbit-spec/scripts")
    contract_scripts = os.path.join(plugin_root, ".claude/features/contract/scripts")
    os.makedirs(spec_scripts)
    os.makedirs(contract_scripts)

    # Copy the real dispatch script into the plugin layout.
    target_script = os.path.join(spec_scripts, "dispatch-spec-create.py")
    shutil.copy(REAL_SCRIPT, target_script)
    os.chmod(target_script, 0o755)

    # Stub build-prompt.py — prints its own absolute path so we can verify
    # which layout the dispatcher resolved.
    stub = os.path.join(contract_scripts, "build-prompt.py")
    with open(stub, "w") as f:
        f.write(
            "#!/usr/bin/env python3\n"
            "import os, sys\n"
            "print(os.path.abspath(__file__))\n"
        )
    os.chmod(stub, 0o755)

    return plugin_root, target_script, stub


def main():
    with tempfile.TemporaryDirectory() as tmp:
        plugin_root, target_script, expected_build_prompt = build_fixture(tmp)

        # Invoke from an arbitrary outside cwd (not the plugin root, not the
        # user project) so cwd-based resolution would fail/mis-resolve.
        outside_cwd = tempfile.mkdtemp()
        try:
            r = subprocess.run(
                ["python3", target_script, "--feature-name", "foo"],
                cwd=outside_cwd, capture_output=True, text=True,
            )
        finally:
            shutil.rmtree(outside_cwd, ignore_errors=True)

        if r.returncode != 0:
            print(f"FAIL: plugin-layout dispatch exited {r.returncode}; "
                  f"stderr={r.stderr!r}", file=sys.stderr)
            return 1

        # The stub printed its own path. It MUST be the plugin-layout stub.
        resolved = r.stdout.strip()
        if resolved != expected_build_prompt:
            print(f"FAIL: dispatch resolved build-prompt.py to {resolved!r}; "
                  f"expected plugin-layout path {expected_build_prompt!r}",
                  file=sys.stderr)
            return 1

    print("PASS: dispatch-spec-create.py resolves repo_root via __file__ in plugin layout")
    return 0


if __name__ == "__main__":
    sys.exit(main())
