#!/usr/bin/env python3
"""test-validate-feature-ref-resolution.py — regression for issue #1053.

validate_feature() in lib/checks.py validates a feature.json against
schemas/feature.json.schema.json. That schema carries RELATIVE sibling $refs
(manifest.schema.json, runtime.schema.json, configuration.schema.json,
prompts.schema.json). Under jsonschema 4.17.3 a bare
`jsonschema.validate(data, schema)` cannot resolve those relative refs and
raises RefResolutionError ("unknown url type: 'manifest.schema.json'") the
moment validation DESCENDS into one of them — which happens for every real
feature.json that carries a `manifest` section. RefResolutionError is NOT a
ValidationError, so it escaped the existing try/except and crashed the caller,
reddening the contract repo gate (and rabbit-spec / rabbit-feature suites that
invoke validate-feature).

This test pins both directions of the fix:

  t1  validate_feature SUCCEEDS on a real feature that HAS a manifest section
      (descends into the manifest $ref) — this is the case that crashed.
  t2  validate_feature SUCCEEDS on a real feature with a prompts section
      (descends into another sibling $ref).
  t3  validate_feature still REJECTS an invalid feature.json (one that
      violates the schema) — proving the resolver fix did not disable
      schema validation by swallowing errors.

Non-interactive. Exits non-zero on any failure.

Version: 1.0.0
Owner: rabbit-workflow team (contract)
Deprecation criterion: when feature.json schema $refs are inlined (no sibling
$refs to resolve) or jsonschema is dropped as a dependency.
"""

import importlib.util
import json
import os
import shutil
import sys
import tempfile

TEST_DIR = os.path.dirname(os.path.abspath(__file__))
FEATURE_DIR = os.path.normpath(os.path.join(TEST_DIR, ".."))
CHECKS_PATH = os.path.join(FEATURE_DIR, "lib", "checks.py")
FEATURES_ROOT = os.path.normpath(os.path.join(FEATURE_DIR, ".."))

PASS = 0
FAIL = 0


def ok(name, msg):
    global PASS
    print(f"  PASS {name}: {msg}")
    PASS += 1


def bad(name, msg):
    global FAIL
    print(f"  FAIL {name}: {msg}", file=sys.stderr)
    FAIL += 1


def load_checks():
    spec = importlib.util.spec_from_file_location(
        "contract_lib_checks_refres", CHECKS_PATH
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


try:
    import jsonschema  # noqa: F401
    _HAVE_JSONSCHEMA = True
except ImportError:
    _HAVE_JSONSCHEMA = False

checks = load_checks()


def has_section(feature_name, key):
    fj = os.path.join(FEATURES_ROOT, feature_name, "feature.json")
    if not os.path.isfile(fj):
        return False
    with open(fj) as f:
        return bool(json.load(f).get(key))


# t1: a real feature that HAS a manifest validates successfully.
manifest_feature = None
for cand in ("rabbit-cage", "rabbit-feature"):
    if has_section(cand, "manifest"):
        manifest_feature = cand
        break

if manifest_feature is None:
    bad("t1", "no real feature with a manifest section found to exercise the $ref")
else:
    res = checks.validate_feature(os.path.join(FEATURES_ROOT, manifest_feature))
    if res.passed:
        ok("t1", f"validate_feature passed on {manifest_feature} (manifest $ref resolved)")
    else:
        bad("t1", f"validate_feature failed on {manifest_feature}: {res.messages}")

# t2: a real feature carrying a prompts section validates (another $ref).
prompts_feature = None
for cand in ("tdd-subagent", "rabbit-spec"):
    if has_section(cand, "prompts"):
        prompts_feature = cand
        break

if prompts_feature is None:
    ok("t2", "no feature with prompts section on disk — skipped (manifest path covered by t1)")
else:
    res = checks.validate_feature(os.path.join(FEATURES_ROOT, prompts_feature))
    if res.passed:
        ok("t2", f"validate_feature passed on {prompts_feature} (prompts $ref resolved)")
    else:
        bad("t2", f"validate_feature failed on {prompts_feature}: {res.messages}")

# t3: an INVALID feature.json (schema violation) still FAILS validation, so
# the ref-resolver fix did not silently disable schema checking. We build a
# fixture whose feature.json has a malformed manifest entry (manifest items
# require {api, args}; an item missing `api` violates manifest.schema.json),
# which is only detectable if the $ref is actually resolved AND enforced.
if not _HAVE_JSONSCHEMA:
    ok("t3", "jsonschema not installed — schema-violation arm not applicable")
else:
    d = tempfile.mkdtemp(prefix="contract-refres-invalid-")
    try:
        name = os.path.basename(d)
        os.makedirs(os.path.join(d, "specs"))
        os.makedirs(os.path.join(d, "test"))
        with open(os.path.join(d, "specs/spec.md"), "w") as f:
            f.write("# spec\nbody\n")
        with open(os.path.join(d, "specs/contract.md"), "w") as f:
            f.write("# contract\nbody\n")
        run_py = os.path.join(d, "test/run.py")
        with open(run_py, "w") as f:
            f.write("#!/usr/bin/env python3\nimport sys; sys.exit(0)\n")
        os.chmod(run_py, 0o755)
        feature_data = {
            "name": name,
            "version": "0.1.0",
            "owner": "rabbit-workflow team",
            "tdd_state": "spec",
            "summary": "Invalid-manifest fixture for #1053.",
            "deprecation_criterion": "when test is done",
            # manifest item missing required `api` field → schema violation,
            # only caught if the manifest $ref is resolved and enforced.
            "manifest": [{"args": {}}],
        }
        with open(os.path.join(d, "feature.json"), "w") as f:
            json.dump(feature_data, f, indent=2)

        res = checks.validate_feature(d)
        violation = any("schema violation" in m for m in res.messages)
        if not res.passed and violation:
            ok("t3", "invalid manifest in feature.json still fails schema validation")
        else:
            bad(
                "t3",
                f"expected schema-violation failure, got passed={res.passed} "
                f"messages={res.messages}",
            )
    finally:
        shutil.rmtree(d, ignore_errors=True)


print(f"\nResults: {PASS} passed, {FAIL} failed")
sys.exit(1 if FAIL else 0)
