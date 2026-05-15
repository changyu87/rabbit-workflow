#!/usr/bin/env bash
# test-workspace-map-invocation.sh — verify that file-backlog-item.sh delegates
# storage path resolution to workspace-map.sh (contract) rather than hardcoding
# the path by convention.
#
# Tests FAIL until file-backlog-item.sh is updated to invoke workspace-map.sh.

set -u

REPO_ROOT="$(git -C "$(dirname "${BASH_SOURCE[0]}")" rev-parse --show-toplevel 2>/dev/null)"
FEATURE_DIR="${REPO_ROOT}/.claude/features/rabbit-backlog"
SCRIPTS_DIR="${FEATURE_DIR}/scripts"
FILE_BACKLOG="${SCRIPTS_DIR}/file-backlog-item.sh"
CONTRACT_SCRIPTS="${REPO_ROOT}/.claude/features/contract/scripts"
WORKSPACE_MAP="${CONTRACT_SCRIPTS}/workspace-map.sh"

pass=0
fail=0

ok() {
    echo "  PASS  $1"
    pass=$((pass + 1))
}

fail_t() {
    echo "  FAIL  $1${2:+ -- $2}"
    fail=$((fail + 1))
}

echo "=== test-workspace-map-invocation.sh: workspace-map.sh delegation ==="
echo ""

# t_wm1: workspace-map.sh exists at the declared contract path
if [ -f "$WORKSPACE_MAP" ]; then
    ok "t_wm1: workspace-map.sh exists at contract path: $WORKSPACE_MAP"
else
    fail_t "t_wm1: workspace-map.sh exists at contract path: $WORKSPACE_MAP" \
           "file not found: $WORKSPACE_MAP"
fi

# t_wm2: workspace-map.sh is executable
if [ -x "$WORKSPACE_MAP" ]; then
    ok "t_wm2: workspace-map.sh is executable"
else
    fail_t "t_wm2: workspace-map.sh is executable" \
           "not executable (or does not exist): $WORKSPACE_MAP"
fi

# t_wm3: file-backlog-item.sh invokes workspace-map.sh when resolving storage path.
#
# Strategy: create an isolated git repo, inject a stub workspace-map.sh via PATH
# that records its invocation, run file-backlog-item.sh, then assert the stub
# was called.
#
# The stub workspace-map.sh writes a sentinel file on any invocation:
#   <stub-sentinel>
# It also outputs the expected path so file-backlog-item.sh can proceed.

ISO_REPO="$(mktemp -d)"
SENTINEL_FILE="$(mktemp)"
trap 'rm -rf "$ISO_REPO" "$SENTINEL_FILE"' EXIT

git -C "$ISO_REPO" init --quiet
git -C "$ISO_REPO" config user.email "test@rabbit"
git -C "$ISO_REPO" config user.name "rabbit-test"
git -C "$ISO_REPO" commit --allow-empty -m "init" --quiet
# Ensure 'main' branch for branch guard compatibility.
_B="$(git -C "$ISO_REPO" branch --show-current 2>/dev/null)"
[ "$_B" != "main" ] && git -C "$ISO_REPO" branch -m "$_B" main 2>/dev/null || true

# Install find-feature.sh so file-backlog-item.sh can validate the feature.
FIND_FEATURE_SRC="${CONTRACT_SCRIPTS}/find-feature.sh"
ISO_CONTRACT_SCRIPTS="$ISO_REPO/.claude/features/contract/scripts"
mkdir -p "$ISO_CONTRACT_SCRIPTS"
cp "$FIND_FEATURE_SRC" "$ISO_CONTRACT_SCRIPTS/find-feature.sh"
chmod +x "$ISO_CONTRACT_SCRIPTS/find-feature.sh"
cp "$(dirname "$FIND_FEATURE_SRC")/find-feature.py" "$ISO_CONTRACT_SCRIPTS/find-feature.py"

# Create feature.json for test-feature so find-feature.sh can discover it.
mkdir -p "$ISO_REPO/.claude/features/test-feature"
cat > "$ISO_REPO/.claude/features/test-feature/feature.json" <<'FEATEOF'
{"name":"test-feature","version":"1.0.0","owner":"test","tdd_state":"test-green","summary":"test"}
FEATEOF

# Stub dir injected into PATH ahead of real contract scripts.
STUB_DIR="$(mktemp -d)"
trap 'rm -rf "$ISO_REPO" "$SENTINEL_FILE" "$STUB_DIR"' EXIT

# Create stub workspace-map.sh
EXPECTED_OUTPUT="${ISO_REPO}/.claude/backlogs/test-feature"
cat > "$STUB_DIR/workspace-map.sh" <<STUBEOF
#!/usr/bin/env bash
# Stub: record invocation and output the expected backlog path.
touch "$SENTINEL_FILE"
echo "$EXPECTED_OUTPUT"
STUBEOF
chmod +x "$STUB_DIR/workspace-map.sh"

# Remove sentinel before test so [ -e ] correctly detects if stub was called
# (mktemp creates an empty file; touch also creates empty file; use -e not -s)
rm -f "$SENTINEL_FILE"

# Copy file-backlog-item.sh into ISO_REPO so dirname resolves there.
ISO_SCRIPTS_DIR="$ISO_REPO/scripts"
mkdir -p "$ISO_SCRIPTS_DIR"
cp "$FILE_BACKLOG" "$ISO_SCRIPTS_DIR/file-backlog-item.sh"
chmod +x "$ISO_SCRIPTS_DIR/file-backlog-item.sh"

# Inject stub into PATH. The script must resolve workspace-map.sh via PATH
# or via a configurable path variable.
if [ -x "$FILE_BACKLOG" ]; then
    # Run with stub in PATH before real contract scripts
    PATH="$STUB_DIR:$CONTRACT_SCRIPTS:$PATH" \
    RABBIT_ROOT="$ISO_REPO" \
        "$ISO_SCRIPTS_DIR/file-backlog-item.sh" \
        --related-feature test-feature \
        --title "Workspace map delegation test" \
        2>/dev/null || true

    if [ -e "$SENTINEL_FILE" ]; then
        ok "t_wm3: file-backlog-item.sh invokes workspace-map.sh for path resolution"
    else
        fail_t "t_wm3: file-backlog-item.sh invokes workspace-map.sh for path resolution" \
               "workspace-map.sh stub was NOT called — script hardcodes path by convention"
    fi
else
    fail_t "t_wm3: file-backlog-item.sh invokes workspace-map.sh for path resolution" \
           "file-backlog-item.sh not found or not executable"
fi

# t_wm4: file-backlog-item.sh uses the path returned by workspace-map.sh,
# not a hardcoded .claude/backlogs/<feature> path.
#
# Inject a stub workspace-map.sh that returns a DIFFERENT path, then verify
# the item is created there (not at the conventional path).
ISO_REPO2="$(mktemp -d)"
STUB_DIR2="$(mktemp -d)"
CUSTOM_DIR="${ISO_REPO2}/custom-backlog-store"
SENTINEL_FILE2="$(mktemp)"
trap 'rm -rf "$ISO_REPO" "$SENTINEL_FILE" "$STUB_DIR" "$ISO_REPO2" "$STUB_DIR2" "$SENTINEL_FILE2"' EXIT

git -C "$ISO_REPO2" init --quiet
git -C "$ISO_REPO2" config user.email "test@rabbit"
git -C "$ISO_REPO2" config user.name "rabbit-test"
git -C "$ISO_REPO2" commit --allow-empty -m "init" --quiet
# Ensure 'main' branch for branch guard compatibility.
_B2="$(git -C "$ISO_REPO2" branch --show-current 2>/dev/null)"
[ "$_B2" != "main" ] && git -C "$ISO_REPO2" branch -m "$_B2" main 2>/dev/null || true

# Install find-feature.sh and feature.json for ISO_REPO2
ISO_CONTRACT_SCRIPTS2="$ISO_REPO2/.claude/features/contract/scripts"
mkdir -p "$ISO_CONTRACT_SCRIPTS2"
cp "$FIND_FEATURE_SRC" "$ISO_CONTRACT_SCRIPTS2/find-feature.sh"
chmod +x "$ISO_CONTRACT_SCRIPTS2/find-feature.sh"
cp "$(dirname "$FIND_FEATURE_SRC")/find-feature.py" "$ISO_CONTRACT_SCRIPTS2/find-feature.py"
mkdir -p "$ISO_REPO2/.claude/features/test-feature"
cat > "$ISO_REPO2/.claude/features/test-feature/feature.json" <<'FEATEOF2'
{"name":"test-feature","version":"1.0.0","owner":"test","tdd_state":"test-green","summary":"test"}
FEATEOF2

cat > "$STUB_DIR2/workspace-map.sh" <<STUBEOF2
#!/usr/bin/env bash
touch "$SENTINEL_FILE2"
echo "$CUSTOM_DIR"
STUBEOF2
chmod +x "$STUB_DIR2/workspace-map.sh"

ISO_SCRIPTS_DIR2="$ISO_REPO2/scripts"
mkdir -p "$ISO_SCRIPTS_DIR2"
cp "$FILE_BACKLOG" "$ISO_SCRIPTS_DIR2/file-backlog-item.sh"
chmod +x "$ISO_SCRIPTS_DIR2/file-backlog-item.sh"

if [ -x "$FILE_BACKLOG" ]; then
    PATH="$STUB_DIR2:$CONTRACT_SCRIPTS:$PATH" \
    RABBIT_ROOT="$ISO_REPO2" \
        "$ISO_SCRIPTS_DIR2/file-backlog-item.sh" \
        --related-feature test-feature \
        --title "Custom path test" \
        2>/dev/null || true

    # Item must appear in CUSTOM_DIR, not in the conventional .claude/backlogs/ path
    CONVENTIONAL="${ISO_REPO2}/.claude/backlogs/test-feature"
    CUSTOM_ITEM=$(find "$CUSTOM_DIR" -name "item.json" 2>/dev/null | head -1)

    if [ -n "$CUSTOM_ITEM" ] && [ ! -d "$CONVENTIONAL" ]; then
        ok "t_wm4: item created at path returned by workspace-map.sh (not hardcoded conventional path)"
    elif [ -d "$CONVENTIONAL" ]; then
        fail_t "t_wm4: item created at path returned by workspace-map.sh (not hardcoded conventional path)" \
               "item was created at conventional path $CONVENTIONAL — path is hardcoded, not delegated"
    else
        fail_t "t_wm4: item created at path returned by workspace-map.sh (not hardcoded conventional path)" \
               "item not found at custom path $CUSTOM_DIR and conventional path $CONVENTIONAL does not exist either"
    fi
else
    fail_t "t_wm4: item created at path returned by workspace-map.sh (not hardcoded conventional path)" \
           "file-backlog-item.sh not found or not executable"
fi

echo ""
echo "Results: $pass passed, $fail failed"
if [ "$fail" -gt 0 ]; then
    exit 1
fi
exit 0
