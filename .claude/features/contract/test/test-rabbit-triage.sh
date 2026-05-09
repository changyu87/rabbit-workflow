#!/bin/bash
# test-rabbit-triage.sh — verify rabbit-triage.sh builds a valid triage prompt.

set -u

FEATURE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SCRIPT="$FEATURE_DIR/scripts/rabbit-triage.sh"
FAIL=0

# Build a minimal fixture feature dir in /tmp.
FIXTURE="$(mktemp -d)"
mkdir -p "$FIXTURE/docs/bugs/test-bug-1"
mkdir -p "$FIXTURE/docs/spec"

cat > "$FIXTURE/docs/bugs/test-bug-1/bug.json" <<'JSON'
{
  "bug_name": "test-bug-1",
  "status": "open",
  "related_feature": null,
  "summary": "Test bug for triage script validation",
  "filed_by": "test",
  "filed_at": "2026-05-09"
}
JSON

cat > "$FIXTURE/docs/spec/spec.md" <<'SPEC'
# test-feature spec
Minimal spec for triage test fixture.
SPEC

OUTPUT="$("$SCRIPT" "$FIXTURE" "test-bug-1" 2>&1)"
EXIT_CODE=$?

# Clean up fixture.
rm -rf "$FIXTURE"

if [ $EXIT_CODE -ne 0 ]; then
  echo "FAIL: rabbit-triage.sh exited with code $EXIT_CODE" >&2
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
check_contains "bug name" "test-bug-1"

if [ $FAIL -ne 0 ]; then
  echo "test-rabbit-triage: FAIL" >&2
  exit 1
fi

echo "test-rabbit-triage: all checks passed."
