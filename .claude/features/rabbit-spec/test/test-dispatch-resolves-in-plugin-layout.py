#!/usr/bin/env python3
"""test-dispatch-resolves-in-plugin-layout.py — rabbit-spec Inv 3(e).

Asserts dispatch-spec-creator.py resolves <repo_root> via
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
REAL_SCRIPT = os.path.join(FEATURE_DIR, "scripts/dispatch-spec-creator.py")


def build_fixture(tmp):
    # Plugin layout: <tmp>/.rabbit/.claude/features/{rabbit-spec/scripts,contract/scripts}/
    plugin_root = os.path.join(tmp, ".rabbit")
    spec_scripts = os.path.join(plugin_root, ".claude/features/rabbit-spec/scripts")
    contract_scripts = os.path.join(plugin_root, ".claude/features/contract/scripts")
    os.makedirs(spec_scripts)
    os.makedirs(contract_scripts)

    # Copy the real dispatch script into the plugin layout.
    target_script = os.path.join(spec_scripts, "dispatch-spec-creator.py")
    shutil.copy(REAL_SCRIPT, target_script)
    os.chmod(target_script, 0o755)

    # Stub build-prompt.py — mirrors the real build-prompt's output-dir join
    # (<repo_root>/.rabbit/prompts/...) and records its OWN absolute path as
    # the prompt body so we can verify which layout the dispatcher resolved
    # even after the dispatcher relocates the prompt to the canonical root.
    stub = os.path.join(contract_scripts, "build-prompt.py")
    with open(stub, "w") as f:
        f.write(
            "#!/usr/bin/env python3\n"
            "import os, sys, subprocess\n"
            "root = os.environ.get('RABBIT_ROOT')\n"
            "if not root:\n"
            "    root = subprocess.run(['git','-C',os.path.dirname(os.path.abspath(__file__)),\n"
            "        'rev-parse','--show-toplevel'], capture_output=True, text=True).stdout.strip()\n"
            "out_dir = os.path.join(root, '.rabbit', 'prompts')\n"
            "os.makedirs(out_dir, exist_ok=True)\n"
            "p = os.path.join(out_dir, 'spec-create-%d.txt' % os.getpid())\n"
            "open(p, 'w').write(os.path.abspath(__file__))\n"
            "print(p)\n"
        )
    os.chmod(stub, 0o755)

    return plugin_root, target_script, stub


def main():
    with tempfile.TemporaryDirectory() as tmp:
        # Resolve symlinks so absolute paths match Path(__file__).resolve().
        tmp = os.path.realpath(tmp)
        plugin_root, target_script, expected_build_prompt = build_fixture(tmp)

        # Vendored install: the session exports RABBIT_ROOT=<host>/.rabbit.
        env = dict(os.environ)
        env["RABBIT_ROOT"] = plugin_root

        # Invoke from an arbitrary outside cwd (not the plugin root, not the
        # user project) so cwd-based resolution would fail/mis-resolve.
        outside_cwd = tempfile.mkdtemp()
        try:
            r = subprocess.run(
                ["python3", target_script, "--feature-name", "foo"],
                cwd=outside_cwd, capture_output=True, text=True, env=env,
            )
        finally:
            shutil.rmtree(outside_cwd, ignore_errors=True)

        if r.returncode != 0:
            print(f"FAIL: plugin-layout dispatch exited {r.returncode}; "
                  f"stderr={r.stderr!r}", file=sys.stderr)
            return 1

        # The emitted prompt records which build-prompt stub resolved. It MUST
        # be the plugin-layout stub.
        prompt_path = r.stdout.strip()
        if not os.path.isfile(prompt_path):
            print(f"FAIL: emitted prompt path does not exist: {prompt_path!r}",
                  file=sys.stderr)
            return 1
        with open(prompt_path) as f:
            resolved = f.read().strip()
        if resolved != expected_build_prompt:
            print(f"FAIL: dispatch resolved build-prompt.py to {resolved!r}; "
                  f"expected plugin-layout path {expected_build_prompt!r}",
                  file=sys.stderr)
            return 1

    print("PASS: dispatch-spec-creator.py resolves repo_root via __file__ in plugin layout")
    return 0


if __name__ == "__main__":
    sys.exit(main())
