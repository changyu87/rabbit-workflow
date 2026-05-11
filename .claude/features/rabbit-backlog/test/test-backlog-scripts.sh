#!/usr/bin/env bash
# test-backlog-scripts.sh — failing tests for centralized storage + per-feature ID scheme.
# ALL tests are expected to FAIL until the new design is implemented.
#
# New design being tested:
#   - file-backlog-item.sh uses --related-feature <name> (not --dir / --name)
#   - Items written to .claude/backlogs/<feature-name>/<PREFIX>-BACKLOG-<N>/item.json
#   - ID scheme: <FEATURE-NAME-UPPERCASED>-BACKLOG-<N> (per-feature counter)
#   - feature.json must NOT contain bugs_root or backlog_root
#   - .claude/backlogs/rabbit-cage/ must exist with RABBIT-CAGE-BACKLOG-1..6

set -u

REPO_ROOT="$(git -C "$(dirname "${BASH_SOURCE[0]}")" rev-parse --show-toplevel 2>/dev/null)"
FEATURE_DIR="${REPO_ROOT}/.claude/features/rabbit-backlog"
SCRIPTS_DIR="${FEATURE_DIR}/scripts"
REGISTRY="${REPO_ROOT}/.claude/features/registry.json"
CENTRAL_BACKLOGS="${REPO_ROOT}/.claude/backlogs"

FILE_BACKLOG="${SCRIPTS_DIR}/file-backlog-item.sh"
ITEM_STATUS="${SCRIPTS_DIR}/backlog-item-status.sh"

pass=0
fail=0

ok() {
    echo "  PASS  $1"
    pass=$((pass + 1))
}

fail_t() {
    echo "  FAIL  $1${2:+ -- $2}"
    fail=$((fail + 1))
}

echo "=== test-backlog-scripts.sh: centralized storage + per-feature ID ==="
echo ""

# t1: scripts/file-backlog-item.sh exists and is executable
if [ -x "$FILE_BACKLOG" ]; then
    ok "t1: file-backlog-item.sh exists and is executable"
else
    fail_t "t1: file-backlog-item.sh exists and is executable" "not found or not executable: $FILE_BACKLOG"
fi

# t2: scripts/backlog-item-status.sh exists and is executable
if [ -x "$ITEM_STATUS" ]; then
    ok "t2: backlog-item-status.sh exists and is executable"
else
    fail_t "t2: backlog-item-status.sh exists and is executable" "not found or not executable: $ITEM_STATUS"
fi

# t3: file-backlog-item.sh --related-feature rabbit-backlog creates item at centralized path
# Expected path: .claude/backlogs/rabbit-backlog/RABBIT-BACKLOG-BACKLOG-1/item.json
EXPECTED_DIR="${CENTRAL_BACKLOGS}/rabbit-backlog/RABBIT-BACKLOG-BACKLOG-1"
EXPECTED_ITEM="${EXPECTED_DIR}/item.json"

# Remove any leftover from a previous partial run to get a clean counter
rm -rf "${CENTRAL_BACKLOGS}/rabbit-backlog" 2>/dev/null || true

if [ -x "$FILE_BACKLOG" ]; then
    if "$FILE_BACKLOG" --related-feature rabbit-backlog --title "Test item" 2>/dev/null; then
        if [ -f "$EXPECTED_ITEM" ]; then
            ok "t3: --related-feature creates .claude/backlogs/rabbit-backlog/RABBIT-BACKLOG-BACKLOG-1/item.json"
        else
            fail_t "t3: --related-feature creates .claude/backlogs/rabbit-backlog/RABBIT-BACKLOG-BACKLOG-1/item.json" \
                   "item.json not at expected path: $EXPECTED_ITEM"
        fi
    else
        fail_t "t3: --related-feature creates .claude/backlogs/rabbit-backlog/RABBIT-BACKLOG-BACKLOG-1/item.json" \
               "script exited non-zero"
    fi
else
    fail_t "t3: --related-feature creates .claude/backlogs/rabbit-backlog/RABBIT-BACKLOG-BACKLOG-1/item.json" \
           "script not found or not executable"
fi

# t4: created item.json has status=open, name=RABBIT-BACKLOG-BACKLOG-1, history[0].action=opened
if [ -f "$EXPECTED_ITEM" ]; then
    result=$(python3 - "$EXPECTED_ITEM" <<'PYEOF' 2>/dev/null
import sys, json
d = json.load(open(sys.argv[1]))
issues = []
if d.get("status") != "open":
    issues.append(f"status={d.get('status')!r} (want 'open')")
if d.get("name") != "RABBIT-BACKLOG-BACKLOG-1":
    issues.append(f"name={d.get('name')!r} (want 'RABBIT-BACKLOG-BACKLOG-1')")
h = d.get("history", [])
first_action = h[0].get("action") if h else "missing"
if first_action != "opened":
    issues.append(f"history[0].action={first_action!r} (want 'opened')")
print("; ".join(issues))
PYEOF
)
    if [ -z "$result" ]; then
        ok "t4: item.json has status=open, name=RABBIT-BACKLOG-BACKLOG-1, history[0].action=opened"
    else
        fail_t "t4: item.json has status=open, name=RABBIT-BACKLOG-BACKLOG-1, history[0].action=opened" "$result"
    fi
else
    fail_t "t4: item.json has status=open, name=RABBIT-BACKLOG-BACKLOG-1, history[0].action=opened" \
           "item.json not found (t3 prerequisite failed)"
fi

# t5: a second call creates RABBIT-BACKLOG-BACKLOG-2 (counter increments per-feature)
EXPECTED_ITEM2="${CENTRAL_BACKLOGS}/rabbit-backlog/RABBIT-BACKLOG-BACKLOG-2/item.json"

if [ -x "$FILE_BACKLOG" ]; then
    if "$FILE_BACKLOG" --related-feature rabbit-backlog --title "Second test item" 2>/dev/null; then
        if [ -f "$EXPECTED_ITEM2" ]; then
            ok "t5: second call creates RABBIT-BACKLOG-BACKLOG-2 (counter increments)"
        else
            fail_t "t5: second call creates RABBIT-BACKLOG-BACKLOG-2 (counter increments)" \
                   "item.json not at: $EXPECTED_ITEM2"
        fi
    else
        fail_t "t5: second call creates RABBIT-BACKLOG-BACKLOG-2 (counter increments)" \
               "script exited non-zero on second call"
    fi
else
    fail_t "t5: second call creates RABBIT-BACKLOG-BACKLOG-2 (counter increments)" \
           "script not found or not executable"
fi

# Clean up temporary items created by t3/t5 to avoid polluting .claude/backlogs
rm -rf "${CENTRAL_BACKLOGS}/rabbit-backlog" 2>/dev/null || true

# t6: --related-feature nonexistent-xyz fails with non-zero exit (registry validation)
if [ -x "$FILE_BACKLOG" ]; then
    if "$FILE_BACKLOG" --related-feature nonexistent-xyz --title "Should fail" 2>/dev/null; then
        fail_t "t6: --related-feature nonexistent-xyz fails with non-zero exit" \
               "command succeeded but should have failed (registry validation)"
    else
        ok "t6: --related-feature nonexistent-xyz fails with non-zero exit"
    fi
else
    fail_t "t6: --related-feature nonexistent-xyz fails with non-zero exit" \
           "script not found or not executable"
fi

# t7: backlog-item-status.sh set ITEM_DIR in-progress succeeds (existing behavior still works)
# The current script supports --dir / --name; if those are removed, this test probes
# whether the new interface still allows status transitions on an existing item directory.
TMPDIR_T7="$(mktemp -d)"
cleanup_all() {
    rm -rf "$TMPDIR_T7" "${TMPDIR_T8:-}"
}
trap cleanup_all EXIT

# Create a bare item.json directly so we can test status transitions independent of
# how the item was originally filed (avoids coupling to old --dir API).
cat > "$TMPDIR_T7/item.json" <<'JSON'
{
  "name": "DUMMY-T7",
  "title": "t7 item",
  "status": "open",
  "priority": "medium",
  "description": "",
  "owner": "test",
  "filed": "2026-05-11T00:00:00Z",
  "filed_by": "test",
  "closed": null,
  "history": [
    { "ts": "2026-05-11T00:00:00Z", "actor": "test", "action": "opened", "note": "initial filing" }
  ]
}
JSON

if [ -x "$ITEM_STATUS" ]; then
    if "$ITEM_STATUS" set "$TMPDIR_T7" in-progress 2>/dev/null; then
        ok "t7: backlog-item-status.sh set in-progress succeeds"
    else
        fail_t "t7: backlog-item-status.sh set in-progress succeeds" \
               "set in-progress exited non-zero"
    fi
else
    fail_t "t7: backlog-item-status.sh set in-progress succeeds" \
           "backlog-item-status.sh not found or not executable"
fi

# t8: backlog-item-status.sh direct open-to-done is denied (existing behavior)
TMPDIR_T8="$(mktemp -d)"

cat > "$TMPDIR_T8/item.json" <<'JSON'
{
  "name": "DUMMY-T8",
  "title": "t8 item",
  "status": "open",
  "priority": "low",
  "description": "",
  "owner": "test",
  "filed": "2026-05-11T00:00:00Z",
  "filed_by": "test",
  "closed": null,
  "history": [
    { "ts": "2026-05-11T00:00:00Z", "actor": "test", "action": "opened", "note": "initial filing" }
  ]
}
JSON

if [ -x "$ITEM_STATUS" ]; then
    if "$ITEM_STATUS" set "$TMPDIR_T8" done 2>/dev/null; then
        fail_t "t8: direct open-to-done is denied" \
               "transition succeeded but should be denied"
    else
        ok "t8: direct open-to-done is denied"
    fi
else
    fail_t "t8: direct open-to-done is denied" \
           "backlog-item-status.sh not found or not executable"
fi

# t9: feature.json does NOT contain bugs_root or backlog_root key
FEATURE_JSON="${FEATURE_DIR}/feature.json"
if [ -f "$FEATURE_JSON" ]; then
    result=$(python3 - "$FEATURE_JSON" <<'PYEOF' 2>/dev/null
import sys, json
d = json.load(open(sys.argv[1]))
found = [k for k in ("bugs_root", "backlog_root") if k in d]
print(", ".join(found))
PYEOF
)
    if [ -z "$result" ]; then
        ok "t9: feature.json does NOT contain bugs_root or backlog_root"
    else
        fail_t "t9: feature.json does NOT contain bugs_root or backlog_root" \
               "found forbidden keys: $result"
    fi
else
    fail_t "t9: feature.json does NOT contain bugs_root or backlog_root" \
           "feature.json not found: $FEATURE_JSON"
fi

# t10: .claude/backlogs/rabbit-cage/ exists with RABBIT-CAGE-BACKLOG-1 through RABBIT-CAGE-BACKLOG-6
CAGE_BACKLOGS="${CENTRAL_BACKLOGS}/rabbit-cage"
if [ -d "$CAGE_BACKLOGS" ]; then
    all_present=1
    missing=()
    for n in 1 2 3 4 5 6; do
        item="${CAGE_BACKLOGS}/RABBIT-CAGE-BACKLOG-${n}/item.json"
        if [ ! -f "$item" ]; then
            all_present=0
            missing+=("RABBIT-CAGE-BACKLOG-${n}")
        fi
    done
    if [ "$all_present" -eq 1 ]; then
        ok "t10: .claude/backlogs/rabbit-cage/ has RABBIT-CAGE-BACKLOG-1 through RABBIT-CAGE-BACKLOG-6"
    else
        fail_t "t10: .claude/backlogs/rabbit-cage/ has RABBIT-CAGE-BACKLOG-1 through RABBIT-CAGE-BACKLOG-6" \
               "missing: ${missing[*]}"
    fi
else
    fail_t "t10: .claude/backlogs/rabbit-cage/ has RABBIT-CAGE-BACKLOG-1 through RABBIT-CAGE-BACKLOG-6" \
           "directory does not exist: $CAGE_BACKLOGS"
fi

echo ""
echo "Results: $pass passed, $fail failed"
if [ "$fail" -gt 0 ]; then
    exit 1
fi
exit 0
