#!/usr/bin/env python3
"""test-generate-readme.py — Inv 3

End-to-end test verifying README.md template + generate_readme generator:
  - t1: template file exists at expected location
  - t2: template contains the killer-story prose ("rabbit-feature-new")
  - t3: template contains "What to do next" section with 3 numbered items
  - t4: template links to "upstream rabbit-workflow"
  - t5: generator writes the output verbatim
  - t6: generator is idempotent (second call returns "no-op")
  - t7: generator raises FileNotFoundError on missing template
"""

import os
import sys
import tempfile

FEATURE_DIR = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, FEATURE_DIR)

from lib.generate_readme import generate_readme  # noqa: E402

TEMPLATE_PATH = os.path.join(FEATURE_DIR, "templates", "README.md.template")

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


# t1: template file exists
if os.path.isfile(TEMPLATE_PATH):
    ok("t1", f"template exists at {TEMPLATE_PATH}")
else:
    fail_t("t1", f"template missing at {TEMPLATE_PATH}")

# Load template content for subsequent tests; bail gracefully if missing.
template_content = ""
if os.path.isfile(TEMPLATE_PATH):
    with open(TEMPLATE_PATH, "r") as f:
        template_content = f.read()

# t2: killer-story prose
if "rabbit-feature-new" in template_content:
    ok("t2", "template contains killer-story ('rabbit-feature-new')")
else:
    fail_t("t2", "template missing killer-story marker 'rabbit-feature-new'")

# t3: "What to do next" section with 3 numbered items
if "What to do next" in template_content:
    # Look for "1.", "2.", "3." in the content after the heading.
    after = template_content.split("What to do next", 1)[1]
    has_three = ("1." in after) and ("2." in after) and ("3." in after)
    if has_three:
        ok("t3", "template has 'What to do next' with 3 numbered items")
    else:
        fail_t("t3", "'What to do next' section missing one of items 1./2./3.")
else:
    fail_t("t3", "template missing 'What to do next' section")

# t4: link to upstream rabbit-workflow
if "upstream rabbit-workflow" in template_content:
    ok("t4", "template links to 'upstream rabbit-workflow'")
else:
    fail_t("t4", "template missing 'upstream rabbit-workflow' link text")

# t5: generator writes the output verbatim
with tempfile.TemporaryDirectory() as tmp:
    out_path = os.path.join(tmp, "README.md")
    result = generate_readme(TEMPLATE_PATH, out_path)
    if result != "wrote":
        fail_t("t5", f"expected return 'wrote', got {result!r}")
    else:
        with open(out_path, "r") as f:
            written = f.read()
        if written == template_content:
            ok("t5", "generator wrote output verbatim")
        else:
            fail_t("t5", "written content does not match template verbatim")

# t6: idempotent — second call returns "no-op"
with tempfile.TemporaryDirectory() as tmp:
    out_path = os.path.join(tmp, "README.md")
    r1 = generate_readme(TEMPLATE_PATH, out_path)
    r2 = generate_readme(TEMPLATE_PATH, out_path)
    if r1 == "wrote" and r2 == "no-op":
        ok("t6", "generator is idempotent (wrote then no-op)")
    else:
        fail_t("t6", f"expected ('wrote', 'no-op'), got ({r1!r}, {r2!r})")

# t7: FileNotFoundError on missing template
with tempfile.TemporaryDirectory() as tmp:
    missing = os.path.join(tmp, "does-not-exist.template")
    out_path = os.path.join(tmp, "README.md")
    try:
        generate_readme(missing, out_path)
        fail_t("t7", "expected FileNotFoundError, no exception raised")
    except FileNotFoundError:
        ok("t7", "raised FileNotFoundError on missing template")
    except Exception as e:
        fail_t("t7", f"expected FileNotFoundError, got {type(e).__name__}: {e}")

print()
print(f"Results: {PASS} passed, {FAIL} failed")
sys.exit(0 if FAIL == 0 else 1)
