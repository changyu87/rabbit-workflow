#!/usr/bin/env python3
"""test-scope-guard-cage-owned-root.py — #855 / Inv 41.

End-to-end guard (real scope-guard.py subprocess) for the rabbit-cage
owned-repo-root-bootstrap carve-out:

  rabbit-cage owns three bootstrap files at the repo root, OUTSIDE its feature
  directory: install.sh, install.py, and the root README.md. The standalone
  per-feature scope-marker gate (Inv 5) authorizes writes only inside the named
  feature's directory, so editing rabbit-cage's own root bootstrap files would
  otherwise require an ad-hoc override. Inv 41 extends scope-guard so that when
  the active marker is `.rabbit-scope-active-rabbit-cage`, a write to any of the
  three owned root files is ALLOWED with no override.

Assertions:
  (i)   marker rabbit-cage active -> Write to root install.sh / install.py /
        README.md is ALLOWED (exit 0).
  (ii)  marker rabbit-cage active -> Write to an UNRELATED root file DENIED;
        Write to another feature's directory DENIED.
  (iii) a DIFFERENT feature's marker active -> Write to root install.sh /
        install.py / README.md DENIED (only rabbit-cage's marker authorizes).
  (iv)  RABBIT_CAGE_OWNED_ROOT lists exactly the three owned basenames.
"""
import glob
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

MARKER_CAGE = os.path.join(REPO_ROOT, ".rabbit-scope-active-rabbit-cage")
MARKER_OTHER = os.path.join(REPO_ROOT, ".rabbit-scope-active-contract")
GLOBAL_MARKER = os.path.join(REPO_ROOT, ".rabbit-scope-active")
OVERRIDE = os.path.join(REPO_ROOT, ".rabbit-scope-override")

OWNED_ROOTS = ("install.sh", "install.py", "README.md")

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


def run_scope_guard(file_path):
    payload = (
        '{"tool_name":"Write","tool_input":{"file_path":"'
        + file_path + '","content":"x"}}'
    )
    result = subprocess.run([sys.executable, SCOPE_GUARD], input=payload,
                            capture_output=True, text=True)
    return result.returncode, result.stderr


print("test-scope-guard-cage-owned-root.py")
print()

# --- Save + clear all live scope markers / override so the test is isolated ---
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

try:
    # === (i) rabbit-cage marker authorizes the three owned root files ===
    print("=== (i) .rabbit-scope-active-rabbit-cage authorizes owned root files ===")
    with open(MARKER_CAGE, "w") as f:
        f.write("rabbit-cage")

    for name in OWNED_ROOTS:
        target = os.path.join(REPO_ROOT, name)
        rc, stderr = run_scope_guard(target)
        if rc == 0:
            ok(f"Write to root {name} ALLOWED (exit 0) under rabbit-cage marker")
        else:
            fail_t(
                f"Write to root {name} exit {rc} (expected 0/ALLOW) under "
                f"rabbit-cage marker; stderr: {stderr.strip()}"
            )

    # === (ii) rabbit-cage marker does NOT broaden to other root paths / dirs ===
    print()
    print("=== (ii) carve-out does NOT broaden rabbit-cage's scope ===")

    unrelated_root = os.path.join(REPO_ROOT, "some-unrelated-root-file.txt")
    rc, stderr = run_scope_guard(unrelated_root)
    if rc != 0:
        ok("Write to unrelated root file DENIED under rabbit-cage marker")
    else:
        fail_t(
            "Write to unrelated root file unexpectedly ALLOWED under rabbit-cage "
            "marker — carve-out broadened beyond the owned set"
        )

    # Write to another feature's directory must still DENY. Skip only if a
    # sibling per-feature marker for that feature is live (parallel TDD cycle).
    other_feature_file = os.path.join(
        REPO_ROOT, ".claude/features/contract/some-new-file.txt")
    rc, stderr = run_scope_guard(other_feature_file)
    if rc != 0:
        ok("Write to another feature's dir DENIED under rabbit-cage marker")
    else:
        fail_t(
            "Write to another feature's dir unexpectedly ALLOWED under "
            "rabbit-cage marker — cross-scope leak"
        )

    if os.path.isfile(MARKER_CAGE):
        os.remove(MARKER_CAGE)

    # === (iii) a different feature's marker does NOT authorize the root files ===
    print()
    print("=== (iii) another feature's marker does NOT authorize owned root files ===")
    with open(MARKER_OTHER, "w") as f:
        f.write("contract")

    for name in OWNED_ROOTS:
        target = os.path.join(REPO_ROOT, name)
        rc, stderr = run_scope_guard(target)
        if rc != 0:
            ok(f"Write to root {name} DENIED under contract marker (only "
               f"rabbit-cage's marker authorizes)")
        else:
            fail_t(
                f"Write to root {name} unexpectedly ALLOWED under contract "
                f"marker — owned-root grant is NOT keyed to rabbit-cage alone"
            )

    if os.path.isfile(MARKER_OTHER):
        os.remove(MARKER_OTHER)

    # === (iv) RABBIT_CAGE_OWNED_ROOT is exactly the three owned basenames ===
    print()
    print("=== (iv) RABBIT_CAGE_OWNED_ROOT constant is explicit + minimal ===")
    src = read(SCOPE_GUARD)
    if "RABBIT_CAGE_OWNED_ROOT" not in src:
        fail_t("scope-guard.py does NOT define RABBIT_CAGE_OWNED_ROOT constant")
    else:
        # Import the module and read the constant for an exact-set assertion.
        import importlib.util
        spec = importlib.util.spec_from_file_location("scope_guard_855", SCOPE_GUARD)
        mod = importlib.util.module_from_spec(spec)
        try:
            spec.loader.exec_module(mod)
            owned = set(getattr(mod, "RABBIT_CAGE_OWNED_ROOT"))
            if owned == set(OWNED_ROOTS):
                ok(f"RABBIT_CAGE_OWNED_ROOT == {sorted(OWNED_ROOTS)} (exact set)")
            else:
                fail_t(
                    f"RABBIT_CAGE_OWNED_ROOT == {sorted(owned)} (expected "
                    f"{sorted(OWNED_ROOTS)}) — set must be minimal + exact"
                )
        except Exception as exc:
            fail_t(f"could not import scope-guard.py / read constant: {exc}")

finally:
    # Restore live markers / override exactly as found.
    for p in (MARKER_CAGE, MARKER_OTHER):
        if os.path.isfile(p):
            os.remove(p)
    if global_existed:
        with open(GLOBAL_MARKER, "w") as f:
            f.write(global_backup)
    for p, content in saved_per_markers:
        with open(p, "w") as f:
            f.write(content)
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
