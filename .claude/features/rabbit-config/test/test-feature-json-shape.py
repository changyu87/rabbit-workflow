#!/usr/bin/env python3
"""test-feature-json-shape.py — Inv 1–4 (plus required-metadata preflight).

Validates rabbit-config feature.json:
  t1: required metadata fields (name, version, owner, status, deprecation_criterion)
  t2: name is 'rabbit-config', status is 'active'
  t3: Inv 1 — manifest contains exactly one publish_skill entry for skills/rabbit-config/SKILL.md
  t4: Inv 2 — runtime.Stop contains exactly one iterate_configurables_alerts entry with empty args
  t5: Inv 3 — runtime.SessionStart contains exactly one iterate_configurables_banner entry with empty args
  t6: Inv 4 — configuration is an empty array
"""

import json
import os
import sys

FEATURE_DIR = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
FEATURE_JSON = os.path.join(FEATURE_DIR, "feature.json")

FAIL = 0


def fail(n, msg):
    global FAIL
    print(f"FAIL t{n}: {msg}", file=sys.stderr)
    FAIL = 1


def ok(n, msg):
    print(f"ok t{n}: {msg}")


if not os.path.isfile(FEATURE_JSON):
    fail(0, f"feature.json not found at {FEATURE_JSON}")
    sys.exit(1)

with open(FEATURE_JSON) as f:
    try:
        data = json.load(f)
    except json.JSONDecodeError as e:
        fail(0, f"feature.json is not valid JSON: {e}")
        sys.exit(1)

# t1: required metadata fields
for field in ("name", "version", "owner", "status", "deprecation_criterion"):
    if not data.get(field):
        fail(1, f"missing or empty field: {field!r}")
    else:
        ok(1, f"{field!r} present")

# t2: name and status
if data.get("name") != "rabbit-config":
    fail(2, f"name must be 'rabbit-config', got {data.get('name')!r}")
else:
    ok(2, "name is 'rabbit-config'")

if data.get("status") != "active":
    fail(2, f"status must be 'active', got {data.get('status')!r}")
else:
    ok(2, "status is 'active'")

# t3: manifest — exactly one publish_skill entry
manifest = data.get("manifest")
if not isinstance(manifest, list) or len(manifest) != 1:
    fail(3, f"manifest must be a list of exactly 1 entry, got: {manifest!r}")
else:
    entry = manifest[0]
    if entry.get("api") != "publish_skill":
        fail(3, f"manifest[0].api must be 'publish_skill', got {entry.get('api')!r}")
    elif entry.get("args", {}).get("source") != "skills/rabbit-config/SKILL.md":
        fail(3, f"manifest[0].args.source must be 'skills/rabbit-config/SKILL.md', got {entry.get('args', {}).get('source')!r}")
    else:
        ok(3, "manifest has exactly one publish_skill entry for skills/rabbit-config/SKILL.md")

# t4: runtime.Stop — exactly one iterate_configurables_alerts entry
runtime = data.get("runtime", {})
stop_entries = runtime.get("Stop", [])
if not isinstance(stop_entries, list) or len(stop_entries) != 1:
    fail(4, f"runtime.Stop must have exactly 1 entry, got {len(stop_entries) if isinstance(stop_entries, list) else stop_entries!r}")
else:
    e = stop_entries[0]
    if e.get("api") != "iterate_configurables_alerts":
        fail(4, f"runtime.Stop[0].api must be 'iterate_configurables_alerts', got {e.get('api')!r}")
    elif e.get("args") != {}:
        fail(4, f"runtime.Stop[0].args must be {{}}, got {e.get('args')!r}")
    else:
        ok(4, "runtime.Stop has one iterate_configurables_alerts entry with empty args")

# t5: runtime.SessionStart — exactly one iterate_configurables_banner entry
session_entries = runtime.get("SessionStart", [])
if not isinstance(session_entries, list) or len(session_entries) != 1:
    fail(5, f"runtime.SessionStart must have exactly 1 entry, got {len(session_entries) if isinstance(session_entries, list) else session_entries!r}")
else:
    e = session_entries[0]
    if e.get("api") != "iterate_configurables_banner":
        fail(5, f"runtime.SessionStart[0].api must be 'iterate_configurables_banner', got {e.get('api')!r}")
    elif e.get("args") != {}:
        fail(5, f"runtime.SessionStart[0].args must be {{}}, got {e.get('args')!r}")
    else:
        ok(5, "runtime.SessionStart has one iterate_configurables_banner entry with empty args")

# t6: configuration is an empty array
configuration = data.get("configuration")
if configuration != []:
    fail(6, f"configuration must be [], got {configuration!r}")
else:
    ok(6, "configuration is an empty array")

if FAIL:
    print("test-feature-json-shape: FAIL", file=sys.stderr)
    sys.exit(1)
print("test-feature-json-shape: all checks passed.")
