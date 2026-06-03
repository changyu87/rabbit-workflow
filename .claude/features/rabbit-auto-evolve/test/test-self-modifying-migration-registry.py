#!/usr/bin/env python3
"""test-self-modifying-migration-registry.py — the loop-critical runtime-state
registry (acceptance criterion 3 of issue #450).

A declared, auditable data file maps loop-critical runtime state (known
markers, agent types, resolved paths, config keys) to a consumption type and
the resulting safe-execution pattern. The registry also declares the fallback
heuristic for state not explicitly listed:
  - marker files & resolved paths -> disk-each-tick (coexistence-window)
  - agent types & session config   -> memory-at-start (restart-safe)

This test asserts the registry exists, carries lifecycle metadata
(schema_version / owner / deprecation_criterion), declares the three patterns
consistently with consumption types, lists at least one entry of each
consumption class, and declares the fallback heuristic.
"""

import json
import sys
from pathlib import Path

FEATURE_DIR = Path(__file__).resolve().parents[1]
REGISTRY = (FEATURE_DIR / "scripts" / "schemas"
            / "self-modifying-migration-registry.json")

FAIL = 0


def fail(msg):
    global FAIL
    print(f"FAIL: {msg}", file=sys.stderr)
    FAIL = 1


def ok(msg):
    print(f"PASS: {msg}")


if not REGISTRY.is_file():
    fail(f"registry data file missing: {REGISTRY}")
    sys.exit(FAIL)

data = json.loads(REGISTRY.read_text())

# Lifecycle metadata (spec-rules §3: schemas record schema_version / owner /
# deprecation_criterion).
for key in ("schema_version", "owner", "deprecation_criterion"):
    if not data.get(key):
        fail(f"registry missing lifecycle key {key!r}")
    else:
        ok(f"registry declares {key}")

# Consumption -> pattern mapping is declared.
CONSUMPTION_TO_PATTERN = {
    "disk-each-tick": "coexistence-window",
    "self-contained": "last-tick-action",
    "memory-at-start": "restart-safe",
}
mapping = data.get("consumption_to_pattern")
if mapping != CONSUMPTION_TO_PATTERN:
    fail(f"registry consumption_to_pattern = {mapping!r}, "
         f"want {CONSUMPTION_TO_PATTERN!r}")
else:
    ok("registry declares the consumption->pattern mapping")

# Entries map a runtime-state token to a consumption type.
entries = data.get("entries")
if not isinstance(entries, list) or not entries:
    fail(f"registry entries missing/empty: {entries!r}")
else:
    ok("registry declares entries")
    seen_consumption = set()
    for e in entries:
        token = e.get("token")
        kind = e.get("kind")
        consumption = e.get("consumption")
        if not token:
            fail(f"entry missing token: {e!r}")
        if kind not in ("marker", "path", "agent-type", "config-key"):
            fail(f"entry {token!r} has unknown kind {kind!r}")
        if consumption not in CONSUMPTION_TO_PATTERN:
            fail(f"entry {token!r} has unknown consumption {consumption!r}")
        else:
            seen_consumption.add(consumption)
    # The known loop markers and agent types must both be represented so the
    # registry covers the two fallback-heuristic classes.
    if "disk-each-tick" not in seen_consumption:
        fail("registry lists no disk-each-tick (marker/path) entry")
    else:
        ok("registry covers a disk-each-tick entry (marker/path)")
    if "memory-at-start" not in seen_consumption:
        fail("registry lists no memory-at-start (agent-type/config) entry")
    else:
        ok("registry covers a memory-at-start entry (agent-type/config)")

# The restart-needed marker itself must be a known marker token (the loop reads
# it from disk each tick).
tokens = {e.get("token") for e in (entries or [])}
if ".rabbit-auto-evolve-restart-needed" not in tokens:
    fail("registry does not list .rabbit-auto-evolve-restart-needed")
else:
    ok("registry lists the restart-needed marker")

# Fallback heuristic is declared (markers/paths -> disk-each-tick; agent
# types/session config -> memory-at-start).
fb = data.get("fallback_heuristic")
if not isinstance(fb, dict):
    fail(f"registry fallback_heuristic missing/not an object: {fb!r}")
else:
    if fb.get("marker") != "disk-each-tick" or fb.get("path") != "disk-each-tick":
        fail(f"fallback heuristic: marker/path must map to disk-each-tick; "
             f"got {fb!r}")
    elif (fb.get("agent-type") != "memory-at-start"
          or fb.get("config-key") != "memory-at-start"):
        fail(f"fallback heuristic: agent-type/config-key must map to "
             f"memory-at-start; got {fb!r}")
    else:
        ok("registry declares the fallback heuristic")

sys.exit(FAIL)
