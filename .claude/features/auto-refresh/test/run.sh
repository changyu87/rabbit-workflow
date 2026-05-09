#!/bin/bash
# End-to-end test of the auto-refresh capability.
# The hook computes REPO_ROOT from its own location ($(dirname BASH_SOURCE)/../..),
# so we copy the hook into a fixture tree at $TMPROOT/ws/.claude/hooks/ and
# drive it from there with a fixture CLAUDE.md and counter file.
set -u

REPO_ROOT="$(cd "$(dirname "$0")/../../../.." && pwd)"
ORIG_HOOK="$REPO_ROOT/.claude/hooks/rwf-refresh.sh"
TMPROOT="$(mktemp -d)"
trap 'rm -rf "$TMPROOT"' EXIT INT TERM

PASS=0; FAIL=0
ok() { echo "  ok   $*"; PASS=$((PASS+1)); }
ko() { echo "  FAIL $*"; FAIL=$((FAIL+1)); }

# t1: source hook script exists and is executable
if [ -x "$ORIG_HOOK" ]; then
  ok "t1: source hook exists and is executable"
else
  ko "t1: missing or non-exec: $ORIG_HOOK"
  echo "summary: $PASS passed, $FAIL failed"; exit 1
fi

# Build fixture workspace mirroring repo layout
WS="$TMPROOT/ws"
mkdir -p "$WS/.claude/hooks"
cp "$ORIG_HOOK" "$WS/.claude/hooks/rwf-refresh.sh"
chmod +x "$WS/.claude/hooks/rwf-refresh.sh"
HOOK="$WS/.claude/hooks/rwf-refresh.sh"

cat > "$WS/CLAUDE.md" <<'EOF'
# CLAUDE
@./.claude/philosophy.md
@./.claude/work-guide.md
EOF
echo "philosophy fixture content" > "$WS/.claude/philosophy.md"
echo "work-guide fixture content" > "$WS/.claude/work-guide.md"

# t2: under threshold -> hook is silent (count incremented, no JSON)
echo "0" > "$WS/.rwf-prompt-counter"
RWF_REFRESH_EVERY=10 bash "$HOOK" >"$TMPROOT/out" 2>"$TMPROOT/err"
rc=$?
counter=$(cat "$WS/.rwf-prompt-counter")
out_size=$(wc -c < "$TMPROOT/out")
if [ "$rc" = "0" ] && [ "$counter" = "1" ] && [ "$out_size" -lt 5 ]; then
  ok "t2: under threshold, counter=1, no output"
else
  ko "t2: rc=$rc counter=$counter out_size=$out_size out=$(cat "$TMPROOT/out")"
fi

# t3: at threshold -> hook emits JSON, counter reset, additionalContext non-empty
echo "9" > "$WS/.rwf-prompt-counter"
RWF_REFRESH_EVERY=10 bash "$HOOK" >"$TMPROOT/out" 2>"$TMPROOT/err"
rc=$?
counter=$(cat "$WS/.rwf-prompt-counter")
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
rm -f "$WS/.rwf-prompt-counter"
RWF_REFRESH_EVERY=10 bash "$HOOK" >/dev/null 2>"$TMPROOT/err"
rc=$?
counter=$(cat "$WS/.rwf-prompt-counter" 2>/dev/null || echo "missing")
[ "$counter" = "1" ] && ok "t4: missing counter initialized then incremented to 1" \
  || ko "t4: counter=$counter rc=$rc err=$(cat "$TMPROOT/err")"

# t5: with RWF_REFRESH_EVERY=1, every call refreshes
echo "0" > "$WS/.rwf-prompt-counter"
RWF_REFRESH_EVERY=1 bash "$HOOK" >"$TMPROOT/out" 2>"$TMPROOT/err"
rc=$?
out=$(cat "$TMPROOT/out")
echo "$out" | jq empty 2>/dev/null && refreshed=1 || refreshed=0
[ "$rc" = "0" ] && [ "$refreshed" = "1" ] \
  && ok "t5: threshold=1 refreshes immediately" \
  || ko "t5: rc=$rc refreshed=$refreshed out=$out"

# t6: systemMessage present in output JSON when refreshed
echo "0" > "$WS/.rwf-prompt-counter"
RWF_REFRESH_EVERY=1 bash "$HOOK" >"$TMPROOT/out" 2>"$TMPROOT/err"
sm=$(jq -r '.systemMessage // ""' "$TMPROOT/out" 2>/dev/null)
echo "$sm" | grep -q "rwf" && ok "t6: systemMessage announces refresh" \
  || ko "t6: sm='$sm'"

echo
echo "summary: $PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ] && exit 0 || exit 1
