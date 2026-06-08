#!/usr/bin/env python3
"""test-dispatch-prompt-path-no-double-rabbit.py — rabbit-spec Inv 3(f).

Regression guard for the vendored-mode `.rabbit/.rabbit/prompts/` doubling.

In a vendored install the dispatcher session exports `RABBIT_ROOT=<host>/.rabbit`.
contract/scripts/build-prompt.py anchors its output dir at the canonical
single-`.rabbit` runtime root resolved by rabbit-cage's `rabbit_runtime_root`,
so the assembled prompt lands at `<rabbit_runtime_root(repo_root)>/prompts/...`
with NO doubled `.rabbit/.rabbit` segment. dispatch-spec-creator.py prints that
emitted path as-is — the upstream guarantee makes any in-dispatcher relocation
redundant.

The emitted path (and the file on disk) MUST live under
`<rabbit_runtime_root(repo_root)>/prompts/`, with NO `.rabbit/.rabbit` segment.

This test stubs build-prompt.py to reproduce build-prompt's real output-dir
anchoring (`rabbit_runtime_root(RABBIT_ROOT)/prompts`), then asserts the
dispatcher's stdout path is the single-`.rabbit` canonical path and the prompt
file actually exists there.

Version: 2.0.0
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

# Stub build-prompt.py that mirrors the REAL (#1073-fixed) build-prompt's
# output-dir anchoring: repo_root = $RABBIT_ROOT (env override) else git
# toplevel; out_dir = rabbit_runtime_root(repo_root)/prompts, where
# rabbit_runtime_root returns repo_root unchanged when it is already a
# `.rabbit` dir (vendored) and appends `.rabbit` otherwise (standalone). This
# is the upstream canonical-path guarantee the dispatcher now relies on.
STUB_BUILD_PROMPT = (
    "#!/usr/bin/env python3\n"
    "import os, sys, subprocess\n"
    "root = os.environ.get('RABBIT_ROOT')\n"
    "if not root:\n"
    "    root = subprocess.run(['git','-C',os.path.dirname(os.path.abspath(__file__)),\n"
    "        'rev-parse','--show-toplevel'], capture_output=True, text=True).stdout.strip()\n"
    "root = os.path.normpath(root)\n"
    "runtime_root = root if os.path.basename(root) == '.rabbit' else os.path.join(root, '.rabbit')\n"
    "out_dir = os.path.join(runtime_root, 'prompts')\n"
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
