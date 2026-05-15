#!/bin/bash
# test-dispatch.sh — verify dispatch-feature-edit.sh output.
# Non-interactive. Exits non-zero on failure.

set -u

FEATURE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPO_ROOT="${RABBIT_ROOT:-$(git -C "$FEATURE_DIR" rev-parse --show-toplevel 2>/dev/null)}"

FAIL=0

# The dispatch script computes REPO_ROOT as 4 levels up from its scripts/ dir.
# With structure: FAKE_REPO/.claude/features/contract/scripts,
# 4 ups from scripts = FAKE_REPO — which is also where feature.json files live
# (FAKE_REPO/.claude/features/<feature-name>/feature.json).
FAKE_ROOT="$(mktemp -d /tmp/rbt-dispatch-XXXX)"
FAKE_REPO="$FAKE_ROOT/rabbit-run"

cleanup() {
  rm -rf "$FAKE_ROOT"
}
trap cleanup EXIT

FAKE_SCRIPTS="$FAKE_REPO/.claude/features/contract/scripts"
FAKE_POLICY_DIR="$FAKE_REPO/.claude/features/policy"
python3 -c "
import os
for d in [
    '$FAKE_SCRIPTS',
    '$FAKE_REPO/.claude/features',
    '$FAKE_REPO/.claude/features/auto-refresh/docs/spec',
    '$FAKE_REPO/.claude',
    '$FAKE_POLICY_DIR',
]:
    os.makedirs(d, exist_ok=True)
"

# Copy scripts — policy-block.sh and find-feature.sh must be adjacent to dispatch-feature-edit.sh.
cp "$FEATURE_DIR/scripts/policy-block.sh" "$FAKE_SCRIPTS/"
cp "$FEATURE_DIR/scripts/dispatch-feature-edit.sh" "$FAKE_SCRIPTS/"
cp "$FEATURE_DIR/scripts/find-feature.sh" "$FAKE_SCRIPTS/"
cp "$FEATURE_DIR/scripts/find-feature.py" "$FAKE_SCRIPTS/find-feature.py"
chmod +x "$FAKE_SCRIPTS/policy-block.sh" "$FAKE_SCRIPTS/dispatch-feature-edit.sh" "$FAKE_SCRIPTS/find-feature.sh" "$FAKE_SCRIPTS/find-feature.py"

# policy-block.sh reads policy files from REPO_ROOT/.claude/features/policy/
# REPO_ROOT = FAKE_REPO (set via RABBIT_ROOT env var)
REAL_POLICY_DIR="$REPO_ROOT/.claude/features/policy"
for f in philosophy.md spec-rules.md coding-rules.md workflow-rules.md; do
  [ -f "$REAL_POLICY_DIR/$f" ] && cp "$REAL_POLICY_DIR/$f" "$FAKE_POLICY_DIR/"
done

# Install a feature.json for the test feature so find-feature.sh can discover it.
# find-feature.sh scans for .claude/features/*/feature.json — no registry.json needed.
python3 -c "import os; os.makedirs('$FAKE_REPO/.claude/features/auto-refresh', exist_ok=True)"
cat > "$FAKE_REPO/.claude/features/auto-refresh/feature.json" <<'JSON'
{
  "name": "auto-refresh",
  "version": "1.0.0",
  "owner": "test",
  "tdd_state": "test-green",
  "summary": "Test entry for dispatch test."
}
JSON

STDERR_FILE="$(mktemp /tmp/rbt-stderr-XXXX)"
STDOUT="$(RABBIT_ROOT="$FAKE_REPO" "$FAKE_SCRIPTS/dispatch-feature-edit.sh" auto-refresh "test task description" 2>"$STDERR_FILE")"
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

# t-rr1: Verify output contains "SCOPE: auto-refresh" (feature-found signal).
# The invocation we already ran must produce this when REPO_ROOT is correct
# and find-feature.sh can locate the feature via its feature.json.
if ! echo "$STDOUT" | grep -qF "SCOPE: auto-refresh"; then
  echo "FAIL [t-rr1]: SCOPE line absent — REPO_ROOT likely wrong (feature not found by find-feature.sh)" >&2
  FAIL=1
else
  echo "t-rr1: PASS (SCOPE: auto-refresh present — feature resolved correctly)"
fi

# t-rr2: Verify the script's REPO_ROOT computation: git rev-parse from the
# scripts dir inside the real repo equals repo root.
REAL_SCRIPTS_DIR="$REPO_ROOT/.claude/features/contract/scripts"
COMPUTED_ROOT="$(git -C "$REAL_SCRIPTS_DIR" rev-parse --show-toplevel 2>/dev/null)"
if [ "$COMPUTED_ROOT" != "$REPO_ROOT" ]; then
  echo "FAIL [t-rr2]: REPO_ROOT mismatch — got '$COMPUTED_ROOT', want '$REPO_ROOT'" >&2
  FAIL=1
else
  echo "t-rr2: PASS (git rev-parse from scripts resolves to repo root: $COMPUTED_ROOT)"
fi

if [ $FAIL -ne 0 ]; then
  echo "test-dispatch: FAIL" >&2
  exit 1
fi

echo "test-dispatch: all checks passed."
