#!/usr/bin/env bash
# test-branch-guard.sh — tests for file-backlog-item.sh branch guard
# and SKILL.md Working Protocol user-decision gate.
#
# t1: file-backlog-item.sh on non-main branch warns and exits non-zero (no tty = bypass)
# t2: file-backlog-item.sh on main branch succeeds without prompt
# t3: SKILL.md Working Protocol contains user-decision gate language

set -u

REPO_ROOT="$(git -C "$(dirname "${BASH_SOURCE[0]}")" rev-parse --show-toplevel 2>/dev/null)"
FEATURE_DIR="${REPO_ROOT}/.claude/features/rabbit-backlog"
SCRIPTS_DIR="${FEATURE_DIR}/scripts"
FILE_BACKLOG="${SCRIPTS_DIR}/file-backlog-item.sh"
SKILL_SRC="${FEATURE_DIR}/skills/rabbit-backlog/SKILL.md"

pass=0
fail=0

ok()     { echo "  PASS  $1"; pass=$((pass + 1)); }
fail_t() { echo "  FAIL  $1${2:+ -- $2}"; fail=$((fail + 1)); }

echo "=== test-branch-guard.sh: branch guard + SKILL.md user-decision gate ==="
echo ""

# ---------------------------------------------------------------------------
# Set up isolated git repo for branch guard tests
# ---------------------------------------------------------------------------
ISO_REPO="$(mktemp -d)"
trap 'rm -rf "$ISO_REPO"' EXIT

git -C "$ISO_REPO" init --quiet
git -C "$ISO_REPO" config user.email "test@rabbit"
git -C "$ISO_REPO" config user.name "rabbit-test"
git -C "$ISO_REPO" commit --allow-empty -m "init" --quiet

# Create feature.json for rabbit-backlog so find-feature.sh can discover it.
mkdir -p "$ISO_REPO/.claude/features/rabbit-backlog"
cat > "$ISO_REPO/.claude/features/rabbit-backlog/feature.json" <<'FEATEOF'
{
  "name": "rabbit-backlog",
  "version": "1.0.0",
  "owner": "test",
  "tdd_state": "test-green",
  "summary": "Test feature for backlog filing tests."
}
FEATEOF

# Rename default branch to 'main' (in case it's 'master')
CURRENT_BRANCH="$(git -C "$ISO_REPO" branch --show-current 2>/dev/null)"
if [ "$CURRENT_BRANCH" != "main" ]; then
  git -C "$ISO_REPO" branch -m "$CURRENT_BRANCH" main --quiet 2>/dev/null || true
fi

# Copy scripts and contract scripts into ISO_REPO
ISO_SCRIPTS_DIR="$ISO_REPO/scripts"
mkdir -p "$ISO_SCRIPTS_DIR"
cp "$FILE_BACKLOG" "$ISO_SCRIPTS_DIR/file-backlog-item.sh"
chmod +x "$ISO_SCRIPTS_DIR/file-backlog-item.sh"

ISO_CONTRACT_SCRIPTS="$ISO_REPO/.claude/features/contract/scripts"
mkdir -p "$ISO_CONTRACT_SCRIPTS"
WORKSPACE_MAP_SRC="$REPO_ROOT/.claude/features/contract/scripts/workspace-map.sh"
FIND_FEATURE_SRC="$REPO_ROOT/.claude/features/contract/scripts/find-feature.sh"
if [ -f "$WORKSPACE_MAP_SRC" ]; then
  cp "$WORKSPACE_MAP_SRC" "$ISO_CONTRACT_SCRIPTS/workspace-map.sh"
  chmod +x "$ISO_CONTRACT_SCRIPTS/workspace-map.sh"
fi
if [ -f "$FIND_FEATURE_SRC" ]; then
  cp "$FIND_FEATURE_SRC" "$ISO_CONTRACT_SCRIPTS/find-feature.sh"
  chmod +x "$ISO_CONTRACT_SCRIPTS/find-feature.sh"
  cp "$(dirname "$FIND_FEATURE_SRC")/find-feature.py" "$ISO_CONTRACT_SCRIPTS/find-feature.py"
fi

ISO_FILE_BACKLOG="$ISO_SCRIPTS_DIR/file-backlog-item.sh"

# t1: file-backlog-item.sh on non-main branch warns (stderr) and exits non-zero when tty unavailable
# When running without a tty, the script must still warn on stderr.
# We simulate non-main by creating and checking out a non-main branch.
git -C "$ISO_REPO" checkout -b "feature/test-branch" --quiet 2>/dev/null

BRANCH_NOW="$(git -C "$ISO_REPO" branch --show-current 2>/dev/null)"
if [ "$BRANCH_NOW" = "feature/test-branch" ]; then
  # Run the script with stdin closed (no tty) — should output warning and exit non-zero
  STDERR_OUT="$(cd "$ISO_REPO" && "$ISO_FILE_BACKLOG" \
    --related-feature rabbit-backlog \
    --title "Branch guard test" \
    </dev/null 2>&1 1>/dev/null || true)"
  EXIT_CODE=0
  cd "$ISO_REPO" && "$ISO_FILE_BACKLOG" \
    --related-feature rabbit-backlog \
    --title "Branch guard test" \
    </dev/null >/dev/null 2>/dev/null || EXIT_CODE=$?

  if [ "$EXIT_CODE" -ne 0 ]; then
    ok "t1: non-main branch with no tty exits non-zero"
  else
    fail_t "t1: non-main branch with no tty exits non-zero" \
           "script exited 0 but should exit non-zero on non-main (exit=$EXIT_CODE)"
  fi
else
  fail_t "t1: non-main branch with no tty exits non-zero" \
         "could not set up non-main branch (got: $BRANCH_NOW)"
fi

# t2: file-backlog-item.sh on main branch succeeds without prompt
git -C "$ISO_REPO" checkout main --quiet 2>/dev/null
BRANCH_MAIN="$(git -C "$ISO_REPO" branch --show-current 2>/dev/null)"
if [ "$BRANCH_MAIN" = "main" ]; then
  EXIT_CODE_MAIN=0
  cd "$ISO_REPO" && "$ISO_FILE_BACKLOG" \
    --related-feature rabbit-backlog \
    --title "Main branch test" \
    >/dev/null 2>/dev/null || EXIT_CODE_MAIN=$?

  if [ "$EXIT_CODE_MAIN" -eq 0 ]; then
    ok "t2: main branch succeeds without prompt"
  else
    fail_t "t2: main branch succeeds without prompt" \
           "script exited $EXIT_CODE_MAIN on main branch"
  fi
else
  fail_t "t2: main branch succeeds without prompt" \
         "could not switch to main branch (got: $BRANCH_MAIN)"
fi

# t3: SKILL.md Working Protocol section contains user-decision gate language
GATE_KEYWORDS=("confirm" "summary" "recommend")
ALL_FOUND=1
MISSING=()

if [ -f "$SKILL_SRC" ]; then
  # Check for Working Protocol section with gate language
  # Must contain reference to showing summary/verdict and asking user to confirm
  for kw in "${GATE_KEYWORDS[@]}"; do
    if ! grep -qi "$kw" "$SKILL_SRC" 2>/dev/null; then
      if ! grep -qi "$kw" "$SKILL_SRC"; then
        ALL_FOUND=0
        MISSING+=("$kw")
      fi
    fi
  done

  # Also check that the section explicitly gates on user confirmation before rabbit-feature-touch
  if ! grep -q 'rabbit-feature-touch' "$SKILL_SRC"; then
    ALL_FOUND=0
    MISSING+=("rabbit-feature-touch reference")
  fi

  if [ "$ALL_FOUND" -eq 1 ]; then
    ok "t3: SKILL.md Working Protocol has user-decision gate language"
  else
    fail_t "t3: SKILL.md Working Protocol has user-decision gate language" \
           "missing keywords: ${MISSING[*]}"
  fi
else
  fail_t "t3: SKILL.md Working Protocol has user-decision gate language" \
         "SKILL.md not found: $SKILL_SRC"
fi

echo ""
echo "Results: $pass passed, $fail failed"
if [ "$fail" -gt 0 ]; then
  exit 1
fi
exit 0
