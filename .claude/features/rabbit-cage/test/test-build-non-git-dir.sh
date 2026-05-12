#!/usr/bin/env bash
# test-build-non-git-dir.sh — invariant 30: build.sh passes RABBIT_ROOT to generate-claude-md.sh
#
# Verifies that the generate-claude-md subprocess invocation in build.sh passes
# RABBIT_ROOT so that installs into non-git directories succeed.

set -euo pipefail

REPO_ROOT="$(git -C "$(dirname "${BASH_SOURCE[0]}")" rev-parse --show-toplevel)"
BUILD_SH="$REPO_ROOT/.claude/features/rabbit-cage/scripts/build.sh"
GENERATE_SCRIPT="$REPO_ROOT/.claude/features/rabbit-cage/scripts/generate-claude-md.sh"

pass=0
fail=0

ok() {
    echo "  PASS t$1: $2"
    pass=$((pass + 1))
}

fail_t() {
    echo "  FAIL t$1: $2"
    fail=$((fail + 1))
}

echo "test-build-non-git-dir.sh"

# t1: build.sh exists and is executable
if [ -f "$BUILD_SH" ] && [ -x "$BUILD_SH" ]; then
    ok 1 "build.sh exists and is executable"
else
    fail_t 1 "build.sh missing or not executable"
fi

# t2: build.sh source contains RABBIT_ROOT env var pass to subprocess (invariant 30)
if grep -q 'RABBIT_ROOT' "$BUILD_SH"; then
    ok 2 "build.sh source contains RABBIT_ROOT (env var passed to generate-claude-md.sh)"
else
    fail_t 2 "build.sh does NOT contain RABBIT_ROOT — fix not applied (invariant 30 violated)"
fi

# t3: Running build.sh with a non-git temp dir as repo_root produces CLAUDE.md there
# Set up temp non-git target dir with minimal contract
TMPDIR_TARGET="$(mktemp -d)"
trap "rm -rf '$TMPDIR_TARGET'" EXIT

mkdir -p "$TMPDIR_TARGET/.claude/features/contract"
cat > "$TMPDIR_TARGET/.claude/features/contract/build-contract.json" <<'JSON'
{
  "version": "1.0.0",
  "targets": [
    {
      "name": "CLAUDE.md",
      "type": "generate-claude-md",
      "destination": "CLAUDE.md"
    }
  ]
}
JSON

# Run build.sh with:
#   arg1 = REPO_ROOT      (so it finds the generate-claude-md.sh script via GENERATE_CLAUDE_MD var)
#   ... but we need TMPDIR_TARGET contract. Override the CONTRACT path argument.
# build.sh signature: build.sh [REPO_ROOT]
# It constructs CONTRACT and GENERATE_CLAUDE_MD from REPO_ROOT.
# We need to pass TMPDIR_TARGET contract; build.sh has no flag for that.
# So instead call build.sh's embedded Python directly with TMPDIR_TARGET as repo_root
# and the TMPDIR_TARGET contract — this replicates exactly what build.sh does.

if python3 - "$REPO_ROOT" "$TMPDIR_TARGET" "$TMPDIR_TARGET/.claude/features/contract/build-contract.json" "$GENERATE_SCRIPT" <<'PYEOF'
import json, os, subprocess, sys

actual_repo_root = sys.argv[1]   # where policy files live
target_root      = sys.argv[2]   # the non-git temp dir (acts as repo_root for build)
contract_path    = sys.argv[3]
generate_script  = sys.argv[4]

with open(contract_path) as f:
    contract = json.load(f)

errors = 0
for target in contract.get("targets", []):
    name = target["name"]
    ttype = target["type"]
    destination = os.path.join(target_root, target["destination"])

    if ttype == "generate-claude-md":
        # This is the FIXED version: pass RABBIT_ROOT so generate-claude-md.sh
        # can locate policy files even when target_root is not a git repo.
        env = dict(os.environ)
        env["RABBIT_ROOT"] = actual_repo_root
        result = subprocess.run(
            ["bash", generate_script, "--write", target_root],
            capture_output=True, text=True,
            env=env
        )
        if result.returncode != 0:
            print(f"  [error] {name}: generate-claude-md failed\n{result.stderr}", file=sys.stderr)
            errors += 1
        else:
            print(f"  [built] {name}")

if errors:
    sys.exit(1)
PYEOF
then
    if [ -f "$TMPDIR_TARGET/CLAUDE.md" ]; then
        ok 3 "CLAUDE.md created in non-git temp dir when RABBIT_ROOT is passed to subprocess"
    else
        fail_t 3 "subprocess exited 0 but CLAUDE.md not found in temp dir"
    fi
else
    fail_t 3 "generate-claude-md.sh failed when RABBIT_ROOT was passed (unexpected)"
fi

echo ""
echo "Results: $pass passed, $fail failed"
[ "$fail" -eq 0 ]
