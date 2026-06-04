#!/usr/bin/env python3
"""test-runtime-emit-configurable-alert-declarable.py — E2E for #773.

Proves emit_configurable_alert is admitted into the runtime API enum so a
feature can declare it directly in a runtime[<event>] entry (per-feature
re-homing of JSON-key configurable override alerts, part of #733).

Covers end-to-end:
  t1  the schema enum admits "emit_configurable_alert"
  t2  the schema-sourced checks._RUNTIME_API_ENUM admits it
  t3  a feature declaring emit_configurable_alert in runtime[Stop]
      validates clean via validate_meta_contract (declarable)
  t4  a feature declaring a bogus api value is STILL rejected
  t5  the runtime dispatcher protocol resolves the api to a callable
      runtime function (getattr resolution, mirroring rabbit-cage's
      _dispatcher_lib._invoke) and invoking it returns a typed result

Non-interactive. Exits non-zero on failure.
"""

import importlib.util
import json
import os
import sys
import tempfile

FEATURE_DIR = os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
)
sys.path.insert(0, FEATURE_DIR)
SCHEMA_PATH = os.path.join(FEATURE_DIR, "schemas", "runtime.schema.json")
CHECKS_PATH = os.path.join(FEATURE_DIR, "lib", "checks.py")

API = "emit_configurable_alert"
FAIL = 0


def fail(msg):
    global FAIL
    print(f"FAIL: {msg}", file=sys.stderr)
    FAIL = 1


def ok(msg):
    print(f"PASS: {msg}")


def load_checks():
    spec = importlib.util.spec_from_file_location("contract_lib_checks_773", CHECKS_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# t1: the schema enum admits emit_configurable_alert
with open(SCHEMA_PATH) as f:
    schema = json.load(f)
enum = schema["definitions"]["call_list"]["items"]["properties"]["api"]["enum"]
if API in enum:
    ok(f"t1: runtime.schema.json api enum admits {API!r}")
else:
    fail(f"t1: {API!r} not in runtime api enum: {sorted(enum)}")

# t2: the schema-sourced checks enum admits it (Inv 33 flow-through)
checks = load_checks()
if API in checks._RUNTIME_API_ENUM:
    ok(f"t2: checks._RUNTIME_API_ENUM (schema-sourced) admits {API!r}")
else:
    fail(f"t2: {API!r} not in checks._RUNTIME_API_ENUM")


def make_feature(root, name, feature):
    fdir = os.path.join(root, ".claude", "features", name)
    os.makedirs(fdir, exist_ok=True)
    with open(os.path.join(fdir, "feature.json"), "w") as f:
        json.dump(feature, f)
    return fdir


# t3: a feature declaring emit_configurable_alert in runtime[Stop] validates clean
with tempfile.TemporaryDirectory() as td:
    feature = {
        "name": "rabbit-cage",
        "version": "1.0.0",
        "owner": "rabbit-workflow team",
        "deprecation_criterion": "n/a",
        "runtime": {
            "Stop": [
                {"api": API,
                 "args": {"feature_name": "rabbit-cage",
                          "configurable_id": "bypass-permissions"}}
            ]
        },
    }
    fdir = make_feature(td, "rabbit-cage", feature)
    res = checks.validate_meta_contract(fdir)
    if res.passed is True:
        ok(f"t3: feature declaring {API} in runtime[Stop] validates clean")
    else:
        fail(f"t3: declarable feature failed validation: "
             f"passed={res.passed} messages={res.messages!r}")

# t4: a feature declaring a bogus api value is STILL rejected
with tempfile.TemporaryDirectory() as td:
    feature = {
        "name": "feat-bogus",
        "version": "1.0.0",
        "owner": "rabbit-workflow team",
        "deprecation_criterion": "n/a",
        "runtime": {
            "Stop": [
                {"api": "emit_not_a_real_api", "args": {}}
            ]
        },
    }
    fdir = make_feature(td, "feat-bogus", feature)
    res = checks.validate_meta_contract(fdir)
    if res.passed is False:
        ok("t4: feature declaring a bogus runtime api is still rejected")
    else:
        fail(f"t4: bogus api unexpectedly validated: passed={res.passed}")

# t5: dispatcher protocol resolves the api to a runtime callable and invoking
#     it returns a typed result. Mirrors rabbit-cage _dispatcher_lib._invoke:
#     getattr(runtime, api_name), inject repo_root, call with declared args.
import inspect  # noqa: E402
from lib import runtime as rt  # noqa: E402

fn = getattr(rt, API, None)
if fn is None or not callable(fn):
    fail(f"t5a: runtime.{API} is not resolvable/callable via getattr")
else:
    ok(f"t5a: dispatcher getattr resolves runtime.{API} to a callable")
    # the function declares repo_root (dispatcher injects it) — confirm
    # the dispatcher protocol's repo_root injection is accepted.
    sig = inspect.signature(fn)
    if "repo_root" in sig.parameters:
        ok("t5b: runtime function accepts dispatcher-injected repo_root kwarg")
    else:
        fail("t5b: runtime function lacks repo_root kwarg the dispatcher injects")
    # invoke as the dispatcher would: declared args + injected repo_root
    with tempfile.TemporaryDirectory() as td:
        conf = {
            "id": "bypass-permissions",
            "subcommand": "bypass-permissions",
            "storage": {"type": "json-key",
                        "file": ".claude/settings.local.json",
                        "key": "permissions.defaultMode"},
            "values": {
                "true": {"api": "set_json_key",
                         "args": {"file": ".claude/settings.local.json",
                                  "key": "permissions.defaultMode",
                                  "value": "bypassPermissions"}},
                "false": {"api": "delete_json_key",
                          "args": {"file": ".claude/settings.local.json",
                                   "key": "permissions.defaultMode"}},
            },
            "default": "false",
            "alert-on": "true",
            "alert-message": {"text": "BYPASS-PERMISSIONS MODE ACTIVE",
                              "icon": "siren", "color": "red"},
        }
        make_feature(td, "rabbit-cage", {"name": "rabbit-cage",
                                         "version": "1.0.0", "owner": "x",
                                         "configuration": [conf]})
        sf = os.path.join(td, ".claude", "settings.local.json")
        os.makedirs(os.path.dirname(sf), exist_ok=True)
        with open(sf, "w") as f:
            json.dump({"permissions": {"defaultMode": "bypassPermissions"}}, f)
        declared_args = {"feature_name": "rabbit-cage",
                         "configurable_id": "bypass-permissions"}
        kwargs = dict(declared_args)
        kwargs["repo_root"] = td  # dispatcher injection
        result = fn(**kwargs)
        if (isinstance(result, dict) and result.get("type") == "print"
                and result.get("text") == "BYPASS-PERMISSIONS MODE ACTIVE"):
            ok("t5c: dispatcher-style invocation returns the configurable's print_result")
        else:
            fail(f"t5c: unexpected dispatcher invocation result: {result!r}")

if FAIL:
    print("test-runtime-emit-configurable-alert-declarable: FAIL", file=sys.stderr)
    sys.exit(1)
print("test-runtime-emit-configurable-alert-declarable: all checks passed.")
