#!/usr/bin/env python3
# test-templates-have-version.py — verify every template file carries a template_version marker.

import os
import re
import sys
import glob

FEATURE_DIR = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
TEMPLATES_DIR = os.path.join(FEATURE_DIR, "templates")
FAIL = 0

# Word-boundary match: rejects '_template_version' (Inv 18 / BACKLOG-3).
TEMPLATE_VERSION_RE = re.compile(r"(?<![A-Za-z0-9_])template_version(?![A-Za-z0-9])")

patterns = ["*.md", "*.json", "*.txt"]
for pattern in patterns:
    for tmpl in glob.glob(os.path.join(TEMPLATES_DIR, pattern)):
        if not os.path.isfile(tmpl):
            continue
        content = open(tmpl).read()
        if not TEMPLATE_VERSION_RE.search(content):
            print(f"FAIL: missing 'template_version' marker in: {tmpl}", file=sys.stderr)
            FAIL = 1

if FAIL != 0:
    print("test-templates-have-version: FAIL", file=sys.stderr)
    sys.exit(1)

print("test-templates-have-version: all template files contain 'template_version'.")
