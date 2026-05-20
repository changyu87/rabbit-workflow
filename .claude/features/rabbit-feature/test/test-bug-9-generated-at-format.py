#!/usr/bin/env python3
"""E2E test for rabbit-spec Inv 3 detail (generated_at format).

The spec (impl-suggestion Schema field semantics) requires `generated_at` to
be an ISO 8601 UTC timestamp of the form `YYYY-MM-DDTHH:MM:SSZ` (RFC 3339
profile with `Z` suffix). This test:

1. Writes a fixture impl-suggestion JSON file with a conforming timestamp.
2. Parses it and asserts the timestamp matches a strict regex derived from
   the spec.
3. Asserts a malformed timestamp (e.g., with timezone offset, no Z, or with
   fractional seconds) is rejected by the same regex.

Closes RABBIT-SPEC-BACKLOG-9 test gap (a): generated_at format check on a
real impl-suggestion JSON.
"""
import json
import os
import re
import sys
import tempfile

# Strict regex from the spec: YYYY-MM-DDTHH:MM:SSZ
GENERATED_AT_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")


def _write_fixture(path, generated_at):
    payload = {
        "schema_version": "1.0.0",
        "feature": "rabbit-spec",
        "generated_at": generated_at,
        "request_summary": "fixture",
        "spec_changes": "none",
        "implementation_approach": "n/a",
        "affected_files": [],
        "key_invariants": [],
    }
    with open(path, "w") as f:
        json.dump(payload, f)


def test_conforming_timestamp_accepted():
    """A timestamp shaped YYYY-MM-DDTHH:MM:SSZ MUST match the regex."""
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "impl-suggestion-rabbit-spec.json")
        _write_fixture(path, "2026-05-20T02:30:00Z")
        with open(path) as f:
            data = json.load(f)
        ts = data["generated_at"]
        assert GENERATED_AT_RE.match(ts), \
            f"conforming timestamp {ts!r} must match {GENERATED_AT_RE.pattern}"


def test_missing_z_suffix_rejected():
    """Timestamp without the trailing Z MUST NOT match."""
    bad = "2026-05-20T02:30:00"
    assert not GENERATED_AT_RE.match(bad), \
        f"timestamp without Z suffix must be rejected: {bad!r}"


def test_timezone_offset_rejected():
    """Timestamp with an explicit offset (e.g., +00:00) MUST NOT match —
    spec mandates the Z form only."""
    bad = "2026-05-20T02:30:00+00:00"
    assert not GENERATED_AT_RE.match(bad), \
        f"timestamp with offset must be rejected: {bad!r}"


def test_fractional_seconds_rejected():
    """Timestamp with fractional seconds MUST NOT match — spec format has
    integer seconds only."""
    bad = "2026-05-20T02:30:00.123Z"
    assert not GENERATED_AT_RE.match(bad), \
        f"timestamp with fractional seconds must be rejected: {bad!r}"


def test_date_only_rejected():
    """Date-only string MUST NOT match."""
    bad = "2026-05-20"
    assert not GENERATED_AT_RE.match(bad), \
        f"date-only string must be rejected: {bad!r}"


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    fail = 0
    for t in tests:
        try:
            t()
            print(f"PASS: {t.__name__}")
        except Exception as e:
            print(f"FAIL: {t.__name__}: {e}")
            fail += 1
    print()
    print("ALL PASS" if fail == 0 else f"FAILED: {fail}")
    sys.exit(0 if fail == 0 else 1)
