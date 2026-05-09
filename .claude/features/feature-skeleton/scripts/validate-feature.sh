#!/bin/bash
# validate-feature.sh — verify a feature directory against the feature-skeleton schema.
#
# Usage: validate-feature.sh <feature-dir>
#
# Exit codes:
#   0  pass
#   1  validation error(s); details on stderr
#   2  invocation error (bad usage, missing dir)

set -u

FEATURE_DIR="${1:-}"
if [ -z "$FEATURE_DIR" ]; then
  echo "usage: validate-feature.sh <feature-dir>" >&2
  exit 2
fi
if [ ! -d "$FEATURE_DIR" ]; then
  echo "ERROR: not a directory: $FEATURE_DIR" >&2
  exit 2
fi

EXPECTED_NAME="$(basename "$FEATURE_DIR")"
ERRORS=0
err() { echo "ERROR: $*" >&2; ERRORS=$((ERRORS + 1)); }

# Required files / dirs
[ -f "$FEATURE_DIR/feature.json" ]  || err "missing feature.json"
[ -f "$FEATURE_DIR/spec.md" ]       || err "missing spec.md"
[ -f "$FEATURE_DIR/contract.md" ]   || err "missing contract.md"
[ -d "$FEATURE_DIR/test" ]          || err "missing test/ directory"
if [ -f "$FEATURE_DIR/test/run.sh" ]; then
  [ -x "$FEATURE_DIR/test/run.sh" ] || err "test/run.sh not executable"
else
  err "missing test/run.sh"
fi

# Bail early if feature.json is absent or invalid JSON.
if [ ! -f "$FEATURE_DIR/feature.json" ]; then
  echo "FAIL: $ERRORS error(s) in $FEATURE_DIR" >&2
  exit 1
fi
if ! jq empty "$FEATURE_DIR/feature.json" 2>/dev/null; then
  err "feature.json is not valid JSON"
  echo "FAIL: $ERRORS error(s) in $FEATURE_DIR" >&2
  exit 1
fi

# Field-by-field checks against feature.json.
NAME=$(jq -r '.name // ""' "$FEATURE_DIR/feature.json")
[ -z "$NAME" ] && err "feature.json: missing name"
[ -n "$NAME" ] && [ "$NAME" != "$EXPECTED_NAME" ] && \
  err "feature.json: name '$NAME' does not match directory name '$EXPECTED_NAME'"

VERSION=$(jq -r '.version // ""' "$FEATURE_DIR/feature.json")
if [ -z "$VERSION" ]; then
  err "feature.json: missing version"
elif ! echo "$VERSION" | grep -qE '^[0-9]+\.[0-9]+\.[0-9]+$'; then
  err "feature.json: version '$VERSION' is not semver (X.Y.Z)"
fi

OWNER=$(jq -r '.owner.primary // ""' "$FEATURE_DIR/feature.json")
[ -z "$OWNER" ] && err "feature.json: missing owner.primary"

STATUS=$(jq -r '.status // ""' "$FEATURE_DIR/feature.json")
case "$STATUS" in
  active|experimental|deprecated|archived) ;;
  "")  err "feature.json: missing status" ;;
  *)   err "feature.json: invalid status '$STATUS' (allowed: active|experimental|deprecated|archived)" ;;
esac

TDD_STATE=$(jq -r '.tdd_state // ""' "$FEATURE_DIR/feature.json")
case "$TDD_STATE" in
  spec|test-red|impl|test-green|review|merged|deprecated) ;;
  "")  err "feature.json: missing tdd_state" ;;
  *)   err "feature.json: invalid tdd_state '$TDD_STATE' (allowed: spec|test-red|impl|test-green|review|merged|deprecated)" ;;
esac

CRITERION=$(jq -r '.deprecation.criterion // ""' "$FEATURE_DIR/feature.json")
[ -z "$CRITERION" ] && err "feature.json: missing deprecation.criterion"

# Contract arrays must exist as arrays (empty is fine).
jq -e '.contract.reads   | type == "array"' "$FEATURE_DIR/feature.json" >/dev/null 2>&1 || err "feature.json: contract.reads must be an array"
jq -e '.contract.writes  | type == "array"' "$FEATURE_DIR/feature.json" >/dev/null 2>&1 || err "feature.json: contract.writes must be an array"
jq -e '.contract.invokes | type == "array"' "$FEATURE_DIR/feature.json" >/dev/null 2>&1 || err "feature.json: contract.invokes must be an array"

CREATED=$(jq -r '.created // ""' "$FEATURE_DIR/feature.json")
if [ -z "$CREATED" ]; then
  err "feature.json: missing created"
elif ! echo "$CREATED" | grep -qE '^[0-9]{4}-[0-9]{2}-[0-9]{2}$'; then
  err "feature.json: created '$CREATED' is not YYYY-MM-DD"
fi

UPDATED=$(jq -r '.updated // ""' "$FEATURE_DIR/feature.json")
if [ -z "$UPDATED" ]; then
  err "feature.json: missing updated"
elif ! echo "$UPDATED" | grep -qE '^[0-9]{4}-[0-9]{2}-[0-9]{2}$'; then
  err "feature.json: updated '$UPDATED' is not YYYY-MM-DD"
fi

if [ "$ERRORS" -gt 0 ]; then
  echo "FAIL: $ERRORS error(s) in $FEATURE_DIR" >&2
  exit 1
fi
echo "PASS: $FEATURE_DIR"
exit 0
