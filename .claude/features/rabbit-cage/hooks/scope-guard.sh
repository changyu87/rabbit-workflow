#!/bin/bash
# scope-guard.sh v2.0.0 — PreToolUse hook enforcing repo-wide default-deny.
#
# Any write inside the repo root is denied unless:
#   (a) the target basename is settings.json or settings.local.json, or
#   (b) a .rabbit-scope-active marker exists in some ancestor of the target.
#
# Writes outside the repo root are unrestricted.
# The .rabbit-scope-active marker file itself is always exempt.
#
# Version: 2.0.0
# Owner: rabbit-workflow team (scope-guard feature)
# Deprecation criterion: when Claude Code exposes per-feature write boundaries natively.

set -u

REPO_ROOT="$(git -C "$(dirname "${BASH_SOURCE[0]}")" rev-parse --show-toplevel 2>/dev/null || echo "")"

INPUT="$(cat)"
TOOL_NAME="$(echo "$INPUT" | jq -r '.tool_name // ""' 2>/dev/null)"

# Resolve a path to absolute, without requiring the path to exist.
abspath() {
  local p="$1"
  case "$p" in
    /*) echo "$p" ;;
    *)  echo "$PWD/$p" ;;
  esac
}

# Walk up from $1's parent, looking for a directory that contains $2 as a file.
# Echoes the path of the first such directory found, or empty if none.
walk_up_find() {
  local target="$1" want="$2"
  local dir
  dir="$(dirname "$target")"
  while [ "$dir" != "/" ] && [ -n "$dir" ] && [ "$dir" != "." ]; do
    if [ -e "$dir/$want" ]; then
      echo "$dir"
      return 0
    fi
    dir="$(dirname "$dir")"
  done
  return 1
}

# Decide for one target. Echo "ALLOW" or "DENY <reason>".
decide() {
  local target="$1"
  local abs; abs="$(abspath "$target")"
  # Resolve symlinks so a symlink into a protected area is caught.
  if [ -L "$abs" ]; then
    abs="$(readlink -f "$abs" 2>/dev/null || realpath "$abs" 2>/dev/null || echo "$abs")"
  fi
  local base; base="$(basename "$abs")"

  # 1. Outside the repo entirely -> always allow
  if [ -z "$REPO_ROOT" ] || [ "${abs#"$REPO_ROOT/"}" = "$abs" ]; then
    echo "ALLOW (outside repo root)"
    return 0
  fi

  # 2. Marker file itself is always exempt
  if [ "$base" = ".rabbit-scope-active" ]; then
    echo "ALLOW (marker file is exempt)"
    return 0
  fi

  # 3. Allowlisted filenames -> always allow
  if [ "$base" = "settings.json" ] || [ "$base" = "settings.local.json" ] || [ "$base" = ".gitignore" ]; then
    echo "ALLOW (allowlisted filename)"
    return 0
  fi

  # 3b. Centralized bug/backlog storage — always allow (metadata-only writes, no TDD)
  if [[ "$abs" == "$REPO_ROOT/.claude/bugs/"* ]] || [[ "$abs" == "$REPO_ROOT/.claude/backlogs/"* ]]; then
    echo "ALLOW (centralized bug/backlog storage)"
    return 0
  fi

  # 4. Active scope marker anywhere in ancestor chain -> check further
  if walk_up_find "$abs" ".rabbit-scope-active" >/dev/null; then
    # 4b. Scope marker exists — verify target is within the scoped feature directory
    #     Read feature name from marker -> look up path in registry -> restrict to subtree
    SCOPE_FEATURE="$(cat "$REPO_ROOT/.rabbit-scope-active" 2>/dev/null)"
    REGISTRY="$REPO_ROOT/.claude/features/registry.json"
    FEATURE_PATH=$(python3 -c "import json,sys; r=json.load(open('$REGISTRY')); print(r.get('features',{}).get('$SCOPE_FEATURE',{}).get('path',''))" 2>/dev/null)
    if [ -n "$FEATURE_PATH" ]; then
      FEATURE_ABS="$REPO_ROOT/$FEATURE_PATH"
      if [[ "$abs" != "$FEATURE_ABS"* ]]; then
        echo "DENY write to '$abs' denied: outside active scope '$SCOPE_FEATURE' (allowed: $FEATURE_ABS/). Use dispatch-feature-edit.sh for cross-feature work."
        return 1
      fi
      # 4c. Within scoped feature — deny if feature is in test-green state
      FEATURE_JSON="$FEATURE_ABS/feature.json"
      TDD_STATE=$(python3 -c "import json; print(json.load(open('$FEATURE_JSON')).get('tdd_state',''))" 2>/dev/null)
      if [ "$TDD_STATE" = "test-green" ]; then
        # 4b-override. Override marker — human-approved bypass of test-green deny
        OVERRIDE_FILE="$REPO_ROOT/.rabbit-scope-override"
        USED_FILE="$REPO_ROOT/.rabbit-scope-override-used"
        if [ -f "$OVERRIDE_FILE" ]; then
          override_mode="$(cat "$OVERRIDE_FILE" | tr -d '[:space:]')"
          if [ "$override_mode" = "session" ]; then
            echo "ALLOW (session override active)"
            return 0
          elif [ "$override_mode" = "one-time" ]; then
            rm -f "$OVERRIDE_FILE"
            touch "$USED_FILE"
            echo "ALLOW (one-time override consumed)"
            return 0
          fi
        fi
        echo "DENY write to '$abs' denied: feature '$SCOPE_FEATURE' is in test-green state. Invoke the rabbit-feature-touch skill to reset the TDD state before editing."
        return 1
      fi
    fi
    echo "ALLOW (under active scope)"
    return 0
  fi

  # 4b-override. Override marker — human-approved bypass for no-scope-marker case
  OVERRIDE_FILE="$REPO_ROOT/.rabbit-scope-override"
  USED_FILE="$REPO_ROOT/.rabbit-scope-override-used"
  if [ -f "$OVERRIDE_FILE" ]; then
    override_mode="$(cat "$OVERRIDE_FILE" | tr -d '[:space:]')"
    if [ "$override_mode" = "session" ]; then
      echo "ALLOW (session override active)"
      return 0
    elif [ "$override_mode" = "one-time" ]; then
      rm -f "$OVERRIDE_FILE"
      touch "$USED_FILE"
      echo "ALLOW (one-time override consumed)"
      return 0
    fi
  fi

  # 5. Default deny
  echo "DENY write to '$abs' denied: no active scope marker and file is not on the allowlist (settings.json, settings.local.json). Dispatcher must touch .rabbit-scope-active before calling Agent."
  return 1
}

# Extract write targets from a Bash command string. Conservative.
extract_bash_targets() {
  local cmd="$1"
  # Strip heredoc bodies from the full command before segment splitting
  # to avoid false positives from heredoc content containing > or command names.
  local cmd_stripped_heredocs
  local _py_strip; _py_strip="$(mktemp /tmp/scope-guard-strip.XXXXXX.py 2>/dev/null)"
  if [ -n "$_py_strip" ]; then
    # Write the python stripping script to a temp file to avoid shell-quoting conflicts
    cat > "$_py_strip" << 'STRIP_HEREDOCS_PY'
import re, sys
s = sys.stdin.read()
# Remove heredoc bodies: << [-] [optional-quote] DELIM [optional-quote] [rest-of-line] \n body \n DELIM [\n]
s = re.sub(r"<<[- ]*['\"]?([A-Za-z_]\w*)['\"]?[^\n]*\n(.*\n)*?\1\n?", ' ', s, flags=re.DOTALL)
print(s, end='')
STRIP_HEREDOCS_PY
    cmd_stripped_heredocs="$(printf '%s' "$cmd" | python3 "$_py_strip" 2>/dev/null)" \
      || cmd_stripped_heredocs="$cmd"
    rm -f "$_py_strip"
  else
    cmd_stripped_heredocs="$cmd"
  fi
  local segments; segments="$(echo "$cmd_stripped_heredocs" | tr ';|&' '\n')"
  while IFS= read -r seg; do
    seg="${seg#"${seg%%[![:space:]]*}"}"
    [ -z "$seg" ] && continue

    # Strip single/double quoted regions from segment before pattern matching
    # to avoid false positives when string data contains >, >>, tee, cp, mv, etc.
    local stripped
    stripped="$(echo "$seg" | python3 -c "
import re, sys
s = sys.stdin.read()
# Remove single-quoted regions
s = re.sub(r\"'[^']*'\", ' ', s)
# Remove double-quoted regions
s = re.sub(r'\"[^\"]*\"', ' ', s)
print(s, end='')
" 2>/dev/null)" || stripped="$seg"

    # > path or >> path
    echo "$stripped" | grep -oE '>>?[[:space:]]*[^[:space:]<>|&;]+' \
      | sed -E 's/^>>?[[:space:]]*//' || true

    # tee path / tee -a path
    echo "$stripped" | grep -oE '\btee[[:space:]]+(-[a-z]+[[:space:]]+)?[^[:space:]<>|&;]+' \
      | sed -E 's/.*tee[[:space:]]+(-[a-z]+[[:space:]]+)?//' || true

    # sed -i ... path
    echo "$stripped" | grep -oE "\bsed[[:space:]]+-i[[:space:]]+[^[:space:]<>|&;]+([[:space:]]+[^[:space:]<>|&;]+)*" \
      | awk '{print $NF}' || true

    # cp src dst, mv src dst — last word is target
    echo "$stripped" | grep -oE '\bcp[[:space:]]+(-[a-zA-Z]+[[:space:]]+)*[^[:space:]<>|&;]+([[:space:]]+[^[:space:]<>|&;]+)+' \
      | awk '{print $NF}' || true
    echo "$stripped" | grep -oE '\bmv[[:space:]]+(-[a-zA-Z]+[[:space:]]+)*[^[:space:]<>|&;]+([[:space:]]+[^[:space:]<>|&;]+)+' \
      | awk '{print $NF}' || true

    # rm path[s] — every non-flag arg is a target
    if echo "$stripped" | grep -qE '^[[:space:]]*rm[[:space:]]'; then
      echo "$stripped" | sed -E 's/^[[:space:]]*rm[[:space:]]+//' \
        | tr ' ' '\n' | grep -v '^-' | grep -v '^$' || true
    fi

    # touch path[s]
    if echo "$stripped" | grep -qE '^[[:space:]]*touch[[:space:]]'; then
      echo "$stripped" | sed -E 's/^[[:space:]]*touch[[:space:]]+//' \
        | tr ' ' '\n' | grep -v '^-' | grep -v '^$' || true
    fi

    # mkdir path[s]
    if echo "$stripped" | grep -qE '^[[:space:]]*mkdir[[:space:]]'; then
      echo "$stripped" | sed -E 's/^[[:space:]]*mkdir[[:space:]]+//' \
        | tr ' ' '\n' | grep -v '^-' | grep -v '^$' || true
    fi
  done <<< "$segments"
}

# Check one target. Echoes nothing on allow, prints "scope-guard: ..." on deny.
# Returns 0 on allow, 1 on deny. (We do NOT exit here; the caller exits so
# `exit 2` happens in the parent script, not a piped subshell.)
check_one_target() {
  local target="$1"
  local result
  result="$(decide "$target")"
  case "$result" in
    DENY*)
      echo "scope-guard: $result" >&2
      return 1
      ;;
  esac
  return 0
}

# Collect targets into a variable (no piping into a function — piping creates
# a subshell that swallows our exit code).
collect_and_check() {
  local targets="$1"
  if [ -z "$targets" ]; then
    return 0
  fi
  while IFS= read -r t; do
    [ -z "$t" ] && continue
    check_one_target "$t" || return 1
  done <<< "$targets"
  return 0
}

case "$TOOL_NAME" in
  Write|Edit)
    target="$(echo "$INPUT" | jq -r '.tool_input.file_path // ""' 2>/dev/null)"
    if [ -n "$target" ]; then
      collect_and_check "$target" || exit 2
    fi
    ;;
  Bash)
    cmd="$(echo "$INPUT" | jq -r '.tool_input.command // ""' 2>/dev/null)"
    if [ -n "$cmd" ]; then
      bash_targets="$(extract_bash_targets "$cmd")"
      collect_and_check "$bash_targets" || exit 2
    fi
    ;;
  *)
    ;;
esac

exit 0
