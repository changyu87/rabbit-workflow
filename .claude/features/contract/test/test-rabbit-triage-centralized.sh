#!/bin/bash
# test-rabbit-triage-centralized.sh — assert rabbit-triage.sh finds bug.json at
# <repo-root>/.claude/bugs/<feature-name>/<bug-name>/bug.json (centralized storage).
#
# Invariant 14: rabbit-triage.sh locates bug.json in the centralized .claude/bugs/
# directory, not in <feature-dir>/docs/bugs/.
#
# R3-compliant: no interactive constructs, fully automated.

set -u

FEATURE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SCRIPT="$FEATURE_DIR/scripts/rabbit-triage.sh"
REPO_ROOT="$(git -C "$FEATURE_DIR" rev-parse --show-toplevel 2>/dev/null)"
FAIL=0

# Use a test-specific feature name that won't collide with real features.
FIXTURE_FEATURE_NAME="contract-triage-test-fixture-$$"

# Build a minimal fixture feature dir in /tmp (spec only, no docs/bugs/).
FIXTURE_FEATURE_DIR="$(mktemp -d)"
mkdir -p "$FIXTURE_FEATURE_DIR/docs/spec"
cat > "$FIXTURE_FEATURE_DIR/docs/spec/spec.md" <<'SPEC'
# contract-triage-test-fixture spec
Minimal spec for centralized-triage test fixture.
SPEC

# Override FEATURE_BASENAME by using the fixture feature name as the feature dir basename.
# We do this by creating a symlink or a directory named after the fixture feature.
# Simpler: use a temp dir named after the fixture feature name.
FIXTURE_NAMED_DIR="$(dirname "$FIXTURE_FEATURE_DIR")/$FIXTURE_FEATURE_NAME"
mv "$FIXTURE_FEATURE_DIR" "$FIXTURE_NAMED_DIR"
FIXTURE_FEATURE_DIR="$FIXTURE_NAMED_DIR"

BUG_NAME="FIXTURE-BUG-$$"

# Create bug.json at the centralized location in the REAL repo root.
# (The .claude/bugs/ path is on the scope-guard allowlist — no scope marker needed.)
CENTRALIZED_BUG_DIR="$REPO_ROOT/.claude/bugs/$FIXTURE_FEATURE_NAME/$BUG_NAME"
mkdir -p "$CENTRALIZED_BUG_DIR"
cat > "$CENTRALIZED_BUG_DIR/bug.json" <<'JSON'
{
  "bug_name": "FIXTURE-BUG",
  "status": "open",
  "related_feature": "contract-triage-test-fixture",
  "summary": "Centralized bug for triage script validation",
  "filed_by": "test",
  "filed_at": "2026-05-13"
}
JSON

cleanup() {
  rm -rf "$FIXTURE_FEATURE_DIR"
  rm -rf "$REPO_ROOT/.claude/bugs/$FIXTURE_FEATURE_NAME"
}
trap cleanup EXIT

# Verify the old incorrect path does NOT have a bug.json.
OLD_BUG_PATH="$FIXTURE_FEATURE_DIR/docs/bugs/$BUG_NAME/bug.json"
if [ -f "$OLD_BUG_PATH" ]; then
  echo "FAIL: test setup error — bug.json exists at old path $OLD_BUG_PATH" >&2
  exit 1
fi

# Call rabbit-triage.sh — uses git to derive REPO_ROOT from the script's own location.
OUTPUT="$("$SCRIPT" "$FIXTURE_FEATURE_DIR" "$BUG_NAME" 2>&1)"
EXIT_CODE=$?

if [ $EXIT_CODE -ne 0 ]; then
  echo "FAIL: rabbit-triage.sh exited $EXIT_CODE when given centralized bug path" >&2
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
check_contains "bug content present" "Centralized bug for triage script validation"

if [ $FAIL -ne 0 ]; then
  echo "test-rabbit-triage-centralized: FAIL" >&2
  exit 1
fi

echo "test-rabbit-triage-centralized: all checks passed."
