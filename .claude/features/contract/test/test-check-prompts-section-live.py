#!/usr/bin/env python3
"""test-check-prompts-section-live.py — Inv 53 live-repo integration test.

Runs check_prompts_section against the REAL .claude/features/ tree (not a
synthetic tempdir). Closes the regression class where a synthetic-mock
surface diverges from the real repo (e.g. a prompts entry committed without
a matching template).

If this test fails it means the live repo has a real, on-disk violation of
the cross-feature prompts lint: a missing template, a duplicate id, a
missing inject file, an inject list without philosophy.md, an orphan
placeholder, or an orphan slot. Surface check_prompts_section's messages
verbatim — they identify the offending feature and reason.
"""

import os
import sys

FEATURE_DIR = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
REPO_ROOT = os.path.normpath(os.path.join(FEATURE_DIR, "..", "..", ".."))
FEATURES_ROOT = os.path.join(REPO_ROOT, ".claude", "features")

sys.path.insert(0, FEATURE_DIR)
from lib.checks import check_prompts_section  # noqa: E402

r = check_prompts_section(FEATURES_ROOT)
if not r.passed:
    print("FAIL: check_prompts_section reported violations against the live repo:", file=sys.stderr)
    for m in r.messages:
        print(f"  {m}", file=sys.stderr)
    sys.exit(1)

print("test-check-prompts-section-live: PASS")
