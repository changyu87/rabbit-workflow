#!/usr/bin/env python3
# tdd-drift-check.py — verify a feature's claimed tdd_state matches reality.
#
# Rules:
#   spec        : not test-checked (no claim about test outcome)
#   spec-update : not test-checked (no claim about test outcome)
#   test-red    : test/run.sh MUST exit non-zero
#   impl        : transitional; no test-outcome check
#   test-green  : test/run.sh MUST exit 0
#   deprecated  : not test-checked (terminal)
#
# Usage: tdd-drift-check.py <feature-dir>
# Exit:  0 ok; 1 drift detected; 2 invocation error.

import json
import os
import subprocess
import sys


def run_tests_get_rc(runner):
    if not (os.path.isfile(runner) and os.access(runner, os.X_OK)):
        sys.stderr.write(f"ERROR: {runner} missing or not executable\n")
        return None, 2
    try:
        res = subprocess.run(
            ["bash", runner],
            capture_output=True, check=False,
        )
        return res.returncode, 0
    except Exception as e:
        sys.stderr.write(f"ERROR: failed to run {runner}: {e}\n")
        return None, 2


def main(argv):
    if not argv:
        sys.stderr.write("usage: tdd-drift-check.py <feature-dir>\n")
        return 2
    d = argv[0]
    if not os.path.isdir(d):
        sys.stderr.write(f"ERROR: not a directory: {d}\n")
        return 2
    feat_path = os.path.join(d, "feature.json")
    if not os.path.isfile(feat_path):
        sys.stderr.write(f"ERROR: missing feature.json in {d}\n")
        return 2

    try:
        with open(feat_path, "r") as f:
            data = json.load(f)
    except Exception as e:
        sys.stderr.write(f"ERROR: failed to parse {feat_path}: {e}\n")
        return 2

    state = data.get("tdd_state", "") or ""
    runner = os.path.join(d, "test", "run.sh")

    if state in ("spec", "spec-update", "impl", "deprecated"):
        print(f"OK ({state}, no test-outcome check)")
        return 0

    if state == "test-red":
        rc, err = run_tests_get_rc(runner)
        if err != 0:
            return err
        if rc == 0:
            sys.stderr.write(
                "DRIFT: claim 'test-red' but tests passed (rc=0). "
                "Either advance to test-green or restore failing tests.\n"
            )
            return 1
        print(f"OK (test-red, tests failing as expected, rc={rc})")
        return 0

    if state == "test-green":
        rc, err = run_tests_get_rc(runner)
        if err != 0:
            return err
        if rc != 0:
            sys.stderr.write(
                f"DRIFT: claim '{state}' but tests failed (rc={rc}). "
                "Either fix tests or transition back.\n"
            )
            return 1
        print(f"OK ({state}, tests passing)")
        return 0

    if state == "":
        sys.stderr.write("ERROR: feature.json has no tdd_state\n")
        return 2

    sys.stderr.write(f"ERROR: unknown tdd_state '{state}'\n")
    return 2


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except BrokenPipeError:
        sys.exit(0)
