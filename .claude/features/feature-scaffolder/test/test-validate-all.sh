#!/bin/bash
# End-to-end test of validate-all.sh — sweep validator over a features root.
#
# Strategy: stage a fixture features root + a stub validator (since we can't
# rely on feature-skeleton's validator being present on this branch). The
# validate-all.sh script's job is the sweep + aggregation, not the validation
# logic itself; the stub lets us test the sweep independently.
set -u

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
FEATURE_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
SWEEP="$FEATURE_DIR/scripts/validate-all.sh"
TMPROOT="$(mktemp -d)"
trap 'rm -rf "$TMPROOT"' EXIT INT TERM

PASS=0; FAIL=0
ok() { echo "  ok   $*"; PASS=$((PASS+1)); }
ko() { echo "  FAIL $*"; FAIL=$((FAIL+1)); }

# Stub validator: passes if marker file ".pass" exists in the feature dir,
# fails otherwise. validate-all.sh accepts a --validator override.
STUB="$TMPROOT/stub-validator.sh"
cat > "$STUB" <<'SH'
#!/bin/bash
[ -f "$1/.pass" ] && { echo "PASS: $1"; exit 0; } || { echo "FAIL: $1" >&2; exit 1; }
SH
chmod +x "$STUB"

mkfeat() {
  local d="$1" pass="$2"
  mkdir -p "$d"
  echo "{\"name\":\"$(basename "$d")\"}" > "$d/feature.json"
  [ "$pass" = "yes" ] && touch "$d/.pass"
}

run() { "$SWEEP" --validator "$STUB" "$@" 2>"$TMPROOT/err" >"$TMPROOT/out"; echo $?; }

# v1: empty root -> ok (no features to sweep)
mkdir -p "$TMPROOT/r1"
rc=$(run "$TMPROOT/r1")
[ "$rc" = "0" ] && ok "v1: empty root -> ok (vacuous)" \
  || ko "v1: rc=$rc err=$(cat "$TMPROOT/err")"

# v2: all features pass -> ok
mkdir -p "$TMPROOT/r2"
mkfeat "$TMPROOT/r2/a" yes
mkfeat "$TMPROOT/r2/b" yes
rc=$(run "$TMPROOT/r2")
[ "$rc" = "0" ] && ok "v2: all features pass -> ok" \
  || ko "v2: rc=$rc err=$(cat "$TMPROOT/err")"

# v3: one feature fails -> overall fails, names the failing feature
mkdir -p "$TMPROOT/r3"
mkfeat "$TMPROOT/r3/good" yes
mkfeat "$TMPROOT/r3/bad" no
rc=$(run "$TMPROOT/r3")
[ "$rc" != "0" ] && (cat "$TMPROOT/out" "$TMPROOT/err" | grep -q "bad") \
  && ok "v3: one feature fails -> overall fails (names 'bad')" \
  || ko "v3: rc=$rc out=$(cat "$TMPROOT/out") err=$(cat "$TMPROOT/err")"

# v4: dir without feature.json is skipped (not all subdirs are features)
mkdir -p "$TMPROOT/r4"
mkfeat "$TMPROOT/r4/real-feat" yes
mkdir -p "$TMPROOT/r4/random-dir"
rc=$(run "$TMPROOT/r4")
[ "$rc" = "0" ] \
  && ok "v4: non-feature subdir (no feature.json) is skipped" \
  || ko "v4: rc=$rc err=$(cat "$TMPROOT/err")"

# v5: $FEATURES_ROOT env var honored when no positional arg given
mkdir -p "$TMPROOT/r5"
mkfeat "$TMPROOT/r5/x" yes
rc=$("$SWEEP" --validator "$STUB" 2>"$TMPROOT/err" >"$TMPROOT/out"; echo $?)  # no path arg
# Without env override and no arg, defaults to .claude/features which doesn't exist in tmp
# -> should still exit 0 (vacuous) OR error clearly. Either acceptable.
# Set FEATURES_ROOT and re-run; this should now sweep r5.
rc=$(env FEATURES_ROOT="$TMPROOT/r5" "$SWEEP" --validator "$STUB" 2>"$TMPROOT/err" >"$TMPROOT/out"; echo $?)
[ "$rc" = "0" ] && grep -q "x" "$TMPROOT/out" \
  && ok "v5: \$FEATURES_ROOT env honored" \
  || ko "v5: rc=$rc out=$(cat "$TMPROOT/out") err=$(cat "$TMPROOT/err")"

# v6: validate-feature.sh from feature-skeleton autodetected if --validator omitted.
# Scaffold real features via new-feature.sh so the real validator passes them.
SCAFFOLD="$FEATURE_DIR/scripts/new-feature.sh"
mkdir -p "$TMPROOT/r6"
"$SCAFFOLD" "$TMPROOT/r6" "feat-alpha" >/dev/null 2>&1
"$SCAFFOLD" "$TMPROOT/r6" "feat-beta"  >/dev/null 2>&1
rc=$("$SWEEP" "$TMPROOT/r6" 2>"$TMPROOT/err" >"$TMPROOT/out"; echo $?)
if [ "$rc" = "0" ]; then
  ok "v6: autodetected feature-skeleton validator passes freshly scaffolded features"
elif [ "$rc" = "2" ] && grep -qi "validate-feature\|validator" "$TMPROOT/err"; then
  ok "v6: missing validator reported clearly with rc=2"
else
  ko "v6: rc=$rc out=$(cat "$TMPROOT/out") err=$(cat "$TMPROOT/err")"
fi

echo
echo "summary: $PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ] && exit 0 || exit 1
