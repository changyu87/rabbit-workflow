#!/bin/bash
# tdd-context.sh — emit machine-first JSON describing a feature's TDD state,
# intended for inclusion in subagent prompts so every spawned agent knows:
#   - which feature it is working on
#   - what TDD step it is in
#   - what the next allowed step is (and what triggers it)
#   - the deprecation criterion (so it doesn't accidentally extend EOL'd code)
#   - the contract (what it reads / writes / invokes)
#
# Usage:
#   tdd-context.sh <feature-dir>          # JSON output (default)
#   tdd-context.sh --text <feature-dir>   # human-readable summary
#
# Exit:
#   0 success
#   2 invocation error

set -u

mode="json"
if [ "${1:-}" = "--text" ]; then
  mode="text"; shift
fi

dir="${1:-}"
[ -z "$dir" ] && { echo "usage: tdd-context.sh [--text] <feature-dir>" >&2; exit 2; }
[ ! -f "$dir/feature.json" ] && { echo "ERROR: no feature.json in $dir" >&2; exit 2; }

state=$(jq -r '.tdd_state // ""' "$dir/feature.json")
name=$(jq -r '.name // ""' "$dir/feature.json")
crit=$(jq -r '.deprecation.criterion // ""' "$dir/feature.json")

# Forward-only allowed next state per current state.
allowed_next() {
  case "$1" in
    spec)       echo '["test-red"]' ;;
    test-red)   echo '["impl"]' ;;
    impl)       echo '["test-green"]' ;;
    test-green) echo '["review"]' ;;
    review)     echo '["merged"]' ;;
    merged)     echo '["deprecated"]' ;;
    deprecated) echo '[]' ;;
    *)          echo '[]' ;;
  esac
}

# Per-state guidance for the agent: what must be true to advance.
guidance_for() {
  case "$1" in
    spec)
      echo "Author end-to-end tests under test/. They MUST be runnable unattended (no human input). They MUST fail (red) when run, since no implementation exists yet. Then transition to test-red." ;;
    test-red)
      echo "Tests exist and fail. Begin implementation under scripts/ (or wherever the spec dictates). Do NOT modify the tests to make them pass. Then transition to impl when implementation work has started." ;;
    impl)
      echo "Implementation in progress. Run test/run.sh frequently. When all tests pass, transition to test-green." ;;
    test-green)
      echo "All tests pass. Open a pull request now (branch should already exist per branch-per-feature). Then transition to review." ;;
    review)
      echo "PR is open. Address review feedback. If feedback requires more work, use --force to step back to impl. When merged, transition to merged." ;;
    merged)
      echo "Feature is on main. Only mutation allowed now is documentation or deprecation. Transition to deprecated only when superseded per the deprecation criterion." ;;
    deprecated)
      echo "TERMINAL. Do not extend or modify behavior. Direct callers to the successor (if any). This feature should be removed when the deprecation criterion is fully met." ;;
    *)
      echo "Unknown state. Repair feature.json before proceeding." ;;
  esac
}

# Build JSON output by combining feature.json contents with derived fields.
build_json() {
  local next; next=$(allowed_next "$state")
  local g;    g=$(guidance_for "$state")
  jq -n \
    --arg name "$name" \
    --arg state "$state" \
    --argjson next "$next" \
    --arg guide "$g" \
    --arg crit "$crit" \
    --slurpfile feat "$dir/feature.json" \
    '{
      feature_name: $name,
      current_state: $state,
      allowed_next_states: $next,
      guidance: $guide,
      deprecation_criterion: $crit,
      contract: $feat[0].contract,
      version: $feat[0].version,
      owner: $feat[0].owner,
      status: $feat[0].status
    }'
}

if [ "$mode" = "json" ]; then
  build_json
  exit 0
fi

# Text mode
cat <<EOF
Feature: $name
Current state: $state
Next allowed state(s): $(allowed_next "$state" | jq -r '. | join(", ")')
Guidance:
  $(guidance_for "$state")
Deprecation criterion:
  $crit
EOF
exit 0
