#!/usr/bin/env python3
"""test-spec-bodies-strict-tier.py — Inv 49 two-tier opt-in enforcement.

End-to-end test for the strict-tier / per-feature opt-in behaviour of
test-spec-bodies-no-historical-tags.py. Drives the checker as a subprocess
against fixture feature trees built under tempfile.TemporaryDirectory(),
using the RABBIT_HISTORICAL_TAGS_FEATURES_ROOT and
RABBIT_HISTORICAL_TAGS_CLEANED env overrides so the test never depends on
the live repo's cleanliness.

Behaviours covered (each from Inv 49):

  t1: a feature listed in CLEANED_FEATURES with a strict-tier violation
      (bare issue ref / tombstone language) FAILS and is named in stderr.
  t2: a NOT-cleaned feature with the SAME strict content is NOT flagged.
  t3: empty CLEANED_FEATURES => no strict flags for any feature.
  t4: a baseline-tier violation (e.g. BUG-N) IS flagged regardless of
      opt-in (cleaned or not).
  t5: CHANGELOG.md is never scanned (strict content there is exempt by
      construction).

Non-interactive. Exits non-zero on failure.
"""

import os
import subprocess
import sys
import tempfile

TEST_DIR = os.path.dirname(os.path.abspath(__file__))
CHECKER = os.path.join(TEST_DIR, "test-spec-bodies-no-historical-tags.py")

PASS = 0
FAIL = 0

# Fixture-content fragments assembled by concatenation so this test file
# itself contains no literal strict-tier strings that a future scan of the
# test corpus might trip on. The historical-tags checker only scans
# specs/*.md and skills/*/SKILL.md (never test/), but keeping the fixtures
# assembled is defensive and self-documenting.
_HASH_REF = "see " + "#" + "123 for context"
_TOMBSTONE = "this behaviour was " + "superseded" + " in a later release"
_BASELINE = "BUG" + "-7 tracked this"


def ok(name, msg):
    global PASS
    print(f"  PASS {name}: {msg}")
    PASS += 1


def fail(name, msg):
    global FAIL
    print(f"  FAIL {name}: {msg}", file=sys.stderr)
    FAIL += 1


def make_feature(root, name, spec_body, changelog_body=None):
    """Create <root>/<name>/specs/spec.md with spec_body, plus an optional
    CHANGELOG.md at the feature root."""
    specs = os.path.join(root, name, "specs")
    os.makedirs(specs, exist_ok=True)
    with open(os.path.join(specs, "spec.md"), "w") as f:
        f.write(spec_body)
    if changelog_body is not None:
        with open(os.path.join(root, name, "CHANGELOG.md"), "w") as f:
            f.write(changelog_body)


def run(features_root, cleaned):
    env = dict(os.environ)
    env["RABBIT_HISTORICAL_TAGS_FEATURES_ROOT"] = features_root
    env["RABBIT_HISTORICAL_TAGS_CLEANED"] = cleaned
    return subprocess.run(
        ["python3", CHECKER],
        capture_output=True,
        text=True,
        env=env,
    )


# t0: checker exists
if not os.path.isfile(CHECKER):
    fail("t0", f"checker missing: {CHECKER}")
    print(f"Results: {PASS} passed, {FAIL} failed")
    sys.exit(1)
ok("t0", "checker exists")

# t1: cleaned feature with strict violation -> FAIL, named in output.
with tempfile.TemporaryDirectory() as tmp:
    body = "# alpha\n\n" + _HASH_REF + "\n" + _TOMBSTONE + "\n"
    make_feature(tmp, "alpha", body)
    r = run(tmp, "alpha")
    if r.returncode != 0 and "alpha" in (r.stdout + r.stderr):
        ok("t1", "cleaned feature strict violation flagged")
    else:
        fail("t1", f"expected nonzero + 'alpha'; exit={r.returncode}; "
                   f"stdout={r.stdout}; stderr={r.stderr}")

# t2: NOT-cleaned feature with identical strict content -> NOT flagged.
with tempfile.TemporaryDirectory() as tmp:
    body = "# beta\n\n" + _HASH_REF + "\n" + _TOMBSTONE + "\n"
    make_feature(tmp, "beta", body)
    r = run(tmp, "alpha")  # beta not in cleaned set
    if r.returncode == 0:
        ok("t2", "not-cleaned feature strict content ignored")
    else:
        fail("t2", f"expected exit 0; exit={r.returncode}; "
                   f"stdout={r.stdout}; stderr={r.stderr}")

# t3: empty cleaned set -> no strict flags even for strict content.
with tempfile.TemporaryDirectory() as tmp:
    body = "# gamma\n\n" + _HASH_REF + "\n" + _TOMBSTONE + "\n"
    make_feature(tmp, "gamma", body)
    r = run(tmp, "")  # empty cleaned set
    if r.returncode == 0:
        ok("t3", "empty cleaned set => no strict flags")
    else:
        fail("t3", f"expected exit 0; exit={r.returncode}; "
                   f"stdout={r.stdout}; stderr={r.stderr}")

# t4: baseline violation flagged regardless of opt-in.
with tempfile.TemporaryDirectory() as tmp:
    body = "# delta\n\n" + _BASELINE + "\n"
    make_feature(tmp, "delta", body)
    # delta NOT in cleaned set, but baseline tier is unconditional.
    r = run(tmp, "")
    if r.returncode != 0 and "delta" in (r.stdout + r.stderr):
        ok("t4", "baseline violation flagged regardless of opt-in")
    else:
        fail("t4", f"expected nonzero + 'delta'; exit={r.returncode}; "
                   f"stdout={r.stdout}; stderr={r.stderr}")

# t5: CHANGELOG.md is never scanned (strict content there is exempt).
with tempfile.TemporaryDirectory() as tmp:
    clean_spec = "# epsilon\n\ncurrent design only\n"
    changelog = "# Changelog\n\n" + _HASH_REF + "\n" + _TOMBSTONE + "\n"
    make_feature(tmp, "epsilon", clean_spec, changelog_body=changelog)
    r = run(tmp, "epsilon")  # opted in, but CHANGELOG is exempt
    if r.returncode == 0:
        ok("t5", "CHANGELOG.md never scanned (exempt by construction)")
    else:
        fail("t5", f"expected exit 0; exit={r.returncode}; "
                   f"stdout={r.stdout}; stderr={r.stderr}")

print()
print(f"Results: {PASS} passed, {FAIL} failed")

if FAIL > 0:
    print("test-spec-bodies-strict-tier: FAIL", file=sys.stderr)
    sys.exit(1)

print("test-spec-bodies-strict-tier: all checks passed.")
sys.exit(0)
