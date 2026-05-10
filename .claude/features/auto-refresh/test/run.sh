#!/bin/bash
# End-to-end test of the auto-refresh capability.
# The hook computes REPO_ROOT from its own location ($(dirname BASH_SOURCE)/../..),
# so we copy the hook into a fixture tree at $TMPROOT/ws/.claude/hooks/ and
# drive it from there with a fixture CLAUDE.md and counter file.
#
# Forward/back-compatible across the naming-convention rename: detects whether
# the repo has rbt-refresh.sh (new) or rwf-refresh.sh (legacy) and uses the
# matching counter file name, env var, and systemMessage tag.
set -u

REPO_ROOT="${RABBIT_ROOT:-$(git -C "$(dirname "$0")" rev-parse --show-toplevel 2>/dev/null)}"
TMPROOT="$(mktemp -d)"
trap 'rm -rf "$TMPROOT"' EXIT INT TERM

PASS=0; FAIL=0
ok() { echo "  ok   $*"; PASS=$((PASS+1)); }
ko() { echo "  FAIL $*"; FAIL=$((FAIL+1)); }

# Detect which variant of the hook is present in this repo.
if [ -x "$REPO_ROOT/.claude/hooks/rbt-refresh.sh" ]; then
  ORIG_HOOK="$REPO_ROOT/.claude/hooks/rbt-refresh.sh"
  HOOK_NAME="rbt-refresh.sh"
  COUNTER_NAME=".rbt-prompt-counter"
  ENV_VAR="RBT_REFRESH_EVERY"
  SM_TAG="rbt"
elif [ -x "$REPO_ROOT/.claude/hooks/rwf-refresh.sh" ]; then
  ORIG_HOOK="$REPO_ROOT/.claude/hooks/rwf-refresh.sh"
  HOOK_NAME="rwf-refresh.sh"
  COUNTER_NAME=".rwf-prompt-counter"
  ENV_VAR="RWF_REFRESH_EVERY"
  SM_TAG="rwf"
else
  echo "ERROR: no auto-refresh hook found at .claude/hooks/{rbt,rwf}-refresh.sh" >&2
  exit 1
fi

# t1: source hook script exists and is executable
ok "t1: source hook exists and is executable ($HOOK_NAME)"

# Build fixture workspace mirroring repo layout
WS="$TMPROOT/ws"
mkdir -p "$WS/.claude/hooks"
cp "$ORIG_HOOK" "$WS/.claude/hooks/$HOOK_NAME"
chmod +x "$WS/.claude/hooks/$HOOK_NAME"
HOOK="$WS/.claude/hooks/$HOOK_NAME"
COUNTER="$WS/$COUNTER_NAME"

cat > "$WS/CLAUDE.md" <<'EOF'
# CLAUDE
@./.claude/philosophy.md
@./.claude/work-guide.md
EOF
echo "philosophy fixture content" > "$WS/.claude/philosophy.md"
echo "work-guide fixture content" > "$WS/.claude/work-guide.md"

# t2: under threshold -> hook is silent (count incremented, no JSON)
echo "0" > "$COUNTER"
env "$ENV_VAR=10" RABBIT_ROOT="$WS" bash "$HOOK" >"$TMPROOT/out" 2>"$TMPROOT/err"
rc=$?
counter=$(cat "$COUNTER")
out_size=$(wc -c < "$TMPROOT/out")
if [ "$rc" = "0" ] && [ "$counter" = "1" ] && [ "$out_size" -lt 5 ]; then
  ok "t2: under threshold, counter=1, no output"
else
  ko "t2: rc=$rc counter=$counter out_size=$out_size out=$(cat "$TMPROOT/out")"
fi

# t3: at threshold -> hook emits JSON, counter reset, additionalContext non-empty
echo "9" > "$COUNTER"
env "$ENV_VAR=10" RABBIT_ROOT="$WS" bash "$HOOK" >"$TMPROOT/out" 2>"$TMPROOT/err"
rc=$?
counter=$(cat "$COUNTER")
out=$(cat "$TMPROOT/out")
ctx=""
if echo "$out" | jq empty 2>/dev/null; then
  ctx=$(echo "$out" | jq -r '.additionalContext // ""')
fi
if [ "$rc" = "0" ] && [ "$counter" = "0" ] && [ -n "$ctx" ] && \
   echo "$ctx" | grep -q "philosophy fixture content"; then
  ok "t3: at threshold, counter reset, JSON additionalContext includes file body"
else
  ko "t3: rc=$rc counter=$counter ctx_len=${#ctx} out=$out"
fi

# t4: counter file initialized to 0 if missing
rm -f "$COUNTER"
env "$ENV_VAR=10" RABBIT_ROOT="$WS" bash "$HOOK" >/dev/null 2>"$TMPROOT/err"
rc=$?
counter=$(cat "$COUNTER" 2>/dev/null || echo "missing")
[ "$counter" = "1" ] && ok "t4: missing counter initialized then incremented to 1" \
  || ko "t4: counter=$counter rc=$rc err=$(cat "$TMPROOT/err")"

# t5: with $ENV_VAR=1, every call refreshes
echo "0" > "$COUNTER"
env "$ENV_VAR=1" RABBIT_ROOT="$WS" bash "$HOOK" >"$TMPROOT/out" 2>"$TMPROOT/err"
rc=$?
out=$(cat "$TMPROOT/out")
echo "$out" | jq empty 2>/dev/null && refreshed=1 || refreshed=0
[ "$rc" = "0" ] && [ "$refreshed" = "1" ] \
  && ok "t5: threshold=1 refreshes immediately" \
  || ko "t5: rc=$rc refreshed=$refreshed out=$out"

# t6: systemMessage present in output JSON when refreshed; tag matches variant
echo "0" > "$COUNTER"
env "$ENV_VAR=1" RABBIT_ROOT="$WS" bash "$HOOK" >"$TMPROOT/out" 2>"$TMPROOT/err"
sm=$(jq -r '.systemMessage // ""' "$TMPROOT/out" 2>/dev/null)
echo "$sm" | grep -q "$SM_TAG" && ok "t6: systemMessage announces refresh ([$SM_TAG])" \
  || ko "t6: sm='$sm'"

echo
echo "summary: $PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ] && exit 0 || exit 1
