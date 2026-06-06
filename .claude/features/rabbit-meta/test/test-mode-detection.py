#!/usr/bin/env python3
"""test-mode-detection.py — Inv 1

End-to-end test verifying detect_mode(cwd) vendored/standalone detection:
  - t1: cwd ends in .rabbit and parent has sibling content -> "vendored"
  - t2: cwd is a non-.rabbit directory with no .rabbit ancestor -> "standalone"
  - t3: cwd ends in .rabbit but parent contains only .rabbit -> "standalone"
  - t4: cwd is a sub-directory of .rabbit (basename != .rabbit) -> "standalone"
  - t5: cwd does not exist on disk -> "standalone" (MUST NOT raise)

And the is_vendored(mode) coexistence predicate (Inv 1(b)):
  - t6: is_vendored("vendored") -> True
  - t7: is_vendored("plugin") -> True (dual-accepts the older marker spelling)
  - t8: is_vendored("standalone") -> False
  - t9: is_vendored(<any other value>) -> False
"""

import os
import sys
import tempfile

FEATURE_DIR = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, FEATURE_DIR)

from lib.mode_detection import detect_mode, is_vendored  # noqa: E402

PASS = 0
FAIL = 0


def ok(n, msg):
    global PASS
    print(f"  PASS {n}: {msg}")
    PASS += 1


def fail_t(n, msg):
    global FAIL
    print(f"  FAIL {n}: {msg}", file=sys.stderr)
    FAIL += 1


# t1: cwd ends in .rabbit and parent has sibling content -> "vendored"
with tempfile.TemporaryDirectory() as tmp:
    proj = os.path.join(tmp, "proj")
    os.makedirs(os.path.join(proj, ".rabbit"))
    os.makedirs(os.path.join(proj, "src"))
    rabbit_dir = os.path.join(proj, ".rabbit")
    result = detect_mode(rabbit_dir)
    if result == "vendored":
        ok("t1", f"sibling content -> 'vendored' (got {result!r})")
    else:
        fail_t("t1", f"expected 'vendored', got {result!r}")

# t2: cwd is a non-.rabbit directory with no .rabbit ancestor -> "standalone"
with tempfile.TemporaryDirectory() as tmp:
    repo = os.path.join(tmp, "rabbit-self")
    os.makedirs(repo)
    os.makedirs(os.path.join(repo, "src"))
    result = detect_mode(repo)
    if result == "standalone":
        ok("t2", f"non-.rabbit basename -> 'standalone' (got {result!r})")
    else:
        fail_t("t2", f"expected 'standalone', got {result!r}")

# t3: cwd ends in .rabbit but parent contains only .rabbit -> "standalone"
with tempfile.TemporaryDirectory() as tmp:
    # Degenerate: parent contains only .rabbit.
    parent = os.path.join(tmp, "solo")
    os.makedirs(parent)
    rabbit_dir = os.path.join(parent, ".rabbit")
    os.makedirs(rabbit_dir)
    result = detect_mode(rabbit_dir)
    if result == "standalone":
        ok("t3", f"degenerate solo .rabbit -> 'standalone' (got {result!r})")
    else:
        fail_t("t3", f"expected 'standalone', got {result!r}")

# t4: cwd is a sub-directory of .rabbit (basename != .rabbit) -> "standalone"
with tempfile.TemporaryDirectory() as tmp:
    proj = os.path.join(tmp, "proj")
    os.makedirs(os.path.join(proj, "src"))
    sub = os.path.join(proj, ".rabbit", "sub")
    os.makedirs(sub)
    result = detect_mode(sub)
    if result == "standalone":
        ok("t4", f"sub-dir of .rabbit -> 'standalone' (got {result!r})")
    else:
        fail_t("t4", f"expected 'standalone', got {result!r}")

# t5: cwd does not exist on disk -> "standalone" (MUST NOT raise)
with tempfile.TemporaryDirectory() as tmp:
    missing = os.path.join(tmp, "does-not-exist", ".rabbit")
    try:
        result = detect_mode(missing)
    except Exception as e:
        fail_t("t5", f"raised {type(e).__name__}: {e}")
        result = None
    if result == "standalone":
        ok("t5", f"non-existent path -> 'standalone' (got {result!r})")
    elif result is not None:
        fail_t("t5", f"expected 'standalone', got {result!r}")

# t6: is_vendored("vendored") -> True (the current spelling)
if is_vendored("vendored") is True:
    ok("t6", "is_vendored('vendored') -> True")
else:
    fail_t("t6", f"expected True, got {is_vendored('vendored')!r}")

# t7: is_vendored("plugin") -> True (dual-accepts the older marker spelling)
if is_vendored("plugin") is True:
    ok("t7", "is_vendored('plugin') -> True (older marker dual-accepted)")
else:
    fail_t("t7", f"expected True, got {is_vendored('plugin')!r}")

# t8: is_vendored("standalone") -> False
if is_vendored("standalone") is False:
    ok("t8", "is_vendored('standalone') -> False")
else:
    fail_t("t8", f"expected False, got {is_vendored('standalone')!r}")

# t9: is_vendored(<any other value>) -> False
if is_vendored("bogus") is False and is_vendored("") is False:
    ok("t9", "is_vendored(other) -> False")
else:
    fail_t("t9", "expected False for unrecognized values")

print()
print(f"Results: {PASS} passed, {FAIL} failed")
sys.exit(0 if FAIL == 0 else 1)
