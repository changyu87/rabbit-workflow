#!/usr/bin/env bash
# test-rabbit-print-schema.sh — tests for rabbit-print.schema.json

set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SCHEMAS_DIR="$SCRIPT_DIR/../schemas"
SCHEMA_FILE="$SCHEMAS_DIR/rabbit-print.schema.json"

FAIL=0
ok()  { echo "  ok   $*"; }
fail() { echo "  FAIL $*"; FAIL=1; }

# t1: schema file exists
[ -f "$SCHEMA_FILE" ] && ok "t1: rabbit-print.schema.json exists" || fail "t1: rabbit-print.schema.json missing at $SCHEMA_FILE"

# t2: schema is valid JSON
if [ -f "$SCHEMA_FILE" ]; then
  python3 -m json.tool "$SCHEMA_FILE" >/dev/null 2>&1 \
    && ok "t2: rabbit-print.schema.json is valid JSON" \
    || fail "t2: rabbit-print.schema.json is not valid JSON"
fi

# t3: schema has a "format" field describing the [rabbit] pattern
if [ -f "$SCHEMA_FILE" ]; then
  python3 -c "import json; d=json.load(open('$SCHEMA_FILE')); assert 'format' in d, 'missing format'" 2>/dev/null \
    && ok "t3: schema has 'format' field" \
    || fail "t3: schema missing 'format' field"
fi

# t4: schema has a "colors" field with "normal" and "alert" keys
if [ -f "$SCHEMA_FILE" ]; then
  python3 -c "
import json
d = json.load(open('$SCHEMA_FILE'))
colors = d.get('colors', {})
assert 'normal' in colors, 'missing normal'
assert 'alert' in colors, 'missing alert'
" 2>/dev/null \
    && ok "t4: schema colors has 'normal' and 'alert' keys" \
    || fail "t4: schema colors missing 'normal' or 'alert'"
fi

# t5: schema has a "version" field
if [ -f "$SCHEMA_FILE" ]; then
  python3 -c "import json; d=json.load(open('$SCHEMA_FILE')); assert 'version' in d, 'missing version'" 2>/dev/null \
    && ok "t5: schema has 'version' field" \
    || fail "t5: schema missing 'version' field"
fi

if [ $FAIL -ne 0 ]; then
  echo "test-rabbit-print-schema: FAIL"
  exit 1
fi
echo "test-rabbit-print-schema: all checks passed."
