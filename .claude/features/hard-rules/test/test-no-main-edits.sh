#!/bin/bash
# Test the no-main-edits enforcement check.
# Strategy: spin up a throwaway git repo, switch branches, run the check.
set -u

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
FEATURE_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
CHECK="$FEATURE_DIR/scripts/check-no-main-edits.sh"
TMPROOT="$(mktemp -d)"
trap 'rm -rf "$TMPROOT"' EXIT INT TERM

PASS=0; FAIL=0
ok() { echo "  ok   $*"; PASS=$((PASS+1)); }
ko() { echo "  FAIL $*"; FAIL=$((FAIL+1)); }

# Set up a fake repo
cd "$TMPROOT"
git init -q -b main repo
cd repo
git -c user.email=t@t -c user.name=T commit --allow-empty -q -m initial

# t1: on main -> check fails
out=$("$CHECK" 2>&1); rc=$?
[ "$rc" != "0" ] && echo "$out" | grep -qiE 'main' \
  && ok "t1: check fails on main" \
  || ko "t1: rc=$rc out=$out"

# t2: on a feature branch -> check passes
git checkout -q -b feat/something
out=$("$CHECK" 2>&1); rc=$?
[ "$rc" = "0" ] && ok "t2: check passes on feature branch" \
  || ko "t2: rc=$rc out=$out"

# t3: alternative main name (master) -> check fails
git checkout -q main
git branch -m master 2>/dev/null || git checkout -q -b master
out=$("$CHECK" 2>&1); rc=$?
[ "$rc" != "0" ] && echo "$out" | grep -qiE 'master|main' \
  && ok "t3: check fails on master too" \
  || ko "t3: rc=$rc out=$out"

# t4: outside a git repo -> check exits non-zero with clear error
cd "$TMPROOT"
out=$("$CHECK" 2>&1); rc=$?
[ "$rc" != "0" ] && echo "$out" | grep -qiE 'not a git repo|no git|fatal' \
  && ok "t4: check errors outside a repo" \
  || ko "t4: rc=$rc out=$out"

echo
echo "summary: $PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ] && exit 0 || exit 1
