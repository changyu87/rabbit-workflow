#!/usr/bin/env bash
# test-backlog-e2e-tdd.sh
# TDD failing test: asserts that BACKLOG-001/item.json exists and is valid.
# Expected to FAIL until file-backlog-item.sh is implemented and run.
# Harness: ok/fail_t, "Results: N passed, N failed", exit 1 on any failure.

set -u

REPO_ROOT="$(git -C "$(dirname "${BASH_SOURCE[0]}")" rev-parse --show-toplevel 2>/dev/null)"
CAGE_DIR="${REPO_ROOT}/.claude/features/rabbit-cage"
ITEM_JSON="${CAGE_DIR}/docs/backlog/BACKLOG-001/item.json"

pass=0
fail=0

ok() {
    echo "  PASS t$1: $2"
    pass=$((pass + 1))
}

fail_t() {
    echo "  FAIL t$1: $2"
    fail=$((fail + 1))
}

echo "test-backlog-e2e-tdd.sh"

# t1: BACKLOG-001/item.json exists
if [ -f "${ITEM_JSON}" ]; then
    ok 1 "BACKLOG-001/item.json exists"
else
    fail_t 1 "BACKLOG-001/item.json does not exist (path: ${ITEM_JSON})"
fi

# t2: item.json contains valid JSON
if [ -f "${ITEM_JSON}" ] && python3 -c "import json; json.load(open('${ITEM_JSON}'))" 2>/dev/null; then
    ok 2 "item.json is valid JSON"
else
    fail_t 2 "item.json is missing or not valid JSON"
fi

# t3: item.json has name="BACKLOG-001"
if [ -f "${ITEM_JSON}" ] && python3 - "${ITEM_JSON}" <<'PYEOF' 2>/dev/null
import sys, json
data = json.load(open(sys.argv[1]))
sys.exit(0 if data.get("name") == "BACKLOG-001" else 1)
PYEOF
then
    ok 3 "item.json has name=\"BACKLOG-001\""
else
    fail_t 3 "item.json missing or name != \"BACKLOG-001\""
fi

# t4: item.json has status="open"
if [ -f "${ITEM_JSON}" ] && python3 - "${ITEM_JSON}" <<'PYEOF' 2>/dev/null
import sys, json
data = json.load(open(sys.argv[1]))
sys.exit(0 if data.get("status") == "open" else 1)
PYEOF
then
    ok 4 "item.json has status=\"open\""
else
    fail_t 4 "item.json missing or status != \"open\""
fi

# t5: item.json has priority="high"
if [ -f "${ITEM_JSON}" ] && python3 - "${ITEM_JSON}" <<'PYEOF' 2>/dev/null
import sys, json
data = json.load(open(sys.argv[1]))
sys.exit(0 if data.get("priority") == "high" else 1)
PYEOF
then
    ok 5 "item.json has priority=\"high\""
else
    fail_t 5 "item.json missing or priority != \"high\""
fi

# t6: item.json title contains the word "E2E"
if [ -f "${ITEM_JSON}" ] && python3 - "${ITEM_JSON}" <<'PYEOF' 2>/dev/null
import sys, json
data = json.load(open(sys.argv[1]))
title = data.get("title", "")
sys.exit(0 if "E2E" in title else 1)
PYEOF
then
    ok 6 "item.json title contains \"E2E\""
else
    fail_t 6 "item.json missing or title does not contain \"E2E\""
fi

echo ""
echo "Results: ${pass} passed, ${fail} failed"
if [ "${fail}" -gt 0 ]; then
    exit 1
fi
exit 0
