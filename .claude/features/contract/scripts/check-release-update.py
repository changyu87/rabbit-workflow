#!/usr/bin/env python3
"""check-release-update.py — deterministic release-channel update probe.

Reads <repo_root>/.version to resolve the upstream channel, throttles
the upstream fetch via <repo_root>/.rabbit/.runtime/last-update-check
(default window 8h, override via RABBIT_UPDATE_CHECK_INTERVAL_SECONDS),
fetches https://raw.githubusercontent.com/<RABBIT_REPO>/<channel>/.version
via stdlib urllib, and writes a single JSON line to stdout describing
the comparison outcome.

Behavior (per contract spec Inv 63):

  - missing/unreadable .version: silent exit 0, no stdout.
  - throttled (now - last_check < interval): silent exit 0, no stdout.
  - fetch failure (URLError, OSError, HTTP non-200, malformed body, any
    other exception): silent exit 0, no stdout. Throttle timestamp IS
    updated to avoid pounding the upstream on transient errors.
  - fetched == local: stdout '{"newer": false}', exit 0.
  - fetched != local: stdout '{"newer": true, "channel": <channel>,
    "current": <local>, "new": <upstream>, "self_update_available": <bool>}',
    exit 0.

self_update_available is true when <rabbit_root>/install.py exists AND
contains the literal string 'fetch_upstream' (the post-#262 self-update
marker). Otherwise false (the consumer suggests the curl|bash fresh-install
fallback).

repo_root is resolved from environment variable RABBIT_ROOT when set
(plugin mode); otherwise falls back to the directory four levels above
this script (.claude/features/contract/scripts -> repo root).

Stdlib only. No subprocess. NEVER blocks the user — every error path
exits 0.

Usage:
    python3 check-release-update.py

Exit codes:
    0 — always (silent on errors; JSON to stdout on success).

Version: 1.0.0
Owner: rabbit-workflow team (contract)
Deprecation criterion: when Claude Code exposes a native release-channel
    update notification mechanism that supersedes this helper.
"""

import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

DEFAULT_INTERVAL_SECONDS = 8 * 60 * 60  # 8 hours
DEFAULT_REPO = "changyu87/rabbit-workflow"
FETCH_TIMEOUT_SECONDS = 5


def resolve_repo_root():
    env_root = os.environ.get("RABBIT_ROOT")
    if env_root:
        return env_root
    # .claude/features/contract/scripts/check-release-update.py
    # parents[0]=scripts, [1]=contract, [2]=features, [3]=.claude, [4]=repo_root
    return str(Path(__file__).resolve().parents[4])


def read_version(version_path):
    try:
        with open(version_path) as f:
            return f.read().strip()
    except OSError:
        return None


def read_throttle(ts_path):
    try:
        with open(ts_path) as f:
            return int(f.read().strip())
    except (OSError, ValueError):
        return 0


def write_throttle(ts_path):
    try:
        os.makedirs(os.path.dirname(ts_path), exist_ok=True)
        with open(ts_path, "w") as f:
            f.write(str(int(time.time())))
    except OSError:
        # Best-effort; never block.
        pass


def resolve_interval():
    raw = os.environ.get("RABBIT_UPDATE_CHECK_INTERVAL_SECONDS")
    if raw is None:
        return DEFAULT_INTERVAL_SECONDS
    try:
        return int(raw)
    except ValueError:
        return DEFAULT_INTERVAL_SECONDS


def fetch_upstream_version(repo, channel):
    url = f"https://raw.githubusercontent.com/{repo}/{channel}/.version"
    try:
        with urllib.request.urlopen(url, timeout=FETCH_TIMEOUT_SECONDS) as resp:
            status = getattr(resp, "status", None) or resp.getcode()
            if status != 200:
                return None
            body = resp.read()
            if isinstance(body, bytes):
                body = body.decode("utf-8", errors="replace")
            return body.strip()
    except (urllib.error.URLError, urllib.error.HTTPError, OSError,
            UnicodeDecodeError, Exception):  # noqa: BLE001
        return None


def probe_self_update(rabbit_root):
    install = os.path.join(rabbit_root, "install.py")
    if not os.path.isfile(install):
        return False
    try:
        with open(install) as f:
            return "fetch_upstream" in f.read()
    except OSError:
        return False


def main():
    repo_root = resolve_repo_root()
    version_path = os.path.join(repo_root, ".version")
    ts_path = os.path.join(repo_root, ".rabbit", ".runtime", "last-update-check")

    local = read_version(version_path)
    if local is None or local == "":
        return 0

    interval = resolve_interval()
    last = read_throttle(ts_path)
    now = int(time.time())
    if last and now - last < interval:
        return 0

    repo = os.environ.get("RABBIT_REPO", DEFAULT_REPO)
    channel = local
    upstream = fetch_upstream_version(repo, channel)

    # Update throttle after the attempt regardless of outcome.
    write_throttle(ts_path)

    if upstream is None or upstream == "":
        return 0

    if upstream == local:
        sys.stdout.write(json.dumps({"newer": False}) + "\n")
        return 0

    self_update = probe_self_update(repo_root)
    sys.stdout.write(json.dumps({
        "newer": True,
        "channel": channel,
        "current": local,
        "new": upstream,
        "self_update_available": self_update,
    }) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
