#!/bin/bash
# End-to-end test of new-feature.sh — the user-mode scaffolder.
set -u

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
FEATURE_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
SCAFFOLD="$FEATURE_DIR/scripts/new-feature.sh"
TMPROOT="$(mktemp -d)"
trap 'rm -rf "$TMPROOT"' EXIT INT TERM

PASS=0; FAIL=0
ok() { echo "  ok   $*"; PASS=$((PASS+1)); }
ko() { echo "  FAIL $*"; FAIL=$((FAIL+1)); }

run() { "$SCAFFOLD" "$@" 2>"$TMPROOT/err" >"$TMPROOT/out"; echo $?; }

# t1: scaffold a new feature; all required files appear
mkdir -p "$TMPROOT/projA/features"
rc=$(run "$TMPROOT/projA/features" "my-feature")
target="$TMPROOT/projA/features/my-feature"
ALL=1
for f in feature.json spec.md contract.md test/run.sh; do
  [ -e "$target/$f" ] || ALL=0
done
[ "$rc" = "0" ] && [ "$ALL" = "1" ] \
  && ok "t1: scaffold creates all required files" \
  || ko "t1: rc=$rc all=$ALL stderr=$(cat "$TMPROOT/err")"

# t2: scaffolded feature.json carries required fields with sensible defaults
target="$TMPROOT/projA/features/my-feature"
name=$(jq -r '.name' "$target/feature.json")
state=$(jq -r '.tdd_state' "$target/feature.json")
status=$(jq -r '.status' "$target/feature.json")
ver=$(jq -r '.version' "$target/feature.json")
owner=$(jq -r '.owner.primary' "$target/feature.json")
crit=$(jq -r '.deprecation.criterion' "$target/feature.json")
if [ "$name" = "my-feature" ] && [ "$state" = "spec" ] && [ "$status" = "experimental" ] \
   && [ "$ver" = "0.1.0" ] && [ -n "$owner" ] && [ -n "$crit" ]; then
  ok "t2: defaults: name=$name state=$state status=$status ver=$ver owner=$owner"
else
  ko "t2: name=$name state=$state status=$status ver=$ver owner=$owner crit_len=${#crit}"
fi

# t3: test/run.sh is executable AND exits non-zero (TDD red state by default)
[ -x "$target/test/run.sh" ] && ! bash "$target/test/run.sh" >/dev/null 2>&1 \
  && ok "t3: test/run.sh is executable and red (exits non-zero)" \
  || ko "t3: test/run.sh permission/exit issue"

# t4: scaffold to an existing dir is rejected
rc=$(run "$TMPROOT/projA/features" "my-feature")
[ "$rc" != "0" ] && grep -qi "exist" "$TMPROOT/err" \
  && ok "t4: refuses overwrite of existing feature dir" \
  || ko "t4: rc=$rc err=$(cat "$TMPROOT/err")"

# t5: invalid name (uppercase) rejected
rc=$(run "$TMPROOT/projA/features" "BadName")
[ "$rc" != "0" ] && grep -qi "name" "$TMPROOT/err" \
  && ok "t5: uppercase name rejected" \
  || ko "t5: rc=$rc err=$(cat "$TMPROOT/err")"

# t6: invalid name (starts with digit) rejected
rc=$(run "$TMPROOT/projA/features" "1bad")
[ "$rc" != "0" ] \
  && ok "t6: name starting with digit rejected" \
  || ko "t6: rc=$rc"

# t7: --owner flag overrides default
rc=$(run "$TMPROOT/projA/features" "with-owner" --owner "alice")
got=$(jq -r '.owner.primary' "$TMPROOT/projA/features/with-owner/feature.json" 2>/dev/null)
[ "$rc" = "0" ] && [ "$got" = "alice" ] \
  && ok "t7: --owner sets owner.primary" \
  || ko "t7: rc=$rc got=$got"

# t8: works at any path (proves portability — not tied to .claude/features)
mkdir -p "$TMPROOT/totally/different/place"
rc=$(run "$TMPROOT/totally/different/place" "anywhere-feature")
[ "$rc" = "0" ] && [ -f "$TMPROOT/totally/different/place/anywhere-feature/feature.json" ] \
  && ok "t8: scaffolds at arbitrary path (portable)" \
  || ko "t8: rc=$rc"

# t9: missing root dir creates intermediate dirs OR errors clearly
rm -rf "$TMPROOT/projB"
rc=$(run "$TMPROOT/projB/features" "auto-mkdir")
# Either: scaffolder creates the parent (rc=0), or refuses with clear msg (rc!=0).
# Both are acceptable; we accept 0 (mkdir -p) as the friendlier default.
if [ "$rc" = "0" ] && [ -f "$TMPROOT/projB/features/auto-mkdir/feature.json" ]; then
  ok "t9: missing parent root auto-created"
elif [ "$rc" != "0" ] && grep -qi "exist\|directory\|root" "$TMPROOT/err"; then
  ok "t9: missing parent root refused with clear error"
else
  ko "t9: rc=$rc err=$(cat "$TMPROOT/err")"
fi

# t10: scaffolded contract.md contains the three required headers (Reads/Writes/Invokes)
for header in "Reads" "Writes" "Invokes"; do
  grep -qE "^#+ *$header" "$target/contract.md" 2>/dev/null \
    || { ko "t10: contract.md missing '$header' header"; return; } 2>/dev/null
done
target="$TMPROOT/projA/features/my-feature"
HAS_ALL=1
for header in "Reads" "Writes" "Invokes"; do
  grep -qE "^#+ *$header" "$target/contract.md" || HAS_ALL=0
done
[ "$HAS_ALL" = "1" ] && ok "t10: contract.md has Reads/Writes/Invokes headers" \
  || ko "t10: contract.md missing one of the headers"

echo
echo "summary: $PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ] && exit 0 || exit 1
