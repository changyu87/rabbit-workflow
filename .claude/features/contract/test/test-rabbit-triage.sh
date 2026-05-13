#!/bin/bash
# test-rabbit-triage.sh — verify rabbit-triage.sh builds a valid triage prompt.
#
# Bug.json is stored at the centralized location:
#   <repo-root>/.claude/bugs/<feature-name>/<bug-name>/bug.json
# as written by rabbit-bug and per invariant 14.

set -u

FEATURE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SCRIPT="$FEATURE_DIR/scripts/rabbit-triage.sh"
REPO_ROOT="$(git -C "$FEATURE_DIR" rev-parse --show-toplevel 2>/dev/null)"
FAIL=0

# Use a test-specific feature name to avoid collisions with real feature bugs.
FIXTURE_FEATURE_NAME="contract-triage-basic-test-$$"
BUG_NAME="test-bug-$$"

# Build a minimal fixture feature dir in /tmp.
FIXTURE="$(mktemp -d)"
FIXTURE_NAMED="$(dirname "$FIXTURE")/$FIXTURE_FEATURE_NAME"
mv "$FIXTURE" "$FIXTURE_NAMED"
FIXTURE="$FIXTURE_NAMED"

mkdir -p "$FIXTURE/docs/spec"

cat > "$FIXTURE/docs/spec/spec.md" <<'SPEC'
# test-feature spec
Minimal spec for triage test fixture.
SPEC

# Create bug.json at the centralized location (per invariant 14 and rabbit-bug storage).
CENTRALIZED_BUG_DIR="$REPO_ROOT/.claude/bugs/$FIXTURE_FEATURE_NAME/$BUG_NAME"
mkdir -p "$CENTRALIZED_BUG_DIR"
cat > "$CENTRALIZED_BUG_DIR/bug.json" <<'JSON'
{
  "bug_name": "test-bug",
  "status": "open",
  "related_feature": null,
  "summary": "Test bug for triage script validation",
  "filed_by": "test",
  "filed_at": "2026-05-09"
}
JSON

cleanup() {
  rm -rf "$FIXTURE"
  rm -rf "$REPO_ROOT/.claude/bugs/$FIXTURE_FEATURE_NAME"
}
trap cleanup EXIT

OUTPUT="$("$SCRIPT" "$FIXTURE" "$BUG_NAME" 2>&1)"
EXIT_CODE=$?

if [ $EXIT_CODE -ne 0 ]; then
  echo "FAIL: rabbit-triage.sh exited with code $EXIT_CODE" >&2
  echo "Output: $OUTPUT" >&2
  FAIL=1
fi

check_contains() {
  local label="$1"
  local pattern="$2"
  if ! echo "$OUTPUT" | grep -qF "$pattern"; then
    echo "FAIL: output does not contain '$pattern' (check: $label)" >&2
    FAIL=1
  fi
}

check_contains "sentinel line" "RABBIT-POLICY-BLOCK-v1"
check_contains "triage request header" "TRIAGE REQUEST"
check_contains "bug name" "$BUG_NAME"

if [ $FAIL -ne 0 ]; then
  echo "test-rabbit-triage: FAIL" >&2
  exit 1
fi

echo "test-rabbit-triage: all checks passed."
