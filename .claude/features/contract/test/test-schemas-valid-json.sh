#!/bin/bash
# test-schemas-valid-json.sh — verify all schema files are valid JSON.

set -u

FEATURE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SCHEMAS_DIR="$FEATURE_DIR/schemas"
FAIL=0

for schema in "$SCHEMAS_DIR"/*.json; do
  [ -f "$schema" ] || continue
  if command -v python3 >/dev/null 2>&1; then
    if ! python3 -c "import json,sys; json.load(open(sys.argv[1]))" "$schema" 2>/dev/null; then
      echo "FAIL: invalid JSON: $schema" >&2
      FAIL=1
    fi
  elif command -v jq >/dev/null 2>&1; then
    if ! jq . "$schema" > /dev/null 2>&1; then
      echo "FAIL: invalid JSON: $schema" >&2
      FAIL=1
    fi
  else
    echo "FAIL: neither python3 nor jq available; cannot validate JSON" >&2
    FAIL=1
    break
  fi
done

if [ $FAIL -ne 0 ]; then
  echo "test-schemas-valid-json: FAIL" >&2
  exit 1
fi

echo "test-schemas-valid-json: all schema files are valid JSON."
