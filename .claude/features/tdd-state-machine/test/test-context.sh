#!/bin/bash
# End-to-end test of tdd-context.sh: emits machine-first JSON describing the
# feature's current TDD state for subagent prompts.
set -u

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
FEATURE_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
CTX="$FEATURE_DIR/scripts/tdd-context.sh"
TMPROOT="$(mktemp -d)"
trap 'rm -rf "$TMPROOT"' EXIT INT TERM

PASS=0; FAIL=0
ok() { echo "  ok   $*"; PASS=$((PASS+1)); }
ko() { echo "  FAIL $*"; FAIL=$((FAIL+1)); }

fix() {
  local d="$1" n="$2" s="$3"
  mkdir -p "$d/test"
  cat > "$d/feature.json" <<JSON
{
  "name": "$n",
  "version": "0.1.0",
  "owner": { "primary": "test" },
  "status": "active",
  "tdd_state": "$s",
  "deprecation": { "criterion": "fixture" },
  "contract": { "reads": [], "writes": [], "invokes": [] },
  "created": "2026-05-08",
  "updated": "2026-05-08"
}
JSON
  echo > "$d/spec.md"; echo > "$d/contract.md"
  printf '#!/bin/bash\nexit 0\n' > "$d/test/run.sh"; chmod +x "$d/test/run.sh"
}

run() { "$CTX" "$@" 2>"$TMPROOT/stderr" >"$TMPROOT/stdout"; echo $?; }

# c1: emits valid JSON with required fields
c1() {
  local d="$TMPROOT/c1"; fix "$d" c1 impl
  local rc; rc=$(run "$d")
  [ "$rc" = "0" ] || { ko "c1: rc=$rc"; return; }
  local out; out="$(cat "$TMPROOT/stdout")"
  echo "$out" | jq empty >/dev/null 2>&1 || { ko "c1: not valid JSON: $out"; return; }
  local fname; fname=$(echo "$out" | jq -r '.feature_name // ""')
  local cs;    cs=$(echo "$out" | jq -r '.current_state // ""')
  local ans;   ans=$(echo "$out" | jq -r '.allowed_next_states | type')
  local guide; guide=$(echo "$out" | jq -r '.guidance // ""')
  if [ "$fname" = "c1" ] && [ "$cs" = "impl" ] && [ "$ans" = "array" ] && [ -n "$guide" ]; then
    ok "c1: JSON has feature_name, current_state, allowed_next_states[], guidance"
  else
    ko "c1: fname=$fname cs=$cs ans=$ans guide_len=${#guide}"
  fi
}

# c2: --text flag emits human-readable view (non-JSON)
c2() {
  local d="$TMPROOT/c2"; fix "$d" c2 spec
  local rc; rc=$(run --text "$d")
  [ "$rc" = "0" ] || { ko "c2: rc=$rc"; return; }
  local out; out="$(cat "$TMPROOT/stdout")"
  echo "$out" | jq empty >/dev/null 2>&1 && { ko "c2: --text should NOT be JSON"; return; }
  echo "$out" | grep -qi "spec" && echo "$out" | grep -qi "next" \
    && ok "c2: --text emits human view with state and next" \
    || ko "c2: missing keywords; out=$out"
}

# c3: guidance differs by state (test-red guides toward impl; spec-update guides toward spec edit)
c3() {
  local d1="$TMPROOT/c3a"; fix "$d1" c3a test-red
  local d2="$TMPROOT/c3b"; fix "$d2" c3b spec-update
  run "$d1" >/dev/null
  local g1; g1=$(jq -r '.guidance' "$TMPROOT/stdout")
  cp "$TMPROOT/stdout" "$TMPROOT/c3a-out"
  run "$d2" >/dev/null
  local g2; g2=$(jq -r '.guidance' "$TMPROOT/stdout")
  if [ -n "$g1" ] && [ -n "$g2" ] && [ "$g1" != "$g2" ]; then
    ok "c3: guidance differs by state"
  else
    ko "c3: g1='$g1' g2='$g2'"
  fi
}

# c4: includes the deprecation criterion (so subagents are aware of EOL)
c4() {
  local d="$TMPROOT/c4"; fix "$d" c4 impl
  run "$d" >/dev/null
  local crit; crit=$(jq -r '.deprecation_criterion // ""' "$TMPROOT/stdout")
  [ "$crit" = "fixture" ] \
    && ok "c4: deprecation_criterion surfaced" \
    || ko "c4: crit='$crit'"
}

# c5: includes contract (subagents know what the feature reads/writes/invokes)
c5() {
  local d="$TMPROOT/c5"; fix "$d" c5 impl
  run "$d" >/dev/null
  jq -e '.contract.reads | type == "array"' "$TMPROOT/stdout" >/dev/null \
    && ok "c5: contract surfaced" \
    || ko "c5: contract missing in output"
}

echo "running tdd-context tests against $CTX"
c1; c2; c3; c4; c5
echo
echo "summary: $PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ] && exit 0 || exit 1
