#!/bin/bash
# test-relink.sh — verify relink.sh creates symlinks from surface declarations.

set -u

SCRIPTS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../scripts" && pwd)"
RELINK="$SCRIPTS_DIR/relink.sh"

FAIL=0
ok()  { echo "  ok   $*"; }
fail() { echo "  FAIL $*" >&2; FAIL=1; }

# ── setup: temp features dir with one feature ─────────────────────────────────
TMPDIR="$(mktemp -d)"
cleanup() { rm -rf "$TMPDIR"; }
trap cleanup EXIT

FEATURES="$TMPDIR/features"
REPO="$TMPDIR/repo"
mkdir -p "$FEATURES/myfeat/hooks"
mkdir -p "$REPO/.claude/hooks"

# Create a real file in the feature dir (the canonical source)
echo '#!/bin/bash' > "$FEATURES/myfeat/hooks/my-hook.sh"
chmod +x "$FEATURES/myfeat/hooks/my-hook.sh"

# Create a registry.json
cat > "$FEATURES/registry.json" <<'REOF'
{
  "schema_version": "1.0.0",
  "owner": "test",
  "features": {
    "myfeat": {
      "name": "myfeat",
      "version": "1.0.0",
      "path": "features/myfeat"
    }
  }
}
REOF

# Create feature.json with a surface hook entry
cat > "$FEATURES/myfeat/feature.json" <<'FJEOF'
{
  "name": "myfeat",
  "version": "1.0.0",
  "owner": "test",
  "tdd_state": "test-green",
  "summary": "test feature",
  "surface": {
    "hooks":    [".claude/hooks/my-hook.sh"],
    "commands": [],
    "agents":   [],
    "skills":   []
  }
}
FJEOF

# ── t1: relink exits 0 ────────────────────────────────────────────────────────
if bash "$RELINK" "$FEATURES" "$REPO" >/dev/null 2>&1; then
  ok "t1: relink exits 0"
else
  fail "t1: relink exited non-zero"
fi

# ── t2: symlink was created at surface path ───────────────────────────────────
LINK="$REPO/.claude/hooks/my-hook.sh"
if [ -L "$LINK" ]; then
  ok "t2: symlink exists at surface path"
else
  fail "t2: symlink missing at $LINK"
fi

# ── t3: symlink points to correct target ─────────────────────────────────────
EXPECTED="$FEATURES/myfeat/hooks/my-hook.sh"
ACTUAL="$(readlink "$LINK" 2>/dev/null)"
if [ "$ACTUAL" = "$EXPECTED" ]; then
  ok "t3: symlink target is correct"
else
  fail "t3: symlink target '$ACTUAL' != '$EXPECTED'"
fi

# ── t4: idempotent — second run exits 0 and skips (no error) ─────────────────
if bash "$RELINK" "$FEATURES" "$REPO" >/dev/null 2>&1; then
  ok "t4: second run (idempotent) exits 0"
else
  fail "t4: second run exited non-zero"
fi

# ── t5: existing regular file is skipped (not overwritten) ───────────────────
TMPDIR2="$(mktemp -d)"
FEATURES2="$TMPDIR2/features"
REPO2="$TMPDIR2/repo"
mkdir -p "$FEATURES2/feat2"
mkdir -p "$REPO2/.claude/hooks"

echo '#!/bin/bash' > "$FEATURES2/feat2/my-hook.sh"
chmod +x "$FEATURES2/feat2/my-hook.sh"

# Pre-existing regular file at surface path
echo "original content" > "$REPO2/.claude/hooks/my-hook.sh"

cat > "$FEATURES2/registry.json" <<'REOF2'
{"schema_version":"1.0.0","owner":"test","features":{"feat2":{"name":"feat2","version":"1.0.0","path":"features/feat2"}}}
REOF2
cat > "$FEATURES2/feat2/feature.json" <<'FJEOF2'
{"name":"feat2","version":"1.0.0","owner":"test","tdd_state":"test-green","summary":"t","surface":{"hooks":[".claude/hooks/my-hook.sh"],"commands":[],"agents":[],"skills":[]}}
FJEOF2

bash "$RELINK" "$FEATURES2" "$REPO2" >/dev/null 2>&1
if [ -f "$REPO2/.claude/hooks/my-hook.sh" ] && [ ! -L "$REPO2/.claude/hooks/my-hook.sh" ]; then
  ok "t5: regular file at surface path was not overwritten"
else
  fail "t5: regular file was overwritten or converted to symlink"
fi

rm -rf "$TMPDIR2"

# ── t6: surface.root[] creates repo-root symlinks via artifacts/ ──────────────
TMPDIR3="$(mktemp -d)"
FEATURES3="$TMPDIR3/features"
REPO3="$TMPDIR3/repo"
mkdir -p "$FEATURES3/rootfeat/artifacts"
mkdir -p "$REPO3"

echo '#!/bin/bash' > "$FEATURES3/rootfeat/artifacts/myinstall.sh"
chmod +x "$FEATURES3/rootfeat/artifacts/myinstall.sh"

cat > "$FEATURES3/registry.json" <<'REOF3'
{"schema_version":"1.0.0","owner":"test","features":{"rootfeat":{"name":"rootfeat","version":"1.0.0","path":"features/rootfeat"}}}
REOF3
cat > "$FEATURES3/rootfeat/feature.json" <<'FJEOF3'
{"name":"rootfeat","version":"1.0.0","owner":"test","tdd_state":"test-green","summary":"t","surface":{"hooks":[],"commands":[],"agents":[],"skills":[],"root":["myinstall.sh"]}}
FJEOF3

bash "$RELINK" "$FEATURES3" "$REPO3" >/dev/null 2>&1
ROOT_LINK="$REPO3/myinstall.sh"
if [ -L "$ROOT_LINK" ]; then
  ok "t6: root surface entry creates symlink at repo root"
else
  fail "t6: root symlink missing at $ROOT_LINK"
fi

rm -rf "$TMPDIR3"

# ── result ────────────────────────────────────────────────────────────────────
if [ $FAIL -ne 0 ]; then
  echo "test-relink: FAIL" >&2
  exit 1
fi
echo "test-relink: all tests passed."
