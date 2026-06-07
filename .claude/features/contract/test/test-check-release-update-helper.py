#!/usr/bin/env python3
"""test-check-release-update-helper.py — exercises Inv 53's
scripts/check-release-update.py helper.

Covers: throttle skip, newer detected, no-change, network failure silent,
missing .version silent, self-update probe both arms.

The helper performs the deterministic half of the release-channel
notification machinery: read local .version, throttle, urllib.request
fetch the latest release tag_name from the GitHub Releases API
(api.github.com/repos/<repo>/releases/latest), JSON output {newer, channel,
current, new, self_update_available}, silent on any error (#508).
"""

import json
import os
import subprocess
import sys
import tempfile
import time

FEATURE_DIR = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
SCRIPT = os.path.join(FEATURE_DIR, "scripts", "check-release-update.py")

FAIL = 0


def fail(msg):
    global FAIL
    print(f"FAIL: {msg}", file=sys.stderr)
    FAIL = 1


def ok(msg):
    print(f"PASS: {msg}")


def write_file(path, content):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write(content)


def run_helper(repo_root, env_extra=None, timeout=20):
    env = os.environ.copy()
    env["RABBIT_ROOT"] = repo_root
    # Force a long throttle interval by default so callers can opt into
    # the not-throttled path explicitly; pin to a tiny value to force fetch.
    if env_extra:
        env.update(env_extra)
    return subprocess.run(
        [sys.executable, SCRIPT],
        capture_output=True, text=True, timeout=timeout, env=env,
    )


def release_body(tag):
    """Return a bytes GitHub Releases-API /releases/latest JSON body whose
    tag_name is `tag` (plus a couple of sibling fields the real API ships so
    the parser must select tag_name specifically)."""
    return json.dumps({
        "tag_name": tag,
        "name": tag,
        "draft": False,
        "prerelease": False,
    }).encode("utf-8")


def make_urlopen_shim(payload=None, raise_exc=None):
    """Return Python source for a sitecustomize.py shim that monkey-patches
    urllib.request.urlopen at interpreter-start time. Returns either
    the supplied payload (bytes-ish) or raises the supplied exception.

    The helper now passes a urllib.request.Request (to set the Accept
    header), so the shim's _fake MUST accept the request object as its
    first positional arg regardless of type.
    """
    if raise_exc is not None:
        body = f"""
import urllib.request, urllib.error
def _fake(req, timeout=None):
    raise urllib.error.URLError({raise_exc!r})
urllib.request.urlopen = _fake
"""
    else:
        body = f"""
import io
import urllib.request
class _Resp(io.BytesIO):
    def __enter__(self): return self
    def __exit__(self, *a): self.close()
    def getcode(self): return 200
    status = 200
def _fake(req, timeout=None):
    return _Resp({payload!r})
urllib.request.urlopen = _fake
"""
    return body


def run_with_shim(repo_root, shim_src, env_extra=None, timeout=20):
    """Run the helper with a sitecustomize.py shim that monkey-patches urlopen."""
    with tempfile.TemporaryDirectory() as shim_dir:
        with open(os.path.join(shim_dir, "sitecustomize.py"), "w") as f:
            f.write(shim_src)
        env = os.environ.copy()
        env["RABBIT_ROOT"] = repo_root
        # Prepend so sitecustomize.py is discovered.
        existing = env.get("PYTHONPATH", "")
        env["PYTHONPATH"] = shim_dir + (os.pathsep + existing if existing else "")
        if env_extra:
            env.update(env_extra)
        return subprocess.run(
            [sys.executable, SCRIPT],
            capture_output=True, text=True, timeout=timeout, env=env,
        )


# t0: helper exists and is executable / has docstring (Inv 13)
if not os.path.isfile(SCRIPT):
    fail(f"t0: helper missing: {SCRIPT}")
    sys.exit(1)
if not os.access(SCRIPT, os.X_OK):
    fail(f"t0: helper not executable: {SCRIPT}")
else:
    ok("t0: helper exists and is executable")

# t1: missing .version -> exit 0, empty stdout
with tempfile.TemporaryDirectory() as td:
    r = run_helper(td)
    if r.returncode != 0:
        fail(f"t1: expected exit 0 on missing .version, got {r.returncode}; stderr={r.stderr!r}")
    elif r.stdout.strip() != "":
        fail(f"t1: expected empty stdout on missing .version, got {r.stdout!r}")
    else:
        ok("t1: missing .version -> silent exit 0")

# t2: throttle skip — last-update-check recent -> exit 0, empty stdout
with tempfile.TemporaryDirectory() as td:
    write_file(os.path.join(td, ".version"), "dev")
    runtime_dir = os.path.join(td, ".rabbit", ".runtime")
    os.makedirs(runtime_dir)
    # Write a recent timestamp so throttle window is active.
    with open(os.path.join(runtime_dir, "last-update-check"), "w") as f:
        f.write(str(int(time.time())))
    r = run_helper(td, env_extra={"RABBIT_UPDATE_CHECK_INTERVAL_SECONDS": "3600"})
    if r.returncode != 0:
        fail(f"t2: expected exit 0 on throttle, got {r.returncode}; stderr={r.stderr!r}")
    elif r.stdout.strip() != "":
        fail(f"t2: expected empty stdout on throttle, got {r.stdout!r}")
    else:
        ok("t2: throttle skip -> silent exit 0")

# t3: network failure -> silent exit 0
with tempfile.TemporaryDirectory() as td:
    write_file(os.path.join(td, ".version"), "dev")
    # No throttle file so we proceed to fetch.
    shim = make_urlopen_shim(raise_exc="network-down")
    r = run_with_shim(td, shim)
    if r.returncode != 0:
        fail(f"t3: expected exit 0 on URLError, got {r.returncode}; stderr={r.stderr!r}")
    elif r.stdout.strip() != "":
        fail(f"t3: expected empty stdout on URLError, got {r.stdout!r}")
    else:
        ok("t3: network failure -> silent exit 0")
    # Throttle file MUST have been updated after the fetch attempt.
    tsp = os.path.join(td, ".rabbit", ".runtime", "last-update-check")
    if not os.path.isfile(tsp):
        fail("t3b: throttle timestamp not updated after fetch attempt")
    else:
        ok("t3b: throttle timestamp updated after fetch attempt")

# t4: no-change — latest-release tag_name == local -> {"newer": false}
with tempfile.TemporaryDirectory() as td:
    write_file(os.path.join(td, ".version"), "v1.0.7")
    shim = make_urlopen_shim(payload=release_body("v1.0.7"))
    r = run_with_shim(td, shim)
    if r.returncode != 0:
        fail(f"t4: expected exit 0, got {r.returncode}; stderr={r.stderr!r}")
    else:
        try:
            payload = json.loads(r.stdout.strip())
        except json.JSONDecodeError as e:
            fail(f"t4: stdout not JSON: {e}; stdout={r.stdout!r}")
            payload = None
        if payload is not None:
            if payload.get("newer") is False:
                ok("t4: tag_name == local -> {newer: false}")
            else:
                fail(f"t4: expected newer=false, got {payload!r}")

# t5: newer detected — latest-release tag_name > local -> JSON with newer=true
with tempfile.TemporaryDirectory() as td:
    write_file(os.path.join(td, ".version"), "v1.0.6")
    # install.py present and contains fetch_upstream -> self_update_available=true
    write_file(os.path.join(td, "install.py"), "# stub\ndef fetch_upstream():\n    pass\n")
    shim = make_urlopen_shim(payload=release_body("v1.0.7"))
    r = run_with_shim(td, shim)
    if r.returncode != 0:
        fail(f"t5: expected exit 0, got {r.returncode}; stderr={r.stderr!r}")
    else:
        try:
            payload = json.loads(r.stdout.strip())
        except json.JSONDecodeError as e:
            fail(f"t5: stdout not JSON: {e}; stdout={r.stdout!r}")
            payload = None
        if payload is not None:
            if (payload.get("newer") is True
                and payload.get("channel") == "v1.0.6"
                and payload.get("current") == "v1.0.6"
                and payload.get("new") == "v1.0.7"
                and payload.get("self_update_available") is True):
                ok("t5: newer tag_name -> JSON with all fields + self_update_available=true")
            else:
                fail(f"t5: payload mismatch: {payload!r}")

# t6: self-update probe FALSE arm — install.py absent OR no fetch_upstream
with tempfile.TemporaryDirectory() as td:
    write_file(os.path.join(td, ".version"), "v1.0.6")
    # NO install.py
    shim = make_urlopen_shim(payload=release_body("v1.0.7"))
    r = run_with_shim(td, shim)
    payload = None
    if r.returncode == 0:
        try:
            payload = json.loads(r.stdout.strip())
        except json.JSONDecodeError:
            pass
    if payload and payload.get("self_update_available") is False:
        ok("t6a: install.py absent -> self_update_available=false")
    else:
        fail(f"t6a: expected self_update_available=false, got {payload!r}")

with tempfile.TemporaryDirectory() as td:
    write_file(os.path.join(td, ".version"), "v1.0.6")
    write_file(os.path.join(td, "install.py"), "# stub without the magic word\n")
    shim = make_urlopen_shim(payload=release_body("v1.0.7"))
    r = run_with_shim(td, shim)
    payload = None
    if r.returncode == 0:
        try:
            payload = json.loads(r.stdout.strip())
        except json.JSONDecodeError:
            pass
    if payload and payload.get("self_update_available") is False:
        ok("t6b: install.py present but no fetch_upstream -> self_update_available=false")
    else:
        fail(f"t6b: expected self_update_available=false, got {payload!r}")

# t7: malformed Releases-API body (no tag_name) -> silent exit 0, empty stdout
with tempfile.TemporaryDirectory() as td:
    write_file(os.path.join(td, ".version"), "v1.0.6")
    shim = make_urlopen_shim(payload=b'{"message": "Not Found"}')
    r = run_with_shim(td, shim)
    if r.returncode != 0:
        fail(f"t7: expected exit 0 on missing tag_name, got {r.returncode}; stderr={r.stderr!r}")
    elif r.stdout.strip() != "":
        fail(f"t7: expected empty stdout on missing tag_name, got {r.stdout!r}")
    else:
        ok("t7: malformed body (no tag_name) -> silent exit 0")

# t8: non-JSON Releases-API body -> silent exit 0, empty stdout
with tempfile.TemporaryDirectory() as td:
    write_file(os.path.join(td, ".version"), "v1.0.6")
    shim = make_urlopen_shim(payload=b"not-json-at-all")
    r = run_with_shim(td, shim)
    if r.returncode != 0:
        fail(f"t8: expected exit 0 on non-JSON body, got {r.returncode}; stderr={r.stderr!r}")
    elif r.stdout.strip() != "":
        fail(f"t8: expected empty stdout on non-JSON body, got {r.stdout!r}")
    else:
        ok("t8: non-JSON body -> silent exit 0")


if FAIL:
    print("test-check-release-update-helper: FAIL", file=sys.stderr)
    sys.exit(1)
print("test-check-release-update-helper: all checks passed.")
