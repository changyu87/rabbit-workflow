#!/usr/bin/env python3
"""test-runtime-cleanup-old-prompts.py — exercises cleanup_old_prompts:
walks <repo_root>/.rabbit/prompts/ and deletes .txt files older than
max_age_days based on the embedded YYYYMMDD-HHMMSS-ms timestamp in the
filename. Idempotent; returns ok_result on success or missing dir.
"""

import os
import sys
import tempfile
import time

FEATURE_DIR = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, FEATURE_DIR)

from lib.runtime import cleanup_old_prompts  # noqa: E402

FAIL = 0


def fail(msg):
    global FAIL
    print(f"FAIL: {msg}", file=sys.stderr)
    FAIL = 1


def ok(msg):
    print(f"PASS: {msg}")


def fresh_filename():
    now = time.localtime()
    return (f"x-5678-{time.strftime('%Y%m%d-%H%M%S', now)}-000.txt")


# t1: missing .rabbit/prompts/ -> ok_result, no error
with tempfile.TemporaryDirectory() as td:
    r = cleanup_old_prompts(max_age_days=7, repo_root=td)
    if r == {"type": "ok"}:
        ok("t1: missing .rabbit/prompts/ -> ok_result")
    else:
        fail(f"t1: expected ok_result, got {r!r}")


# t2: old file deleted, fresh file preserved
with tempfile.TemporaryDirectory() as td:
    prompts_dir = os.path.join(td, ".rabbit", "prompts")
    os.makedirs(prompts_dir)
    old_name = "x-1234-20200101-000000-000.txt"
    fresh_name = fresh_filename()
    old_path = os.path.join(prompts_dir, old_name)
    fresh_path = os.path.join(prompts_dir, fresh_name)
    with open(old_path, "w") as f:
        f.write("old content")
    with open(fresh_path, "w") as f:
        f.write("fresh content")
    r = cleanup_old_prompts(max_age_days=7, repo_root=td)
    if r != {"type": "ok"}:
        fail(f"t2: expected ok_result, got {r!r}")
    elif os.path.exists(old_path):
        fail(f"t2: old file should have been deleted: {old_path}")
    elif not os.path.exists(fresh_path):
        fail(f"t2: fresh file should be preserved: {fresh_path}")
    else:
        ok("t2: old file deleted, fresh file preserved -> ok_result")


# t3: idempotent — re-running on already-cleaned dir is still ok_result
with tempfile.TemporaryDirectory() as td:
    prompts_dir = os.path.join(td, ".rabbit", "prompts")
    os.makedirs(prompts_dir)
    fresh_name = fresh_filename()
    fresh_path = os.path.join(prompts_dir, fresh_name)
    with open(fresh_path, "w") as f:
        f.write("fresh content")
    r1 = cleanup_old_prompts(max_age_days=7, repo_root=td)
    r2 = cleanup_old_prompts(max_age_days=7, repo_root=td)
    if r1 == {"type": "ok"} and r2 == {"type": "ok"} and os.path.exists(fresh_path):
        ok("t3: idempotent — both calls return ok_result, fresh file remains")
    else:
        fail(f"t3: idempotency fail; r1={r1!r}, r2={r2!r}, exists={os.path.exists(fresh_path)}")


# t4: files whose name doesn't match the timestamp pattern are skipped (not deleted)
with tempfile.TemporaryDirectory() as td:
    prompts_dir = os.path.join(td, ".rabbit", "prompts")
    os.makedirs(prompts_dir)
    weird_path = os.path.join(prompts_dir, "no-timestamp.txt")
    with open(weird_path, "w") as f:
        f.write("oddball")
    r = cleanup_old_prompts(max_age_days=7, repo_root=td)
    if r == {"type": "ok"} and os.path.exists(weird_path):
        ok("t4: non-matching filename is skipped (not deleted)")
    else:
        fail(f"t4: weird file handling: r={r!r}, exists={os.path.exists(weird_path)}")


# t5: hidden non-.txt files (like .injection-failures.log) are not touched
with tempfile.TemporaryDirectory() as td:
    prompts_dir = os.path.join(td, ".rabbit", "prompts")
    os.makedirs(prompts_dir)
    log_path = os.path.join(prompts_dir, ".injection-failures.log")
    with open(log_path, "w") as f:
        f.write("ignored")
    r = cleanup_old_prompts(max_age_days=7, repo_root=td)
    if r == {"type": "ok"} and os.path.exists(log_path):
        ok("t5: non-.txt files are not deleted")
    else:
        fail(f"t5: log file should be preserved: r={r!r}, exists={os.path.exists(log_path)}")


if FAIL:
    print("test-runtime-cleanup-old-prompts: FAIL", file=sys.stderr)
    sys.exit(1)
print("test-runtime-cleanup-old-prompts: all checks passed.")
