#!/usr/bin/env bash
# test-backlog-state-machine.sh — FAILING tests for the new state machine.
#
# State machine being tested:
#   open        -> in-progress   (--reason required)
#   open        -> refused       (--reason required)
#   in-progress -> implemented   (--reason required, --fix-commits required)
#   in-progress -> refused       (--reason required)
#   implemented -> reopened      (--reason required)
#   refused     -> reopened      (--reason required)
#   reopened    -> in-progress   (--reason required)
#   reopened    -> refused       (--reason required)
#
# Invalid/removed: done, cancelled
# Removed transition: open -> done (was valid before)
#
# ALL new tests (t_new1..t_new12) are expected to FAIL until the scripts are updated.

set -u

REPO_ROOT="$(git -C "$(dirname "${BASH_SOURCE[0]}")" rev-parse --show-toplevel 2>/dev/null)"
FEATURE_DIR="${REPO_ROOT}/.claude/features/rabbit-backlog"
SCRIPTS_DIR="${FEATURE_DIR}/scripts"
ITEM_STATUS="${SCRIPTS_DIR}/backlog-item-status.sh"

pass=0
fail=0

ok()     { echo "  PASS  $1"; pass=$((pass + 1)); }
fail_t() { echo "  FAIL  $1${2:+ -- $2}"; fail=$((fail + 1)); }

echo "=== test-backlog-state-machine.sh: new state machine ==="
echo ""

# Helper: create a temp dir with item.json at a given status
make_item_dir() {
    local status name tmpdir
    status="${1:-open}"
    name="${2:-DUMMY}"
    tmpdir="$(mktemp -d)"
    cat > "$tmpdir/item.json" <<JSON
{
  "name": "$name",
  "title": "test item",
  "status": "$status",
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
    echo "$tmpdir"
}

TMPDIRS=()
cleanup_tmpdirs() {
    local d
    for d in "${TMPDIRS[@]:-}"; do
        rm -rf "$d" 2>/dev/null || true
    done
}
trap cleanup_tmpdirs EXIT

# ── t_new1: `implemented` is a valid status ──
# Transition from in-progress with --reason and --fix-commits succeeds;
# item.json shows status="implemented".
T="t_new1: implemented is a valid status (in-progress -> implemented with --fix-commits)"
d="$(make_item_dir in-progress DUMMY-T1)"
TMPDIRS+=("$d")
if [ -x "$ITEM_STATUS" ]; then
    if "$ITEM_STATUS" set "$d" implemented --reason "shipped" --fix-commits "abc1234" 2>/dev/null; then
        status_val="$(jq -r '.status' "$d/item.json" 2>/dev/null)"
        if [ "$status_val" = "implemented" ]; then
            ok "$T"
        else
            fail_t "$T" "status in item.json is '$status_val', expected 'implemented'"
        fi
    else
        fail_t "$T" "command exited non-zero"
    fi
else
    fail_t "$T" "backlog-item-status.sh not found or not executable"
fi

# ── t_new2: `refused` is a valid status ──
# Transition from open with --reason succeeds; item.json shows status="refused".
T="t_new2: refused is a valid status (open -> refused with --reason)"
d="$(make_item_dir open DUMMY-T2)"
TMPDIRS+=("$d")
if [ -x "$ITEM_STATUS" ]; then
    if "$ITEM_STATUS" set "$d" refused --reason "not a real feature" 2>/dev/null; then
        status_val="$(jq -r '.status' "$d/item.json" 2>/dev/null)"
        if [ "$status_val" = "refused" ]; then
            ok "$T"
        else
            fail_t "$T" "status in item.json is '$status_val', expected 'refused'"
        fi
    else
        fail_t "$T" "command exited non-zero"
    fi
else
    fail_t "$T" "backlog-item-status.sh not found or not executable"
fi

# ── t_new3: `reopened` is a valid status ──
# Transition from implemented with --reason succeeds; item.json shows status="reopened".
T="t_new3: reopened is a valid status (implemented -> reopened with --reason)"
d="$(make_item_dir implemented DUMMY-T3)"
TMPDIRS+=("$d")
if [ -x "$ITEM_STATUS" ]; then
    if "$ITEM_STATUS" set "$d" reopened --reason "regression found" 2>/dev/null; then
        status_val="$(jq -r '.status' "$d/item.json" 2>/dev/null)"
        if [ "$status_val" = "reopened" ]; then
            ok "$T"
        else
            fail_t "$T" "status in item.json is '$status_val', expected 'reopened'"
        fi
    else
        fail_t "$T" "command exited non-zero on valid implemented->reopened transition"
    fi
else
    fail_t "$T" "backlog-item-status.sh not found or not executable"
fi

# ── t_new4: `done` is NOT a valid status ──
# Any attempt to set status to 'done' must exit non-zero.
T="t_new4: done is NOT a valid status (rejected)"
d="$(make_item_dir open DUMMY-T4)"
TMPDIRS+=("$d")
if [ -x "$ITEM_STATUS" ]; then
    if "$ITEM_STATUS" set "$d" done --reason "done" 2>/dev/null; then
        fail_t "$T" "command succeeded but 'done' should be rejected as invalid status"
    else
        ok "$T"
    fi
else
    fail_t "$T" "backlog-item-status.sh not found or not executable"
fi

# ── t_new5: `cancelled` is NOT a valid status ──
# Any attempt to set status to 'cancelled' must exit non-zero.
T="t_new5: cancelled is NOT a valid status (rejected)"
d="$(make_item_dir open DUMMY-T5)"
TMPDIRS+=("$d")
if [ -x "$ITEM_STATUS" ]; then
    if "$ITEM_STATUS" set "$d" cancelled --reason "cancelling" 2>/dev/null; then
        fail_t "$T" "command succeeded but 'cancelled' should be rejected as invalid status"
    else
        ok "$T"
    fi
else
    fail_t "$T" "backlog-item-status.sh not found or not executable"
fi

# ── t_new6: --reason is required on every set ──
# Omitting --reason on a valid transition (open -> in-progress) must exit non-zero.
T="t_new6: --reason is required on every set (omitting exits non-zero)"
d="$(make_item_dir open DUMMY-T6)"
TMPDIRS+=("$d")
if [ -x "$ITEM_STATUS" ]; then
    if "$ITEM_STATUS" set "$d" in-progress 2>/dev/null; then
        fail_t "$T" "command succeeded without --reason but should require it"
    else
        ok "$T"
    fi
else
    fail_t "$T" "backlog-item-status.sh not found or not executable"
fi

# ── t_new7: --fix-commits required when transitioning to implemented ──
# Providing --reason but omitting --fix-commits on in-progress -> implemented must exit non-zero.
T="t_new7: --fix-commits required when transitioning to implemented (missing exits non-zero)"
d="$(make_item_dir in-progress DUMMY-T7)"
TMPDIRS+=("$d")
if [ -x "$ITEM_STATUS" ]; then
    if "$ITEM_STATUS" set "$d" implemented --reason "shipped" 2>/dev/null; then
        fail_t "$T" "command succeeded without --fix-commits but should require it for 'implemented'"
    else
        ok "$T"
    fi
else
    fail_t "$T" "backlog-item-status.sh not found or not executable"
fi

# ── t_new8: --fix-commits is rejected for non-implemented transitions ──
# Passing --fix-commits on a non-implemented transition (open -> in-progress) must exit non-zero.
T="t_new8: --fix-commits rejected on non-implemented transitions (open -> in-progress)"
d="$(make_item_dir open DUMMY-T8)"
TMPDIRS+=("$d")
if [ -x "$ITEM_STATUS" ]; then
    if "$ITEM_STATUS" set "$d" in-progress --reason "starting" --fix-commits "abc1234" 2>/dev/null; then
        fail_t "$T" "command succeeded with --fix-commits on a non-implemented transition but should reject it"
    else
        ok "$T"
    fi
else
    fail_t "$T" "backlog-item-status.sh not found or not executable"
fi

# ── t_new9: implemented -> reopened is a valid transition ──
T="t_new9: implemented -> reopened is a valid transition"
d="$(make_item_dir implemented DUMMY-T9)"
TMPDIRS+=("$d")
if [ -x "$ITEM_STATUS" ]; then
    if "$ITEM_STATUS" set "$d" reopened --reason "found regression" 2>/dev/null; then
        status_val="$(jq -r '.status' "$d/item.json" 2>/dev/null)"
        if [ "$status_val" = "reopened" ]; then
            ok "$T"
        else
            fail_t "$T" "status in item.json is '$status_val', expected 'reopened'"
        fi
    else
        fail_t "$T" "command exited non-zero on valid implemented->reopened transition"
    fi
else
    fail_t "$T" "backlog-item-status.sh not found or not executable"
fi

# ── t_new10: refused -> reopened is a valid transition ──
T="t_new10: refused -> reopened is a valid transition"
d="$(make_item_dir refused DUMMY-T10)"
TMPDIRS+=("$d")
if [ -x "$ITEM_STATUS" ]; then
    if "$ITEM_STATUS" set "$d" reopened --reason "reconsidered" 2>/dev/null; then
        status_val="$(jq -r '.status' "$d/item.json" 2>/dev/null)"
        if [ "$status_val" = "reopened" ]; then
            ok "$T"
        else
            fail_t "$T" "status in item.json is '$status_val', expected 'reopened'"
        fi
    else
        fail_t "$T" "command exited non-zero on valid refused->reopened transition"
    fi
else
    fail_t "$T" "backlog-item-status.sh not found or not executable"
fi

# ── t_new11: reopened -> in-progress is a valid transition ──
T="t_new11: reopened -> in-progress is a valid transition"
d="$(make_item_dir reopened DUMMY-T11)"
TMPDIRS+=("$d")
if [ -x "$ITEM_STATUS" ]; then
    if "$ITEM_STATUS" set "$d" in-progress --reason "resuming work" 2>/dev/null; then
        status_val="$(jq -r '.status' "$d/item.json" 2>/dev/null)"
        if [ "$status_val" = "in-progress" ]; then
            ok "$T"
        else
            fail_t "$T" "status in item.json is '$status_val', expected 'in-progress'"
        fi
    else
        fail_t "$T" "command exited non-zero on valid reopened->in-progress transition"
    fi
else
    fail_t "$T" "backlog-item-status.sh not found or not executable"
fi

# ── t_new12: a git commit is created after a successful set transition ──
# Init a temp git repo, call `set`, verify HEAD advances (a commit was made).
T="t_new12: a git commit is created after a successful set transition"
GIT_TMPDIR="$(mktemp -d)"
TMPDIRS+=("$GIT_TMPDIR")
ITEM_SUBDIR="${GIT_TMPDIR}/item"
mkdir -p "$ITEM_SUBDIR"

# Init a bare git repo in the temp dir
git -C "$GIT_TMPDIR" init -q 2>/dev/null
git -C "$GIT_TMPDIR" config user.email "test@test.com"
git -C "$GIT_TMPDIR" config user.name "Test"

cat > "$ITEM_SUBDIR/item.json" <<'JSON'
{
  "name": "DUMMY-T12",
  "title": "t12 item",
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

# Create an initial commit so we have a base HEAD to compare against
git -C "$GIT_TMPDIR" add .
git -C "$GIT_TMPDIR" commit -qm "initial" 2>/dev/null

COMMIT_BEFORE="$(git -C "$GIT_TMPDIR" rev-parse HEAD 2>/dev/null)"

if [ -x "$ITEM_STATUS" ]; then
    if "$ITEM_STATUS" set "$ITEM_SUBDIR" in-progress --reason "starting" 2>/dev/null; then
        COMMIT_AFTER="$(git -C "$GIT_TMPDIR" rev-parse HEAD 2>/dev/null)"
        if [ "$COMMIT_BEFORE" != "$COMMIT_AFTER" ]; then
            ok "$T"
        else
            fail_t "$T" "HEAD did not advance after set (no commit was created)"
        fi
    else
        fail_t "$T" "set in-progress --reason starting exited non-zero"
    fi
else
    fail_t "$T" "backlog-item-status.sh not found or not executable"
fi

echo ""
echo "Results: $pass passed, $fail failed"
if [ "$fail" -gt 0 ]; then
    exit 1
fi
exit 0
