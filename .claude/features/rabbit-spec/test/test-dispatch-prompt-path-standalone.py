#!/usr/bin/env python3
"""test-dispatch-prompt-path-standalone.py — rabbit-spec Inv 3(f) (#1066).

Standalone-mode counterpart to test-dispatch-prompt-path-no-double-rabbit.py.

In standalone mode `repo_root` (Path(__file__).parents[4]) is the git toplevel,
so the canonical runtime root is `<repo_root>/.rabbit` and the prompt MUST land
at `<repo_root>/.rabbit/prompts/...` — exactly where build-prompt already writes
it (no doubling, no relocation). This test pins that the runtime-root pinning
added for the vendored fix does NOT perturb the standalone path.

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

STUB_BUILD_PROMPT = (
    "#!/usr/bin/env python3\n"
    "import os, sys, subprocess\n"
    "root = os.environ.get('RABBIT_ROOT')\n"
    "if not root:\n"
    "    root = subprocess.run(['git','-C',os.path.dirname(os.path.abspath(__file__)),\n"
    "        'rev-parse','--show-toplevel'], capture_output=True, text=True).stdout.strip()\n"
    "out_dir = os.path.join(root, '.rabbit', 'prompts')\n"
    "os.makedirs(out_dir, exist_ok=True)\n"
    "p = os.path.join(out_dir, 'spec-create-%d.txt' % os.getpid())\n"
    "open(p, 'w').write('PROMPT BODY')\n"
    "print(p)\n"
)


def build_standalone_fixture(tmp):
    # Standalone layout: <tmp>/.claude/features/{rabbit-spec,contract}/scripts
    spec_scripts = os.path.join(tmp, ".claude/features/rabbit-spec/scripts")
    contract_scripts = os.path.join(tmp, ".claude/features/contract/scripts")
    os.makedirs(spec_scripts)
    os.makedirs(contract_scripts)

    target_script = os.path.join(spec_scripts, "dispatch-spec-creator.py")
    shutil.copy(REAL_SCRIPT, target_script)
    os.chmod(target_script, 0o755)

    stub = os.path.join(contract_scripts, "build-prompt.py")
    with open(stub, "w") as f:
        f.write(STUB_BUILD_PROMPT)
    os.chmod(stub, 0o755)

    return target_script


def main():
    with tempfile.TemporaryDirectory() as tmp:
        target_script = build_standalone_fixture(tmp)

        # Standalone: RABBIT_ROOT is the git toplevel = <tmp>. parents[4] = <tmp>.
        env = dict(os.environ)
        env["RABBIT_ROOT"] = tmp

        outside_cwd = tempfile.mkdtemp()
        try:
            r = subprocess.run(
                ["python3", target_script, "--feature-name", "foo"],
                cwd=outside_cwd, capture_output=True, text=True, env=env,
            )
        finally:
            shutil.rmtree(outside_cwd, ignore_errors=True)

        if r.returncode != 0:
            print(f"FAIL: standalone dispatch exited {r.returncode}; "
                  f"stderr={r.stderr!r}", file=sys.stderr)
            return 1

        emitted = r.stdout.strip()
        canonical_prompts = os.path.join(tmp, ".rabbit", "prompts")

        if ".rabbit/.rabbit" in emitted:
            print(f"FAIL: standalone emitted path doubles .rabbit: {emitted!r}",
                  file=sys.stderr)
            return 1

        if os.path.normpath(os.path.dirname(emitted)) != os.path.normpath(canonical_prompts):
            print(f"FAIL: standalone emitted dir {os.path.dirname(emitted)!r} != "
                  f"canonical {canonical_prompts!r}", file=sys.stderr)
            return 1

        if not os.path.isfile(emitted):
            print(f"FAIL: standalone emitted path does not exist: {emitted!r}",
                  file=sys.stderr)
            return 1

    print("PASS: dispatch-spec-creator.py emits single-.rabbit prompt path in standalone mode")
    return 0


if __name__ == "__main__":
    sys.exit(main())
