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
[ -f "$FEATURE_DIR/feature.json" ]           || err "missing feature.json"
[ -f "$FEATURE_DIR/docs/spec/spec.md" ]      || err "missing docs/spec/spec.md"
[ -s "$FEATURE_DIR/docs/spec/spec.md" ]      || err "docs/spec/spec.md is empty"
[ -f "$FEATURE_DIR/docs/spec/contract.md" ]  || err "missing docs/spec/contract.md"
[ -s "$FEATURE_DIR/docs/spec/contract.md" ]  || err "docs/spec/contract.md is empty"
[ -d "$FEATURE_DIR/docs/bugs" ]              || err "missing docs/bugs/ directory"
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

OWNER=$(jq -r '.owner // ""' "$FEATURE_DIR/feature.json")
if [ -z "$OWNER" ]; then
  err "feature.json: missing owner"
elif jq -e '.owner | type == "object"' "$FEATURE_DIR/feature.json" >/dev/null 2>&1; then
  err "feature.json: owner must be a flat string, not an object"
fi

TDD_STATE=$(jq -r '.tdd_state // ""' "$FEATURE_DIR/feature.json")
case "$TDD_STATE" in
  spec|test-red|impl|test-green|review|merged|deprecated) ;;
  "")  err "feature.json: missing tdd_state" ;;
  *)   err "feature.json: invalid tdd_state '$TDD_STATE' (allowed: spec|test-red|impl|test-green|review|merged|deprecated)" ;;
esac

SUMMARY=$(jq -r '.summary // ""' "$FEATURE_DIR/feature.json")
[ -z "$SUMMARY" ] && err "feature.json: missing summary"

# surface must be an object with arrays: hooks, commands, agents, skills
jq -e '.surface | type == "object"' "$FEATURE_DIR/feature.json" >/dev/null 2>&1 \
  || err "feature.json: surface must be an object"
jq -e '.surface.hooks    | type == "array"' "$FEATURE_DIR/feature.json" >/dev/null 2>&1 \
  || err "feature.json: surface.hooks must be an array"
jq -e '.surface.commands | type == "array"' "$FEATURE_DIR/feature.json" >/dev/null 2>&1 \
  || err "feature.json: surface.commands must be an array"
jq -e '.surface.agents   | type == "array"' "$FEATURE_DIR/feature.json" >/dev/null 2>&1 \
  || err "feature.json: surface.agents must be an array"
jq -e '.surface.skills   | type == "array"' "$FEATURE_DIR/feature.json" >/dev/null 2>&1 \
  || err "feature.json: surface.skills must be an array"

BUGS_ROOT=$(jq -r '.bugs_root // ""' "$FEATURE_DIR/feature.json")
[ -z "$BUGS_ROOT" ] && err "feature.json: missing bugs_root"

CRITERION=$(jq -r '.deprecation_criterion // ""' "$FEATURE_DIR/feature.json")
[ -z "$CRITERION" ] && err "feature.json: missing deprecation_criterion"

if [ "$ERRORS" -gt 0 ]; then
  echo "FAIL: $ERRORS error(s) in $FEATURE_DIR" >&2
  exit 1
fi
echo "PASS: $FEATURE_DIR"
exit 0
