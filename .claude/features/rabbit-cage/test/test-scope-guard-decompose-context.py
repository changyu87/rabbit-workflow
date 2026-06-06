#!/usr/bin/env python3
"""test-scope-guard-decompose-context.py — #923 / Inv 47.

End-to-end guard (real scope-guard.py subprocess) for the decompose-context
pass-through marker `.rabbit/.runtime/decompose-active`:

  Orchestration that does batch work across several feature directories sets a
  bounded, auto-cleared JSON marker `{operation, features, expires?}` BEFORE
  the batch work and clears it AFTER. While the marker is present, un-expired,
  and well-formed, scope-guard ALLOWs writes inside any feature directory named
  in `features` — with no per-feature scope marker and no manual override. This
  is the principled replacement for the manual session override; the existing
  per-feature markers and the legacy `.rabbit-scope-override` paths are
  unchanged (additive coexistence).

Assertions:
  (i)   marker authorizing A + B  -> Write inside A and inside B both ALLOWED.
  (ii)  marker authorizing A only -> Write inside an unauthorized feature C's
        dir is DENIED.
  (iii) marker ABSENT             -> Write inside A's dir (no per-feature marker)
        is DENIED (normal bounded-scope rules unchanged).
  (iv)  marker present but expires in the PAST -> treated as absent (DENY).
  (v)   malformed-JSON marker AND empty-`features` marker -> treated as absent
        (DENY).
  (vi)  regression — a per-feature .rabbit-scope-active-<feature> marker and a
        legacy `session` override still ALLOW with the decompose marker absent.
"""
import datetime
import glob
import json
import os
import subprocess
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = subprocess.run(
    ["git", "-C", SCRIPT_DIR, "rev-parse", "--show-toplevel"],
    capture_output=True, text=True, check=True,
).stdout.strip()
SCOPE_GUARD = os.path.join(
    REPO_ROOT, ".claude/features/rabbit-cage/hooks/scope-guard.py")

# Three resolvable, distinct feature names. A = rabbit-cage, B = contract,
# C = policy. Each resolves via find-feature.py to .claude/features/<name>/.
FEAT_A = "rabbit-cage"
FEAT_B = "contract"
FEAT_C = "policy"

DECOMPOSE_MARKER = os.path.join(
    REPO_ROOT, ".rabbit", ".runtime", "decompose-active")
OVERRIDE = os.path.join(REPO_ROOT, ".rabbit-scope-override")
GLOBAL_MARKER = os.path.join(REPO_ROOT, ".rabbit-scope-active")

failures = 0
total = 0


def ok(msg):
    global total
    total += 1
    print(f"  PASS t{total}: {msg}")


def fail_t(msg):
    global total, failures
    total += 1
    failures += 1
    print(f"  FAIL t{total}: {msg}")


def read(path):
    try:
        with open(path) as f:
            return f.read()
    except Exception:
        return ""


def target_in(feature_name, leaf="some-decompose-batch-file.txt"):
    return os.path.join(
        REPO_ROOT, ".claude", "features", feature_name, leaf)


def run_scope_guard(file_path):
    payload = json.dumps(
        {"tool_name": "Write",
         "tool_input": {"file_path": file_path, "content": "x"}})
    result = subprocess.run([sys.executable, SCOPE_GUARD], input=payload,
                            capture_output=True, text=True)
    return result.returncode, result.stderr


def write_marker(obj_or_text):
    os.makedirs(os.path.dirname(DECOMPOSE_MARKER), exist_ok=True)
    with open(DECOMPOSE_MARKER, "w") as f:
        if isinstance(obj_or_text, str):
            f.write(obj_or_text)
        else:
            json.dump(obj_or_text, f)


def clear_marker():
    if os.path.isfile(DECOMPOSE_MARKER):
        os.remove(DECOMPOSE_MARKER)


def iso(dt):
    return dt.replace(microsecond=0).isoformat()


print("test-scope-guard-decompose-context.py")
print()

# --- Save + clear all live scope state so the test is isolated ---
global_existed = os.path.isfile(GLOBAL_MARKER)
global_backup = read(GLOBAL_MARKER) if global_existed else ""
if global_existed:
    os.remove(GLOBAL_MARKER)

saved_per_markers = []
for p in glob.glob(os.path.join(REPO_ROOT, ".rabbit-scope-active-*")):
    if os.path.isfile(p):
        saved_per_markers.append((p, read(p)))
        os.remove(p)

override_existed = os.path.isfile(OVERRIDE)
override_backup = read(OVERRIDE) if override_existed else ""
if override_existed:
    os.remove(OVERRIDE)

decompose_existed = os.path.isfile(DECOMPOSE_MARKER)
decompose_backup = read(DECOMPOSE_MARKER) if decompose_existed else ""
clear_marker()

# A future / past timestamp for expiry cases (UTC, offset-aware).
now = datetime.datetime.now(datetime.timezone.utc)
future = iso(now + datetime.timedelta(hours=1))
past = iso(now - datetime.timedelta(hours=1))

try:
    # === (i) marker authorizing A + B allows writes inside both ===
    print("=== (i) decompose marker authorizing A + B ALLOWs writes in both ===")
    write_marker({"operation": "rabbit-decompose batch scaffold",
                  "features": [FEAT_A, FEAT_B],
                  "expires": future})
    for feat in (FEAT_A, FEAT_B):
        rc, stderr = run_scope_guard(target_in(feat))
        if rc == 0:
            ok(f"Write inside authorized feature '{feat}' ALLOWED (exit 0)")
        else:
            fail_t(f"Write inside authorized feature '{feat}' exit {rc} "
                   f"(expected 0/ALLOW); stderr: {stderr.strip()}")
    clear_marker()

    # === (ii) marker authorizing A only DENYs a write inside C ===
    print()
    print("=== (ii) marker authorizing A only DENYs an unauthorized feature ===")
    write_marker({"operation": "batch", "features": [FEAT_A], "expires": future})
    rc, stderr = run_scope_guard(target_in(FEAT_C))
    if rc != 0:
        ok(f"Write inside unauthorized feature '{FEAT_C}' DENIED")
    else:
        fail_t(f"Write inside unauthorized feature '{FEAT_C}' unexpectedly "
               f"ALLOWED — pass-through widened beyond its named set")
    clear_marker()

    # === (iii) marker ABSENT -> normal bounded-scope rules (DENY) ===
    print()
    print("=== (iii) marker ABSENT -> Write inside A DENIED (normal rules) ===")
    rc, stderr = run_scope_guard(target_in(FEAT_A))
    if rc != 0:
        ok("Write inside A with no marker + no per-feature scope DENIED")
    else:
        fail_t("Write inside A unexpectedly ALLOWED with NO decompose marker "
               "and NO per-feature scope marker — bounded-scope rules broken")

    # === (iv) expired marker treated as absent ===
    print()
    print("=== (iv) marker with expires in the PAST treated as absent (DENY) ===")
    write_marker({"operation": "batch", "features": [FEAT_A], "expires": past})
    rc, stderr = run_scope_guard(target_in(FEAT_A))
    if rc != 0:
        ok("Write inside A DENIED while decompose marker is EXPIRED")
    else:
        fail_t("Write inside A unexpectedly ALLOWED while the decompose marker "
               "is EXPIRED — stale marker must not widen scope")
    clear_marker()

    # === (v) malformed-JSON and empty-features markers treated as absent ===
    print()
    print("=== (v) malformed / empty-features marker treated as absent (DENY) ===")
    write_marker("this is not valid json {{{")
    rc, stderr = run_scope_guard(target_in(FEAT_A))
    if rc != 0:
        ok("Write inside A DENIED with a MALFORMED-JSON decompose marker")
    else:
        fail_t("Write inside A unexpectedly ALLOWED with a malformed decompose "
               "marker — a broken marker must not widen scope")
    clear_marker()

    write_marker({"operation": "batch", "features": [], "expires": future})
    rc, stderr = run_scope_guard(target_in(FEAT_A))
    if rc != 0:
        ok("Write inside A DENIED with an EMPTY-features decompose marker")
    else:
        fail_t("Write inside A unexpectedly ALLOWED with an empty-features "
               "decompose marker — must not widen scope")
    clear_marker()

    # === (vi) regression: per-feature marker + legacy session override ===
    print()
    print("=== (vi) regression — per-feature marker + session override unchanged ===")
    # No decompose marker present.
    per_marker = os.path.join(REPO_ROOT, f".rabbit-scope-active-{FEAT_A}")
    with open(per_marker, "w") as f:
        f.write(FEAT_A)
    rc, stderr = run_scope_guard(target_in(FEAT_A))
    if rc == 0:
        ok(f"per-feature .rabbit-scope-active-{FEAT_A} still ALLOWs its scope")
    else:
        fail_t(f"per-feature marker regressed: Write inside A exit {rc} "
               f"(expected 0); stderr: {stderr.strip()}")
    if os.path.isfile(per_marker):
        os.remove(per_marker)

    with open(OVERRIDE, "w") as f:
        f.write("session")
    rc, stderr = run_scope_guard(target_in(FEAT_C))
    if rc == 0:
        ok("legacy `session` override still ALLOWs any write")
    else:
        fail_t(f"legacy session override regressed: exit {rc} (expected 0); "
               f"stderr: {stderr.strip()}")
    if os.path.isfile(OVERRIDE):
        os.remove(OVERRIDE)

finally:
    # Restore live state exactly as found.
    clear_marker()
    if decompose_existed:
        os.makedirs(os.path.dirname(DECOMPOSE_MARKER), exist_ok=True)
        with open(DECOMPOSE_MARKER, "w") as f:
            f.write(decompose_backup)
    for p in glob.glob(os.path.join(REPO_ROOT, ".rabbit-scope-active-*")):
        if os.path.isfile(p):
            os.remove(p)
    for p, content in saved_per_markers:
        with open(p, "w") as f:
            f.write(content)
    if global_existed:
        with open(GLOBAL_MARKER, "w") as f:
            f.write(global_backup)
    if os.path.isfile(OVERRIDE):
        os.remove(OVERRIDE)
    if override_existed:
        with open(OVERRIDE, "w") as f:
            f.write(override_backup)

print()
print(f"Results: {total - failures} passed, {failures} failed")
if failures == 0:
    print("ALL TESTS PASSED")
    sys.exit(0)
else:
    print(f"{failures} TEST(S) FAILED")
    sys.exit(1)
