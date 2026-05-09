#!/usr/bin/env bash
set -u
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PASS=0; FAIL=0
ok() { echo "  ok   $*"; PASS=$((PASS+1)); }
ko() { echo "  FAIL $*"; FAIL=$((FAIL+1)); }

# t1: make-readonly.sh exists and is executable
t1() {
  [ -x "$REPO_ROOT/make-readonly.sh" ] \
    && ok "t1: make-readonly.sh exists and is executable" \
    || ko "t1: make-readonly.sh missing or not executable"
}

# t2: make-writable.sh exists and is executable
t2() {
  [ -x "$REPO_ROOT/make-writable.sh" ] \
    && ok "t2: make-writable.sh exists and is executable" \
    || ko "t2: make-writable.sh missing or not executable"
}

# t3: make-readonly.sh removes write bit from both archive/ and test/
t3() {
  local tmp; tmp="$(mktemp -d)"
  mkdir -p "$tmp/archive" "$tmp/test"
  echo "data" > "$tmp/archive/sample.txt"
  echo "data" > "$tmp/test/sample.sh"
  ARCHIVE_DIR="$tmp/archive" TEST_DIR="$tmp/test" bash "$REPO_ROOT/make-readonly.sh" >/dev/null
  if [ ! -w "$tmp/archive/sample.txt" ] && [ ! -w "$tmp/test/sample.sh" ]; then
    ok "t3: make-readonly.sh removes write bit from archive/ and test/"
  else
    ko "t3: write bit not removed (archive writable=$([ -w "$tmp/archive/sample.txt" ] && echo yes || echo no) test writable=$([ -w "$tmp/test/sample.sh" ] && echo yes || echo no))"
  fi
  chmod -R u+w "$tmp" && rm -rf "$tmp"
}

# t4: make-writable.sh restores write bit
t4() {
  local tmp; tmp="$(mktemp -d)"
  mkdir -p "$tmp/archive" "$tmp/test"
  echo "data" > "$tmp/archive/sample.txt"
  chmod a-w "$tmp/archive/sample.txt"
  ARCHIVE_DIR="$tmp/archive" TEST_DIR="$tmp/test" bash "$REPO_ROOT/make-writable.sh" >/dev/null
  if [ -w "$tmp/archive/sample.txt" ]; then
    ok "t4: make-writable.sh restores write bit"
  else
    ko "t4: archive/ still read-only after make-writable.sh"
  fi
  rm -rf "$tmp"
}

echo "running readonly-scripts tests"
t1; t2; t3; t4
echo
echo "summary: $PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ] && exit 0 || exit 1
