#!/bin/bash
# scope-guard.sh — PreToolUse hook that enforces breeder/vet scope discipline.
#
# Reads the standard PreToolUse JSON on stdin. For Write/Edit, extracts
# tool_input.file_path. For Bash, parses the command for write targets via
# simple heuristics (redirections, cp/mv/tee/sed -i, rm/touch). Each target
# is checked: if it lives inside a feature directory (any ancestor contains
# feature.json) AND no ancestor of the target contains the
# .rabbit-scope-active marker, the call is denied (exit 2). Targets outside
# any feature directory are allowed unconditionally.
#
# Exempt: writes to or removals of the .rabbit-scope-active marker file
# itself (chicken-and-egg — the dispatcher needs to create/remove it).
#
# Exit:
#   0 allow (no in-scope check needed, or in-scope check passed)
#   2 deny (out-of-scope write inside a feature directory; reason on stderr)
#
# This hook is the active enforcement of the unified work model. The
# dispatcher (typically the main session) protocol:
#   touch <SCOPE>/.rabbit-scope-active
#   Agent({ subagent_type: "rabbit-breeder", prompt: "SCOPE: <SCOPE>; ..." })
#   rm    <SCOPE>/.rabbit-scope-active

set -u

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
  # Resolve symlinks so a symlink into a feature dir is caught by walk_up_find.
  if [ -L "$abs" ]; then
    abs="$(readlink -f "$abs" 2>/dev/null || realpath "$abs" 2>/dev/null || echo "$abs")"
  fi
  local base; base="$(basename "$abs")"

  if [ "$base" = ".rabbit-scope-active" ]; then
    echo "ALLOW (marker file is exempt)"
    return 0
  fi

  if walk_up_find "$abs" ".rabbit-scope-active" >/dev/null; then
    echo "ALLOW (under active scope)"
    return 0
  fi

  local feat_dir
  if feat_dir="$(walk_up_find "$abs" "feature.json")"; then
    echo "DENY '$abs' is inside feature dir '$feat_dir' but no .rabbit-scope-active marker found in any ancestor (dispatcher must touch the marker before Agent call)"
    return 1
  fi

  echo "ALLOW (not under any feature directory)"
  return 0
}

# Extract write targets from a Bash command string. Conservative.
extract_bash_targets() {
  local cmd="$1"
  local segments; segments="$(echo "$cmd" | tr ';|&' '\n')"
  while IFS= read -r seg; do
    seg="${seg#"${seg%%[![:space:]]*}"}"
    [ -z "$seg" ] && continue

    # > path or >> path
    echo "$seg" | grep -oE '>>?[[:space:]]*[^[:space:]<>|&;]+' \
      | sed -E 's/^>>?[[:space:]]*//' || true

    # tee path / tee -a path
    echo "$seg" | grep -oE '\btee[[:space:]]+(-[a-z]+[[:space:]]+)?[^[:space:]<>|&;]+' \
      | sed -E 's/.*tee[[:space:]]+(-[a-z]+[[:space:]]+)?//' || true

    # sed -i ... path
    echo "$seg" | grep -oE "\bsed[[:space:]]+-i[[:space:]]+[^[:space:]<>|&;]+([[:space:]]+[^[:space:]<>|&;]+)*" \
      | awk '{print $NF}' || true

    # cp src dst, mv src dst — last word is target
    echo "$seg" | grep -oE '\bcp[[:space:]]+(-[a-zA-Z]+[[:space:]]+)*[^[:space:]<>|&;]+([[:space:]]+[^[:space:]<>|&;]+)+' \
      | awk '{print $NF}' || true
    echo "$seg" | grep -oE '\bmv[[:space:]]+(-[a-zA-Z]+[[:space:]]+)*[^[:space:]<>|&;]+([[:space:]]+[^[:space:]<>|&;]+)+' \
      | awk '{print $NF}' || true

    # rm path[s] — every non-flag arg is a target
    if echo "$seg" | grep -qE '^[[:space:]]*rm[[:space:]]'; then
      echo "$seg" | sed -E 's/^[[:space:]]*rm[[:space:]]+//' \
        | tr ' ' '\n' | grep -v '^-' | grep -v '^$' || true
    fi

    # touch path[s]
    if echo "$seg" | grep -qE '^[[:space:]]*touch[[:space:]]'; then
      echo "$seg" | sed -E 's/^[[:space:]]*touch[[:space:]]+//' \
        | tr ' ' '\n' | grep -v '^-' | grep -v '^$' || true
    fi

    # mkdir path[s]
    if echo "$seg" | grep -qE '^[[:space:]]*mkdir[[:space:]]'; then
      echo "$seg" | sed -E 's/^[[:space:]]*mkdir[[:space:]]+//' \
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
