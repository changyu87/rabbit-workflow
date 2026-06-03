#!/usr/bin/env python3
"""E2E: workspace-tree.py recognizes the FLAT docs/ layout (rabbit-cage).

A feature laid out with a flat docs/ home — docs/spec.md, docs/contract.md,
docs/CHANGELOG.md as siblings ALONGSIDE a preserved docs/bugs/ subdirectory —
MUST render in the tree with those three files annotated as the feature's
spec/contract/changelog surface, while docs/bugs/ is still surfaced as the
bug tracker subtree. The existing specs/ and docs/spec/ recognition is
unaffected.

The test builds a throwaway feature tree under a tempdir-backed fake repo
(initialized as a git repo so workspace-tree's git-toplevel fallback resolves)
and asserts on the rendered output.
"""
import os
import subprocess
import sys
import tempfile

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = subprocess.run(
    ["git", "-C", SCRIPT_DIR, "rev-parse", "--show-toplevel"],
    capture_output=True, text=True, check=True,
).stdout.strip()
WORKSPACE_TREE = os.path.join(
    REPO_ROOT, ".claude/features/rabbit-cage/scripts/workspace-tree.py"
)

pass_n = 0
fail_n = 0


def ok(msg):
    global pass_n
    print(f"  PASS: {msg}")
    pass_n += 1


def bad(msg):
    global fail_n
    print(f"  FAIL: {msg}")
    fail_n += 1


def build_fixture(root):
    feat = os.path.join(root, ".claude", "features", "flat-docs-feature")
    docs = os.path.join(feat, "docs")
    os.makedirs(os.path.join(docs, "bugs"), exist_ok=True)
    for name in ("spec.md", "contract.md", "CHANGELOG.md"):
        with open(os.path.join(docs, name), "w") as f:
            f.write("# flat-docs fixture\n")
    with open(os.path.join(feat, "feature.json"), "w") as f:
        f.write('{"name": "flat-docs-feature"}\n')
    with open(os.path.join(docs, "bugs", "BUG-1.md"), "w") as f:
        f.write("# bug\n")


def main():
    print("test-workspace-tree-flat-docs.py")
    print()
    with tempfile.TemporaryDirectory() as root:
        build_fixture(root)
        result = subprocess.run(
            [sys.executable, WORKSPACE_TREE, root, "--full"],
            capture_output=True, text=True,
        )
        out = result.stdout
        if result.returncode != 0:
            bad(f"workspace-tree exited rc={result.returncode} "
                f"stderr={result.stderr!r}")
            print()
            print(f"Results: {pass_n} passed, {fail_n} failed")
            return 1

        # The flat docs/ artifacts must appear in the tree.
        for fname in ("spec.md", "contract.md", "CHANGELOG.md"):
            if fname in out:
                ok(f"docs/{fname} present in tree")
            else:
                bad(f"docs/{fname} missing from tree output")

        # docs/ directory and preserved docs/bugs/ subtree must render.
        if "docs/" in out:
            ok("docs/ directory rendered")
        else:
            bad("docs/ directory not rendered")
        if "bugs/" in out:
            ok("docs/bugs/ preserved in tree")
        else:
            bad("docs/bugs/ not rendered")

        # The flat docs spec/contract artifacts must carry the
        # spec/contract annotation (the feature's documentation surface).
        spec_lines = [ln for ln in out.splitlines()
                      if "spec.md" in ln or "contract.md" in ln]
        annotated = [ln for ln in spec_lines if "#" in ln]
        if annotated:
            ok("flat docs spec/contract artifacts carry an annotation")
        else:
            bad("flat docs spec/contract artifacts carry no annotation: "
                f"{spec_lines!r}")

    print()
    print(f"Results: {pass_n} passed, {fail_n} failed")
    return 1 if fail_n else 0


if __name__ == "__main__":
    sys.exit(main())
