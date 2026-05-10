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

ITEM_002="${CAGE_DIR}/docs/backlog/BACKLOG-002/item.json"

# t7: BACKLOG-002/item.json exists
if [ -f "${ITEM_002}" ]; then
    ok 7 "BACKLOG-002/item.json exists"
else
    fail_t 7 "BACKLOG-002/item.json does not exist (path: ${ITEM_002})"
fi

# t8: BACKLOG-002 item.json has priority="medium" and title contains "philosophy"
if [ -f "${ITEM_002}" ] && python3 - "${ITEM_002}" <<'PYEOF' 2>/dev/null
import sys, json
data = json.load(open(sys.argv[1]))
ok = data.get("priority") == "medium" and "philosophy" in data.get("title", "")
sys.exit(0 if ok else 1)
PYEOF
then
    ok 8 "BACKLOG-002 item.json has priority=\"medium\" and title contains \"philosophy\""
else
    fail_t 8 "BACKLOG-002 item.json missing, priority != \"medium\", or title does not contain \"philosophy\""
fi

ITEM_003="${CAGE_DIR}/docs/backlog/BACKLOG-003/item.json"

# t9: BACKLOG-003/item.json exists
if [ -f "${ITEM_003}" ]; then
    ok 9 "BACKLOG-003/item.json exists"
else
    fail_t 9 "BACKLOG-003/item.json does not exist (path: ${ITEM_003})"
fi

# t10: BACKLOG-003 item.json has priority="low" and title contains "numbering"
if [ -f "${ITEM_003}" ] && python3 - "${ITEM_003}" <<'PYEOF' 2>/dev/null
import sys, json
data = json.load(open(sys.argv[1]))
ok = data.get("priority") == "low" and "numbering" in data.get("title", "")
sys.exit(0 if ok else 1)
PYEOF
then
    ok 10 "BACKLOG-003 item.json has priority=\"low\" and title contains \"numbering\""
else
    fail_t 10 "BACKLOG-003 item.json missing, priority != \"low\", or title does not contain \"numbering\""
fi

ITEM_004="${CAGE_DIR}/docs/backlog/BACKLOG-004/item.json"

# t11: BACKLOG-004/item.json exists
if [ -f "${ITEM_004}" ]; then
    ok 11 "BACKLOG-004/item.json exists"
else
    fail_t 11 "BACKLOG-004/item.json does not exist (path: ${ITEM_004})"
fi

# t12: BACKLOG-004 item.json has priority="medium" and title contains "R6"
if [ -f "${ITEM_004}" ] && python3 - "${ITEM_004}" <<'PYEOF' 2>/dev/null
import sys, json
data = json.load(open(sys.argv[1]))
ok = data.get("priority") == "medium" and "R6" in data.get("title", "")
sys.exit(0 if ok else 1)
PYEOF
then
    ok 12 "BACKLOG-004 item.json has priority=\"medium\" and title contains \"R6\""
else
    fail_t 12 "BACKLOG-004 item.json missing, priority != \"medium\", or title does not contain \"R6\""
fi

echo ""
echo "Results: ${pass} passed, ${fail} failed"
if [ "${fail}" -gt 0 ]; then
    exit 1
fi
exit 0
