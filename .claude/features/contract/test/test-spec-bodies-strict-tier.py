#!/usr/bin/env python3
"""test-spec-bodies-strict-tier.py — Inv 49 two-tier opt-in enforcement.

End-to-end test for the strict-tier / per-feature opt-in behaviour of
test-spec-bodies-no-historical-tags.py. Drives the checker as a subprocess
against fixture feature trees built under tempfile.TemporaryDirectory(),
using the RABBIT_HISTORICAL_TAGS_FEATURES_ROOT and
RABBIT_HISTORICAL_TAGS_CLEANED env overrides so the test never depends on
the live repo's cleanliness.

Behaviours covered (each from Inv 49):

  t1: a feature in the opt-in set (via env override) with a strict-tier
      violation (bare issue ref / tombstone language) FAILS and is named
      in stderr.
  t2: a NOT-opted-in feature with the SAME strict content is NOT flagged.
  t3: empty opt-in set => no strict flags for any feature.
  t4: a baseline-tier violation (e.g. BUG-N) IS flagged regardless of
      opt-in.
  t5: CHANGELOG.md is never scanned (strict content there is exempt by
      construction).
  t6: data-driven opt-in — a feature whose OWN feature.json has
      "housekeeping_clean": true is strict-enforced WITHOUT the env
      override; the same strict content in a feature WITHOUT the flag is
      ignored.
  t7: the RABBIT_HISTORICAL_TAGS_CLEANED env override REPLACES the
      feature.json-derived set: a feature with the flag is NOT enforced
      when the override names a different (or empty) set.

Non-interactive. Exits non-zero on failure.
"""

import json
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


def make_feature(root, name, spec_body, changelog_body=None,
                 housekeeping_clean=None):
    """Create <root>/<name>/specs/spec.md with spec_body, plus an optional
    CHANGELOG.md at the feature root. When housekeeping_clean is not None,
    write a feature.json with that top-level flag value."""
    specs = os.path.join(root, name, "specs")
    os.makedirs(specs, exist_ok=True)
    with open(os.path.join(specs, "spec.md"), "w") as f:
        f.write(spec_body)
    if changelog_body is not None:
        with open(os.path.join(root, name, "CHANGELOG.md"), "w") as f:
            f.write(changelog_body)
    if housekeeping_clean is not None:
        with open(os.path.join(root, name, "feature.json"), "w") as f:
            json.dump({"name": name, "housekeeping_clean": housekeeping_clean},
                      f)


def run(features_root, cleaned=None):
    """Run the checker against features_root. When cleaned is None the
    RABBIT_HISTORICAL_TAGS_CLEANED override is NOT set (the checker derives
    the opt-in set from each feature's feature.json). When cleaned is a
    string it is passed as the override (REPLACES the derived set)."""
    env = dict(os.environ)
    env["RABBIT_HISTORICAL_TAGS_FEATURES_ROOT"] = features_root
    env.pop("RABBIT_HISTORICAL_TAGS_CLEANED", None)
    if cleaned is not None:
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

# t6: data-driven opt-in via feature.json housekeeping_clean (NO env
# override). A feature with the flag true is strict-enforced; a sibling
# feature with the same strict content but no flag is ignored.
with tempfile.TemporaryDirectory() as tmp:
    strict_body = "# zeta\n\n" + _HASH_REF + "\n" + _TOMBSTONE + "\n"
    make_feature(tmp, "zeta", strict_body, housekeeping_clean=True)
    make_feature(tmp, "eta", strict_body, housekeeping_clean=False)
    r = run(tmp)  # no env override -> derive from feature.json
    out = r.stdout + r.stderr
    if r.returncode != 0 and "zeta" in out and "eta" not in out:
        ok("t6", "feature.json housekeeping_clean drives opt-in")
    else:
        fail("t6", f"expected nonzero naming zeta only; exit={r.returncode}; "
                   f"stdout={r.stdout}; stderr={r.stderr}")

# t7: the env override REPLACES the feature.json-derived set. A feature
# with the flag true is NOT enforced when the override is set to a set
# that excludes it (here: empty string => empty set).
with tempfile.TemporaryDirectory() as tmp:
    strict_body = "# theta\n\n" + _HASH_REF + "\n" + _TOMBSTONE + "\n"
    make_feature(tmp, "theta", strict_body, housekeeping_clean=True)
    r = run(tmp, "")  # override replaces derived set with empty set
    if r.returncode == 0:
        ok("t7", "env override replaces feature.json-derived set")
    else:
        fail("t7", f"expected exit 0; exit={r.returncode}; "
                   f"stdout={r.stdout}; stderr={r.stderr}")

print()
print(f"Results: {PASS} passed, {FAIL} failed")

if FAIL > 0:
    print("test-spec-bodies-strict-tier: FAIL", file=sys.stderr)
    sys.exit(1)

print("test-spec-bodies-strict-tier: all checks passed.")
sys.exit(0)
