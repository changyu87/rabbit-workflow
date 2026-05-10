#!/bin/bash
# test-dispatch.sh — verify dispatch-feature-edit.sh output.
# Non-interactive. Exits non-zero on failure.

set -u

FEATURE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPO_ROOT="$(cd "$FEATURE_DIR/../../../../.." && pwd)"

FAIL=0

# The dispatch script computes REPO_ROOT as 5 levels up from its scripts/ dir.
# With structure: FAKE_ROOT/rabbit-run/.claude/features/contract/scripts,
# 5 ups from scripts = FAKE_ROOT — which is also where the registry lives
# (FAKE_ROOT/.claude/features/registry.json).
FAKE_ROOT="$(mktemp -d /tmp/rbt-dispatch-XXXX)"
FAKE_REPO="$FAKE_ROOT/rabbit-run"

cleanup() {
  rm -rf "$FAKE_ROOT"
}
trap cleanup EXIT

FAKE_SCRIPTS="$FAKE_REPO/.claude/features/contract/scripts"
python3 -c "
import os
for d in [
    '$FAKE_SCRIPTS',
    '$FAKE_ROOT/.claude/features',
    '$FAKE_ROOT/.claude/features/auto-refresh/docs/spec',
]:
    os.makedirs(d, exist_ok=True)
"

# Copy scripts — policy-block.sh must be adjacent to dispatch-feature-edit.sh.
cp "$FEATURE_DIR/scripts/policy-block.sh" "$FAKE_SCRIPTS/"
cp "$FEATURE_DIR/scripts/dispatch-feature-edit.sh" "$FAKE_SCRIPTS/"
chmod +x "$FAKE_SCRIPTS/policy-block.sh" "$FAKE_SCRIPTS/dispatch-feature-edit.sh"

# policy-block.sh reads philosophy.md and work-guide.md from REPO_ROOT/.claude/
# REPO_ROOT = FAKE_ROOT (5 ups from scripts)
[ -f "$REPO_ROOT/.claude/philosophy.md" ] && cp "$REPO_ROOT/.claude/philosophy.md" "$FAKE_ROOT/.claude/"
[ -f "$REPO_ROOT/.claude/work-guide.md" ]  && cp "$REPO_ROOT/.claude/work-guide.md"  "$FAKE_ROOT/.claude/"

# Verify REPO_ROOT resolves correctly (sanity check).
RESOLVED="$(cd "$FAKE_SCRIPTS/../../../../.." && pwd)"
if [ "$RESOLVED" != "$FAKE_ROOT" ]; then
  echo "SKIP: fake repo depth mismatch (resolved=$RESOLVED want=$FAKE_ROOT)" >&2
  echo "test-dispatch: SKIP" >&2
  exit 0
fi

# Install the test registry at FAKE_ROOT/.claude/features/registry.json.
# Uses 'root' field as per the intended registry schema.
cat > "$FAKE_ROOT/.claude/features/registry.json" <<'JSON'
{
  "schema_version": "1.0.0",
  "owner": "test",
  "features": {
    "auto-refresh": {
      "name": "auto-refresh",
      "version": "1.0.0",
      "owner": "test",
      "tdd_state": "test-green",
      "summary": "Test entry for dispatch test.",
      "root": ".claude/features/auto-refresh"
    }
  }
}
JSON

STDERR_FILE="$(mktemp /tmp/rbt-stderr-XXXX)"
STDOUT="$("$FAKE_SCRIPTS/dispatch-feature-edit.sh" auto-refresh "test task description" 2>"$STDERR_FILE")"
ACTUAL_EXIT=$?
STDERR="$(cat "$STDERR_FILE")"
rm -f "$STDERR_FILE"

# Test 1: exits 0.
if [ $ACTUAL_EXIT -ne 0 ]; then
  echo "FAIL: dispatch-feature-edit.sh exited $ACTUAL_EXIT (expected 0)" >&2
  echo "  STDERR: $STDERR" >&2
  FAIL=1
fi

check_stdout() {
  local label="$1"
  local pattern="$2"
  if ! echo "$STDOUT" | grep -qF "$pattern"; then
    echo "FAIL [$label]: stdout does not contain: $pattern" >&2
    FAIL=1
  fi
}

# Test 2: stdout contains sentinel.
check_stdout "sentinel" "RABBIT-POLICY-BLOCK-v1"

# Test 3: stdout contains SCOPE: auto-refresh.
check_stdout "scope-line" "SCOPE: auto-refresh"

# Test 4: stdout contains task description.
check_stdout "task-desc" "test task description"

# Test 5: stderr does NOT contain [stub].
if echo "$STDERR" | grep -qF "[stub]"; then
  echo "FAIL [no-stub-in-stderr]: stderr contains '[stub]': $STDERR" >&2
  FAIL=1
fi

if [ $FAIL -ne 0 ]; then
  echo "test-dispatch: FAIL" >&2
  exit 1
fi

echo "test-dispatch: all checks passed."
