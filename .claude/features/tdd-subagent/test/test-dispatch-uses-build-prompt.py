#!/usr/bin/env python3
"""Inv 45 — dispatch-tdd-subagent.py uses build-prompt.py + template.

Static-analysis checks against the dispatch script source:
  - no inline f-string assembly (`prompt = f\"\"\"`)
  - references build-prompt.py
  - _policy_block helper removed
  - policy-block.py subprocess target removed
  - no hardcoded ════ banner string (banners live in the template)
  - subprocess shape includes --callable-id tdd-subagent and --slot
"""
import os
import re
import sys

from _helpers import FEATURE_DIR, report

DISPATCH_PY = os.path.join(FEATURE_DIR, "scripts", "dispatch-tdd-subagent.py")

with open(DISPATCH_PY) as f:
    src = f.read()

passed = failed = 0


def ok(msg):
    global passed
    passed += 1
    print(f"  ok   {msg}")


def ko(msg):
    global failed
    failed += 1
    print(f"  FAIL {msg}")


# t-no-f-string-prompt: no `prompt = f"""` inline assembly remains.
if re.search(r'^\s*prompt\s*=\s*f"""', src, re.MULTILINE):
    ko("t-no-f-string-prompt: inline f-string prompt assembly still present")
else:
    ok("t-no-f-string-prompt: inline f-string prompt assembly removed")

# t-references-build-prompt: dispatcher mentions build-prompt.py.
if "build-prompt.py" in src:
    ok("t-references-build-prompt: dispatcher references build-prompt.py")
else:
    ko("t-references-build-prompt: dispatcher does not reference build-prompt.py")

# t-no-policy-block-helper: _policy_block helper is gone.
if "_policy_block" in src:
    ko("t-no-policy-block-helper: _policy_block reference still present")
else:
    ok("t-no-policy-block-helper: _policy_block helper removed")

# t-no-policy-block-py-call: policy-block.py subprocess target is gone.
if "policy-block.py" in src:
    ko("t-no-policy-block-py-call: policy-block.py reference still present")
else:
    ok("t-no-policy-block-py-call: policy-block.py subprocess target removed")

# t-no-section-banners-inline: no hardcoded ═ banner string (16+ in a row).
if re.search("═{16,}", src):
    ko("t-no-section-banners-inline: hardcoded ═ banner present in dispatcher")
else:
    ok("t-no-section-banners-inline: no hardcoded ═ banner in dispatcher")

# t-subprocess-call-shape: dispatcher invokes build-prompt.py with
# --callable-id tdd-subagent and --slot flag(s).
required = ["build-prompt.py", "--callable-id", "tdd-subagent", "--slot"]
missing = [tok for tok in required if tok not in src]
if not missing:
    ok("t-subprocess-call-shape: dispatcher invokes build-prompt.py with id and --slot")
else:
    ko(f"t-subprocess-call-shape: missing tokens in dispatcher: {missing}")

report(passed, failed)
