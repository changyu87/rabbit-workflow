#!/bin/bash
# End-to-end test of install-distribute. Delegates to the existing top-level
# test/test-install.sh (which predates this feature schema). This wrapper
# also adds a sanity check that the install.sh script and its companion test
# both exist with the expected modes.
set -u

REPO_ROOT="$(cd "$(dirname "$0")/../../../.." && pwd)"
INSTALL="$REPO_ROOT/install.sh"
EXISTING_TEST="$REPO_ROOT/test/test-install.sh"

PASS=0; FAIL=0
ok() { echo "  ok   $*"; PASS=$((PASS+1)); }
ko() { echo "  FAIL $*"; FAIL=$((FAIL+1)); }

# t1: install.sh exists and is executable
if [ -x "$INSTALL" ]; then ok "t1: install.sh exists and is executable"
else ko "t1: missing or non-exec: $INSTALL"; fi

# t2: companion test/test-install.sh exists and is executable
if [ -x "$EXISTING_TEST" ]; then ok "t2: test/test-install.sh exists and is executable"
else ko "t2: missing or non-exec: $EXISTING_TEST"; fi

# Bail if we can't proceed
if [ ! -x "$INSTALL" ] || [ ! -x "$EXISTING_TEST" ]; then
  echo "summary: $PASS passed, $FAIL failed"; exit 1
fi

# t3: install.sh fails fast with bad usage (no target arg AND PWD has .claude — collision)
# The script defaults to $PWD as target. Running from REPO_ROOT, target/.claude exists
# (the repo's own .claude/), so the script must refuse to overwrite.
out=$("$INSTALL" "$REPO_ROOT" 2>&1); rc=$?
if [ "$rc" != "0" ] && echo "$out" | grep -qiE 'exists|already|refus'; then
  ok "t3: install.sh refuses to overwrite an existing .claude/"
else
  ko "t3: rc=$rc out=$out"
fi

# t4: full E2E suite (delegates to existing test runner)
echo "  --- delegating to $EXISTING_TEST ---"
if bash "$EXISTING_TEST" >"$EXISTING_TEST".out 2>&1; then
  ok "t4: existing test/test-install.sh suite passes"
else
  ko "t4: existing test suite failed; tail:"
  tail -20 "$EXISTING_TEST".out | sed 's/^/         /' >&2
fi
rm -f "$EXISTING_TEST".out

echo
echo "summary: $PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ] && exit 0 || exit 1
