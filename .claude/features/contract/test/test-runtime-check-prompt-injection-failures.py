#!/usr/bin/env python3
"""test-runtime-check-prompt-injection-failures.py — exercises
check_prompt_injection_failures: reads the structured failure log written
by the PreToolUse prompt-injector hook. Empty/missing -> ok_result;
non-empty -> print_result summarizing distinct failing skill names AND
empties the log file (consume pattern).
"""

import json
import os
import sys
import tempfile

FEATURE_DIR = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, FEATURE_DIR)

from lib.runtime import check_prompt_injection_failures  # noqa: E402

FAIL = 0


def fail(msg):
    global FAIL
    print(f"FAIL: {msg}", file=sys.stderr)
    FAIL = 1


def ok(msg):
    print(f"PASS: {msg}")


LOG_REL = ".rabbit/prompts/.injection-failures.log"


# t1: missing log -> ok_result
with tempfile.TemporaryDirectory() as td:
    r = check_prompt_injection_failures(LOG_REL, repo_root=td)
    if r == {"type": "ok"}:
        ok("t1: missing log -> ok_result")
    else:
        fail(f"t1: expected ok_result, got {r!r}")


# t2: empty log file -> ok_result
with tempfile.TemporaryDirectory() as td:
    log_path = os.path.join(td, LOG_REL)
    os.makedirs(os.path.dirname(log_path))
    open(log_path, "w").close()
    r = check_prompt_injection_failures(LOG_REL, repo_root=td)
    if r == {"type": "ok"}:
        ok("t2: empty log -> ok_result")
    else:
        fail(f"t2: expected ok_result, got {r!r}")


# t3: 2 entries with distinct skill names -> print_result mentions both;
#     log file is emptied (consume).
with tempfile.TemporaryDirectory() as td:
    log_path = os.path.join(td, LOG_REL)
    os.makedirs(os.path.dirname(log_path))
    with open(log_path, "w") as f:
        f.write(json.dumps({"ts": "2026-05-26T10:00:00", "skill": "skill-alpha",
                            "callable_id": "skill-alpha", "error": "boom"}) + "\n")
        f.write(json.dumps({"ts": "2026-05-26T10:01:00", "skill": "skill-beta",
                            "callable_id": "skill-beta", "error": "kaboom"}) + "\n")
    r = check_prompt_injection_failures(LOG_REL, repo_root=td)
    if (r.get("type") == "print"
            and "skill-alpha" in r.get("text", "")
            and "skill-beta" in r.get("text", "")
            and r.get("color") == "red"):
        with open(log_path) as f:
            remaining = f.read()
        if remaining == "":
            ok("t3: 2 distinct skills -> print_result mentions both; log emptied")
        else:
            fail(f"t3: log not emptied after consume: {remaining!r}")
    else:
        fail(f"t3: unexpected result {r!r}")


# t4: 2 entries with same skill name -> skill name appears once (distinct)
with tempfile.TemporaryDirectory() as td:
    log_path = os.path.join(td, LOG_REL)
    os.makedirs(os.path.dirname(log_path))
    with open(log_path, "w") as f:
        f.write(json.dumps({"ts": "2026-05-26T10:00:00", "skill": "skill-alpha",
                            "callable_id": "skill-alpha", "error": "boom"}) + "\n")
        f.write(json.dumps({"ts": "2026-05-26T10:01:00", "skill": "skill-alpha",
                            "callable_id": "skill-alpha", "error": "again"}) + "\n")
    r = check_prompt_injection_failures(LOG_REL, repo_root=td)
    if r.get("type") == "print":
        # count occurrences of "skill-alpha"
        text = r.get("text", "")
        if text.count("skill-alpha") == 1:
            ok("t4: duplicate skill names collapsed to single mention")
        else:
            fail(f"t4: expected skill-alpha mentioned once, got text={text!r}")
    else:
        fail(f"t4: expected print_result, got {r!r}")


if FAIL:
    print("test-runtime-check-prompt-injection-failures: FAIL", file=sys.stderr)
    sys.exit(1)
print("test-runtime-check-prompt-injection-failures: all checks passed.")
