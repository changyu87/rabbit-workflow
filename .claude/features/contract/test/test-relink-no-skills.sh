#!/usr/bin/env bash
# test-relink-no-skills.sh
# t1: relink.sh does not create a repo-root symlink from skills surface entries

set -uo pipefail

FEATURE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RELINK="$FEATURE_DIR/scripts/relink.sh"
REPO_ROOT="$(git -C "$FEATURE_DIR" rev-parse --show-toplevel)"

pass=0; fail=0
ok()     { echo "  PASS t$1: $2"; pass=$((pass + 1)); }
fail_t() { echo "  FAIL t$1: $2"; fail=$((fail + 1)); }

echo "test-relink-no-skills.sh"

# Run relink.sh and verify no skill-named symlink appears at repo root.
# rabbit-cage declares skills: ["rabbit-feature-touch"], so the old code
# would create <repo-root>/rabbit-feature-touch as a dead letter.
bash "$RELINK" "$REPO_ROOT/.claude/features" "$REPO_ROOT" >/dev/null 2>&1 || true

T1_LABEL="t1: relink.sh does not create rabbit-feature-touch symlink at repo root"
if [ ! -e "$REPO_ROOT/rabbit-feature-touch" ] && [ ! -L "$REPO_ROOT/rabbit-feature-touch" ]; then
  ok 1 "$T1_LABEL"
else
  fail_t 1 "$T1_LABEL — found unexpected $REPO_ROOT/rabbit-feature-touch"
fi

T2_LABEL="t2: relink.sh header comment does not mention 'skills'"
if ! grep -q 'surface\.{hooks,commands,agents,skills}' "$RELINK"; then
  ok 2 "$T2_LABEL"
else
  fail_t 2 "$T2_LABEL — header still documents 'skills'"
fi

echo ""
echo "Results: $pass passed, $fail failed"
[ "$fail" -eq 0 ]
