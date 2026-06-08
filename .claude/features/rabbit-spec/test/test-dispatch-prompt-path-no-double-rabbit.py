#!/usr/bin/env python3
"""test-dispatch-prompt-path-no-double-rabbit.py — rabbit-spec Inv 3(f) (#1066).

Regression guard for the vendored-mode `.rabbit/.rabbit/prompts/` doubling.

In a vendored install the dispatcher session exports `RABBIT_ROOT=<host>/.rabbit`.
contract/scripts/build-prompt.py resolves its own repo_root from that env and
unconditionally joins `<repo_root>/.rabbit/prompts/...`, so the assembled prompt
lands at the DOUBLED `<host>/.rabbit/.rabbit/prompts/...` — splitting prompts off
the single-`.rabbit` runtime root every other writer/reader uses.

dispatch-spec-creator.py MUST pin the emitted prompt to the canonical single-
`.rabbit` runtime root via rabbit-cage's `rabbit_runtime_root` resolver: the
final path it prints (and the file on disk) MUST live under
`<rabbit_runtime_root(repo_root)>/prompts/`, with NO `.rabbit/.rabbit` segment.

This test stubs build-prompt.py to reproduce build-prompt's real
`repo_root + .rabbit/prompts` join (driven by RABBIT_ROOT), then asserts the
dispatcher's stdout path is the single-`.rabbit` canonical path and the prompt
file actually exists there.

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

# Stub build-prompt.py that mirrors the REAL build-prompt's output-dir join:
# repo_root = $RABBIT_ROOT (env override) else git toplevel; write under
# <repo_root>/.rabbit/prompts/<id>-<pid>.txt and print that path.
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


def build_vendored_fixture(tmp):
    # Vendored layout: <tmp>/.rabbit/.claude/features/{rabbit-spec,contract}/scripts
    rabbit_root = os.path.join(tmp, ".rabbit")
    spec_scripts = os.path.join(rabbit_root, ".claude/features/rabbit-spec/scripts")
    contract_scripts = os.path.join(rabbit_root, ".claude/features/contract/scripts")
    os.makedirs(spec_scripts)
    os.makedirs(contract_scripts)

    target_script = os.path.join(spec_scripts, "dispatch-spec-creator.py")
    shutil.copy(REAL_SCRIPT, target_script)
    os.chmod(target_script, 0o755)

    stub = os.path.join(contract_scripts, "build-prompt.py")
    with open(stub, "w") as f:
        f.write(STUB_BUILD_PROMPT)
    os.chmod(stub, 0o755)

    return rabbit_root, target_script


def main():
    with tempfile.TemporaryDirectory() as tmp:
        rabbit_root, target_script = build_vendored_fixture(tmp)

        # Vendored install: dispatcher session exports RABBIT_ROOT=<host>/.rabbit.
        env = dict(os.environ)
        env["RABBIT_ROOT"] = rabbit_root

        outside_cwd = tempfile.mkdtemp()
        try:
            r = subprocess.run(
                ["python3", target_script, "--feature-name", "foo"],
                cwd=outside_cwd, capture_output=True, text=True, env=env,
            )
        finally:
            shutil.rmtree(outside_cwd, ignore_errors=True)

        if r.returncode != 0:
            print(f"FAIL: vendored dispatch exited {r.returncode}; "
                  f"stderr={r.stderr!r}", file=sys.stderr)
            return 1

        emitted = r.stdout.strip()

        # The canonical single-`.rabbit` prompts dir for this vendored layout.
        canonical_prompts = os.path.join(rabbit_root, "prompts")
        doubled_prompts = os.path.join(rabbit_root, ".rabbit", "prompts")

        if doubled_prompts in emitted or ".rabbit/.rabbit" in emitted:
            print(f"FAIL: emitted prompt path DOUBLES .rabbit: {emitted!r} "
                  f"(must be under {canonical_prompts!r})", file=sys.stderr)
            return 1

        if os.path.normpath(os.path.dirname(emitted)) != os.path.normpath(canonical_prompts):
            print(f"FAIL: emitted prompt dir {os.path.dirname(emitted)!r} != "
                  f"canonical {canonical_prompts!r}", file=sys.stderr)
            return 1

        if not os.path.isfile(emitted):
            print(f"FAIL: emitted prompt path does not exist on disk: {emitted!r}",
                  file=sys.stderr)
            return 1

        with open(emitted) as f:
            if f.read() != "PROMPT BODY":
                print(f"FAIL: prompt body not preserved at {emitted!r}",
                      file=sys.stderr)
                return 1

    print("PASS: dispatch-spec-creator.py emits single-.rabbit prompt path in vendored mode")
    return 0


if __name__ == "__main__":
    sys.exit(main())
