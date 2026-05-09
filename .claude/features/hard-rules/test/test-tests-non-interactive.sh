#!/bin/bash
# Test the tests-non-interactive enforcement.
# Strategy: build fixture test scripts, some interactive, some not.
set -u

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
FEATURE_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
CHECK="$FEATURE_DIR/scripts/check-tests-non-interactive.sh"
TMPROOT="$(mktemp -d)"
trap 'rm -rf "$TMPROOT"' EXIT INT TERM

PASS=0; FAIL=0
ok() { echo "  ok   $*"; PASS=$((PASS+1)); }
ko() { echo "  FAIL $*"; FAIL=$((FAIL+1)); }

# Args: dir to scan
run() { "$CHECK" "$1" 2>&1; echo "RC:$?"; }

# t1: clean test file -> passes
mkdir -p "$TMPROOT/case1/test"
cat > "$TMPROOT/case1/test/run.sh" <<'EOF'
#!/bin/bash
echo hi
exit 0
EOF
out=$(run "$TMPROOT/case1"); rc=$(echo "$out" | tail -1 | sed 's/RC://')
[ "$rc" = "0" ] && ok "t1: clean test passes" || ko "t1: rc=$rc out=$out"

# t2: 'read' command -> fails
mkdir -p "$TMPROOT/case2/test"
cat > "$TMPROOT/case2/test/run.sh" <<'EOF'
#!/bin/bash
read -p "input: " name
echo "hi $name"
EOF
out=$(run "$TMPROOT/case2"); rc=$(echo "$out" | tail -1 | sed 's/RC://')
[ "$rc" != "0" ] && echo "$out" | grep -qiE 'read|interactive' \
  && ok "t2: 'read' detected" \
  || ko "t2: rc=$rc out=$out"

# t3: 'select' menu -> fails
mkdir -p "$TMPROOT/case3/test"
cat > "$TMPROOT/case3/test/run.sh" <<'EOF'
#!/bin/bash
select x in a b c; do echo "$x"; break; done
EOF
out=$(run "$TMPROOT/case3"); rc=$(echo "$out" | tail -1 | sed 's/RC://')
[ "$rc" != "0" ] && echo "$out" | grep -qiE 'select|interactive' \
  && ok "t3: 'select' detected" \
  || ko "t3: rc=$rc out=$out"

# t4: nested test files - one bad, one ok -> fails and names the bad
mkdir -p "$TMPROOT/case4/test"
cat > "$TMPROOT/case4/test/run.sh" <<'EOF'
#!/bin/bash
exit 0
EOF
cat > "$TMPROOT/case4/test/test-bad.sh" <<'EOF'
#!/bin/bash
read x
EOF
out=$(run "$TMPROOT/case4"); rc=$(echo "$out" | tail -1 | sed 's/RC://')
[ "$rc" != "0" ] && echo "$out" | grep -q "test-bad.sh" \
  && ok "t4: identifies the bad file" \
  || ko "t4: rc=$rc out=$out"

# t5: directory with no test/ subdir -> ok (vacuous; nothing to scan)
mkdir -p "$TMPROOT/case5"
out=$(run "$TMPROOT/case5"); rc=$(echo "$out" | tail -1 | sed 's/RC://')
[ "$rc" = "0" ] && ok "t5: no test/ dir -> vacuously ok" \
  || ko "t5: rc=$rc out=$out"

# t6: 'read' inside a comment is allowed (false-positive guard)
mkdir -p "$TMPROOT/case6/test"
cat > "$TMPROOT/case6/test/run.sh" <<'EOF'
#!/bin/bash
# we used to call 'read' here, removed it
exit 0
EOF
out=$(run "$TMPROOT/case6"); rc=$(echo "$out" | tail -1 | sed 's/RC://')
[ "$rc" = "0" ] && ok "t6: 'read' in comment is allowed" \
  || ko "t6: rc=$rc out=$out"

echo
echo "summary: $PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ] && exit 0 || exit 1
