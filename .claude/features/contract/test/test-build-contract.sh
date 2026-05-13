#!/usr/bin/env bash
# test-build-contract.sh — verify build-contract.json, its schema, and relink.sh deletion.
#
# t1: build-contract.json exists
# t2: build-contract.json is valid JSON
# t3: build-contract.json validates against build-contract.schema.json
# t4: all copy-file source paths declared in build-contract.json exist on disk
# t5: relink.sh does NOT exist at scripts/relink.sh

set -uo pipefail

FEATURE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPO_ROOT="$(git -C "$FEATURE_DIR" rev-parse --show-toplevel)"

CONTRACT="$FEATURE_DIR/build-contract.json"
SCHEMA="$FEATURE_DIR/schemas/build-contract.schema.json"
RELINK="$FEATURE_DIR/scripts/relink.sh"

pass=0; fail=0
ok()     { echo "  PASS t$1: $2"; pass=$((pass + 1)); }
fail_t() { echo "  FAIL t$1: $2"; fail=$((fail + 1)); }

echo "test-build-contract.sh"

# t1: build-contract.json exists
if [ -f "$CONTRACT" ]; then
  ok 1 "build-contract.json exists"
else
  fail_t 1 "build-contract.json does not exist at $CONTRACT"
fi

# t2: build-contract.json is valid JSON
if [ -f "$CONTRACT" ]; then
  if python3 -c "import json,sys; json.load(open(sys.argv[1]))" "$CONTRACT" 2>/dev/null; then
    ok 2 "build-contract.json is valid JSON"
  else
    fail_t 2 "build-contract.json is not valid JSON"
  fi
else
  fail_t 2 "build-contract.json is not valid JSON (file missing)"
fi

# t3: build-contract.json validates against build-contract.schema.json
if [ -f "$CONTRACT" ] && [ -f "$SCHEMA" ]; then
  VALID=0
  if python3 -c "import jsonschema" 2>/dev/null; then
    python3 - "$CONTRACT" "$SCHEMA" <<'PYEOF' 2>/dev/null && VALID=1
import json, sys, jsonschema
doc = json.load(open(sys.argv[1]))
schema = json.load(open(sys.argv[2]))
jsonschema.validate(doc, schema)
PYEOF
  else
    # Fallback: check required fields manually with python3
    python3 - "$CONTRACT" "$SCHEMA" <<'PYEOF' 2>/dev/null && VALID=1
import json, sys

doc = json.load(open(sys.argv[1]))
schema = json.load(open(sys.argv[2]))

required = schema.get("required", [])
for field in required:
    if field not in doc:
        sys.exit(1)

# Validate targets array
targets = doc.get("targets", [])
if not isinstance(targets, list):
    sys.exit(1)

for t in targets:
    for req in ["name", "type", "destination", "check_on_stop"]:
        if req not in t:
            sys.exit(1)
    if t["type"] not in ["copy-file", "generate-claude-md"]:
        sys.exit(1)
    if t["type"] == "copy-file" and "source" not in t:
        sys.exit(1)

sys.exit(0)
PYEOF
  fi
  if [ "$VALID" -eq 1 ]; then
    ok 3 "build-contract.json validates against build-contract.schema.json"
  else
    fail_t 3 "build-contract.json does not validate against build-contract.schema.json"
  fi
else
  fail_t 3 "build-contract.json validates against build-contract.schema.json (file(s) missing)"
fi

# t4: all copy-file source paths declared in build-contract.json exist on disk
if [ -f "$CONTRACT" ] && python3 -c "import json,sys; json.load(open(sys.argv[1]))" "$CONTRACT" 2>/dev/null; then
  T4_FAIL=0
  while IFS= read -r src; do
    full="$REPO_ROOT/$src"
    if [ ! -e "$full" ]; then
      fail_t 4 "copy-file source does not exist: $src"
      T4_FAIL=1
    fi
  done < <(python3 - "$CONTRACT" <<'PYEOF'
import json, sys
doc = json.load(open(sys.argv[1]))
for t in doc.get("targets", []):
    if t.get("type") == "copy-file":
        print(t["source"])
PYEOF
  )
  if [ "$T4_FAIL" -eq 0 ]; then
    ok 4 "all copy-file source paths exist on disk"
  fi
else
  fail_t 4 "all copy-file source paths exist on disk (build-contract.json missing or invalid)"
fi

# t5: relink.sh does NOT exist
if [ ! -f "$RELINK" ]; then
  ok 5 "relink.sh does not exist at scripts/relink.sh"
else
  fail_t 5 "relink.sh still exists at $RELINK (should be deleted)"
fi

echo ""
echo "Results: $pass passed, $fail failed"
[ "$fail" -eq 0 ]
