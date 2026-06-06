#!/usr/bin/env bash
# .claude/features/rabbit-issue/test/gh_shim.sh
# Mock `gh` CLI for tests. Records args to $GH_SHIM_LOG.
# Returns canned responses from $GH_SHIM_RESPONSE_<SUBCOMMAND>_<VERB> or default.
#
# Version: 1.3.0
# Owner: rabbit-workflow team
# Deprecation criterion: when rabbit-issue is retired

set -e
LOG="${GH_SHIM_LOG:-/tmp/gh_shim.log}"
echo "$@" >> "$LOG"

case "$1 $2" in
  "issue create")
    NUM="${GH_SHIM_ISSUE_NUMBER:-9001}"
    echo "https://github.com/test/repo/issues/$NUM"
    ;;
  "issue view")
    NUM="$3"
    # Comment reads go through the JSON API (`--json comments`), never the
    # deprecated `--comments` human view (issue #522). Detect the request
    # and return gh's `{"comments": [...]}` envelope.
    if [[ "$*" == *"--json comments"* ]]; then
      if [ -n "$GH_SHIM_COMMENTS_BODY" ]; then
        cat "$GH_SHIM_COMMENTS_BODY"
      else
        echo "{\"comments\":[{\"body\":\"first comment\"},{\"body\":\"second comment\"}]}"
      fi
    elif [ -n "$GH_SHIM_ISSUE_BODY" ]; then
      cat "$GH_SHIM_ISSUE_BODY"
    else
      echo "{\"number\":$NUM,\"title\":\"test\",\"state\":\"open\",\"labels\":[{\"name\":\"bug\"},{\"name\":\"feature:test\"},{\"name\":\"priority:high\"}],\"body\":\"...\"}"
    fi
    ;;
  "issue close"|"issue reopen")
    echo "OK"
    ;;
  "api "*)
    # `gh api <endpoint> ...`. Used by link_sub_issue: a GET on
    # repos/{slug}/issues/{child} resolves the child's database id, and a
    # POST on repos/{slug}/issues/{parent}/sub_issues establishes the link.
    if [[ "$*" == *"sub_issues"* ]]; then
      # POST .../sub_issues — the link call. Honour an injected failure
      # (already-linked / HTTP error) so idempotence can be exercised.
      if [ -n "$GH_SHIM_SUBISSUE_POST_EXIT" ] && [ "$GH_SHIM_SUBISSUE_POST_EXIT" != "0" ]; then
        echo "${GH_SHIM_SUBISSUE_POST_STDERR:-gh: sub-issue already exists}" >&2
        exit "$GH_SHIM_SUBISSUE_POST_EXIT"
      fi
      echo "{\"sub_issue_id\": ${GH_SHIM_CHILD_ID:-424242}}"
    else
      # GET repos/{slug}/issues/{child} — resolve .id (the database id, which
      # is DELIBERATELY different from the issue number to catch the footgun).
      echo "{\"id\": ${GH_SHIM_CHILD_ID:-424242}, \"number\": ${GH_SHIM_CHILD_NUMBER:-9001}}"
    fi
    ;;
  "issue list")
    if [ -n "$GH_SHIM_LIST_RESPONSE" ]; then
      cat "$GH_SHIM_LIST_RESPONSE"
    else
      echo "[]"
    fi
    ;;
  "label create")
    exit "${GH_SHIM_LABEL_CREATE_EXIT:-0}"
    ;;
  "auth status")
    exit "${GH_SHIM_AUTH_EXIT:-0}"
    ;;
  *)
    echo "gh_shim: unknown subcommand: $@" >&2
    exit 99
    ;;
esac
