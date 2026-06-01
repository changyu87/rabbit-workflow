#!/usr/bin/env python3
"""test-session-start-release-update-wired.py — Inv 16 (amended).

Asserts rabbit-cage's feature.json runtime.SessionStart declares
check_release_update as the THIRD entry (index 2), with args={}, after
welcome_with_policy (index 0) and write_mode_marker (index 1).

This is a structural (wiring) assertion. The API implementation lives in
contract.lib.runtime per contract Inv 47/63; execution-level coverage is
exercised by the dispatcher chain in test-write-mode-marker-wired.py and
the contract feature's own runtime tests.
"""

import json
import sys
from pathlib import Path

RABBIT_CAGE_FEATURE_JSON = (
    Path(__file__).resolve().parents[1] / "feature.json"
)


def test_feature_json_declares_check_release_update_as_third_entry():
    data = json.loads(RABBIT_CAGE_FEATURE_JSON.read_text())
    entries = data["runtime"]["SessionStart"]
    assert len(entries) >= 3, (
        f"SessionStart must declare >=3 entries; got {len(entries)}: "
        f"{[e['api'] for e in entries]}"
    )
    apis = [e["api"] for e in entries]
    assert apis[0] == "welcome_with_policy", (
        f"index 0 must be welcome_with_policy; got {apis[0]!r}"
    )
    assert apis[1] == "write_mode_marker", (
        f"index 1 must be write_mode_marker; got {apis[1]!r}"
    )
    assert apis[2] == "check_release_update", (
        f"index 2 must be check_release_update; got {apis[2]!r}"
    )
    cru = entries[2]
    assert cru.get("args", {}) == {}, (
        f"check_release_update entry must have args={{}}, got {cru.get('args')}"
    )
    print("PASS test_feature_json_declares_check_release_update_as_third_entry")


def main() -> int:
    test_feature_json_declares_check_release_update_as_third_entry()
    return 0


if __name__ == "__main__":
    sys.exit(main())
