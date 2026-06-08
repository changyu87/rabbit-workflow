#!/usr/bin/env python3
"""test-update-banner-channel-not-pin.py — BUG #1111 end-to-end guard.

Drives the FULL SessionStart update-banner pipeline for a local `--src`
install pin: the real deterministic producer `scripts/check-release-update.py`
emits the comparison payload, and the real renderer `lib.runtime` formats the
"update available: ... on channel <channel>" headline.

The bug: the producer reported the VERSION PIN (`local-<sha>`) as the
`channel` field, so the banner rendered the nonsensical
"on channel local-d3a86562". The channel must be a REAL channel label
(`local`) distinct from the version pin.

This is the E2E counterpart to the producer-level helper test
(test-check-release-update-helper.py t5-local) and the renderer-level
runtime test (test-runtime-check-release-update.py): it wires the two real
halves together and asserts the user-visible line.
"""

import json
import os
import subprocess
import sys
import tempfile

FEATURE_DIR = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
SCRIPT = os.path.join(FEATURE_DIR, "scripts", "check-release-update.py")
sys.path.insert(0, FEATURE_DIR)

from lib.runtime import check_release_update  # noqa: E402

FAIL = 0


def fail(msg):
    global FAIL
    print(f"FAIL: {msg}", file=sys.stderr)
    FAIL = 1


def ok(msg):
    print(f"PASS: {msg}")


def urlopen_shim(tag):
    body = json.dumps({"tag_name": tag, "name": tag,
                       "draft": False, "prerelease": False}).encode("utf-8")
    return f"""
import io
import urllib.request
class _Resp(io.BytesIO):
    def __enter__(self): return self
    def __exit__(self, *a): self.close()
    def getcode(self): return 200
    status = 200
def _fake(req, timeout=None):
    return _Resp({body!r})
urllib.request.urlopen = _fake
"""


def render_lines_for_pin(pin, tag):
    """Build a throwaway repo_root with a `.version` pin, run the REAL renderer
    `check_release_update` (which subprocesses the REAL producer script under a
    urlopen shim), and return the joined rendered text plus the parsed payload.
    """
    repo_root = tempfile.mkdtemp()
    # Lay out the contract feature path the renderer subprocesses.
    scripts_dir = os.path.join(repo_root, ".claude", "features", "contract", "scripts")
    os.makedirs(scripts_dir)
    # Symlink the real producer so we exercise the actual code under test.
    os.symlink(SCRIPT, os.path.join(scripts_dir, "check-release-update.py"))
    # Provide the rabbit-cage runtime-root resolver the producer lazy-imports;
    # absent, the producer's inline fallback handles it, so we can skip it.
    with open(os.path.join(repo_root, ".version"), "w") as f:
        f.write(pin)

    shim_dir = tempfile.mkdtemp()
    with open(os.path.join(shim_dir, "sitecustomize.py"), "w") as f:
        f.write(urlopen_shim(tag))

    # check_release_update copies os.environ into the subprocess, so inject the
    # shim + a tiny throttle window via the parent process environment.
    old_pp = os.environ.get("PYTHONPATH", "")
    os.environ["PYTHONPATH"] = shim_dir + (os.pathsep + old_pp if old_pp else "")
    os.environ["RABBIT_UPDATE_CHECK_INTERVAL_SECONDS"] = "0"
    try:
        result = check_release_update(repo_root=repo_root)
    finally:
        if old_pp:
            os.environ["PYTHONPATH"] = old_pp
        else:
            os.environ.pop("PYTHONPATH", None)
        os.environ.pop("RABBIT_UPDATE_CHECK_INTERVAL_SECONDS", None)

    lines = result if isinstance(result, list) else []
    joined = " ".join(x.get("text", "") for x in lines if isinstance(x, dict))
    return joined


# t1: local --src pin -> banner shows "on channel local", NOT the pin.
joined = render_lines_for_pin("local-d3a86562", "v1.0.7")
if "update available" not in joined:
    fail(f"t1: expected an update-available banner, got {joined!r}")
elif "on channel local-d3a86562" in joined:
    fail(f"t1: banner shows the version pin as channel (the #1111 bug): {joined!r}")
elif "on channel local" not in joined:
    fail(f"t1: banner missing the real 'on channel local' label: {joined!r}")
elif "(current: local-d3a86562)" not in joined:
    fail(f"t1: banner must still show the pin as current: {joined!r}")
else:
    ok("t1: local pin -> 'on channel local' (real label), pin shown only as current")

# t2: non-local channel pin still flows through unchanged.
joined = render_lines_for_pin("dev", "v1.0.7")
if "on channel dev" not in joined:
    fail(f"t2: configured channel 'dev' must flow through to the banner: {joined!r}")
else:
    ok("t2: configured channel 'dev' -> 'on channel dev'")


if FAIL:
    print("test-update-banner-channel-not-pin: FAIL", file=sys.stderr)
    sys.exit(1)
print("test-update-banner-channel-not-pin: all checks passed.")
