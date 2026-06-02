#!/usr/bin/env python3
"""test-stop-timestamp-entry-present.py — pins Inv 32: rabbit-cage's
`feature.json` `runtime.Stop` array MUST include an entry
`{"api": "emit_stop_timestamp", "args": {}}` so the Stop dispatcher
surfaces the universal `[rabbit] HH:MM:SS` turn-end marker (defined
by contract Inv 67) on every session's Stop event.
"""

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
RABBIT_CAGE_FEATURE_JSON = REPO / ".claude/features/rabbit-cage/feature.json"


def test_stop_runtime_declares_emit_stop_timestamp_entry():
    data = json.loads(RABBIT_CAGE_FEATURE_JSON.read_text())
    entries = data["runtime"]["Stop"]
    matches = [e for e in entries if e.get("api") == "emit_stop_timestamp"]
    assert matches, (
        "runtime.Stop must include an entry with api='emit_stop_timestamp' "
        f"(per Inv 32); got apis={[e.get('api') for e in entries]}"
    )
    assert len(matches) == 1, (
        f"expected exactly one emit_stop_timestamp entry; got {len(matches)}"
    )
    entry = matches[0]
    assert entry.get("args", {}) == {}, (
        "emit_stop_timestamp entry must have args={} (no parameters); "
        f"got {entry.get('args')!r}"
    )
    print("PASS test_stop_runtime_declares_emit_stop_timestamp_entry")


def main() -> int:
    test_stop_runtime_declares_emit_stop_timestamp_entry()
    return 0


if __name__ == "__main__":
    sys.exit(main())
