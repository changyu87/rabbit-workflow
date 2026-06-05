#!/usr/bin/env python3
"""test-contract-reads-accurate.py — issue #908 (contract reads.files accuracy)

End-to-end check that rabbit-decompose's docs/contract.md `reads.files` block
reflects what the feature's scripts ACTUALLY read, and that the mode-detection
cross-feature dependency is represented as an INVOKE (not a stale file read).

Since #890/#901/#906, handoff-scaffold.py resolves plugin-vs-standalone mode by
REUSING rabbit-meta's canonical detect_mode (a structural check on the
rabbit-root), NOT by reading a hard-coded `<repo>/.rabbit/.runtime/mode` marker
path. The old `reads.files` entry `.rabbit/.runtime/mode` is therefore stale.

This E2E test asserts the corrected contract shape against the live on-disk
artifacts:

  - The contract JSON parses and `reads.files` does NOT list
    `.rabbit/.runtime/mode` (the dead read is removed).
  - No rabbit-decompose script genuinely reads `.rabbit/.runtime/mode` (the
    source of truth that justifies removal). A docstring mention that the
    script does NOT read that path is allowed; an open()/read of that literal
    path is not.
  - The mode-detection dependency is represented under `invokes.scripts` as
    rabbit-meta/lib/mode_detection.py (the real cross-feature dependency).
  - validate_feature reports no errors for the feature (contract meta-checks).

Run non-interactively. Exits non-zero on failure.

Version: 0.1.0
Owner: rabbit-workflow team
Deprecation criterion: when a cross-feature harness enforces reads/invokes
accuracy against every feature's scripts, making this per-feature assertion
redundant.
"""
import json
import os
import re
import sys

FEATURE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DOCS_DIR = os.path.join(FEATURE_DIR, "docs")
SCRIPTS_DIR = os.path.join(FEATURE_DIR, "scripts")

_CONTRACT_LIB = os.path.abspath(
    os.path.join(FEATURE_DIR, "..", "contract", "lib")
)
if _CONTRACT_LIB not in sys.path:
    sys.path.insert(0, _CONTRACT_LIB)
from checks import validate_feature  # noqa: E402

STALE_PATH = ".rabbit/.runtime/mode"


def fail(msg):
    print(f"FAIL: {msg}", file=sys.stderr)
    sys.exit(1)


def load_contract_json(path):
    with open(path, encoding="utf-8") as f:
        text = f.read()
    m = re.search(r"```json\s*(\{.*?\})\s*```", text, re.DOTALL)
    if not m:
        fail(f"no JSON block found in {path}")
    try:
        return json.loads(m.group(1))
    except json.JSONDecodeError as e:
        fail(f"contract JSON does not parse: {e}")


contract = load_contract_json(os.path.join(DOCS_DIR, "contract.md"))

# reads.files must NOT carry the stale mode-marker read.
reads_files = contract.get("reads", {}).get("files", [])
if STALE_PATH in reads_files:
    fail(
        f"docs/contract.md reads.files still lists the stale '{STALE_PATH}' "
        f"read; handoff-scaffold.py resolves mode via detect_mode (a "
        f"structural check), not by reading that path. Remove it."
    )

# Source of truth: no script genuinely reads the stale path. A docstring that
# says the script does NOT read it is fine; an actual file read is not.
read_call = re.compile(
    r"(?:open|read_text|Path)\s*\([^)]*" + re.escape(STALE_PATH)
)
for fname in os.listdir(SCRIPTS_DIR):
    if not fname.endswith(".py"):
        continue
    with open(os.path.join(SCRIPTS_DIR, fname), encoding="utf-8") as f:
        body = f.read()
    if read_call.search(body):
        fail(
            f"scripts/{fname} appears to genuinely read '{STALE_PATH}'; the "
            f"contract removal would be inaccurate."
        )

# The real cross-feature dependency is the detect_mode INVOKE.
invoke_scripts = contract.get("invokes", {}).get("scripts", [])
paths = [s.get("path", "") for s in invoke_scripts]
if not any("rabbit-meta/lib/mode_detection.py" in p for p in paths):
    fail(
        "docs/contract.md invokes.scripts must declare "
        "rabbit-meta/lib/mode_detection.py (the detect_mode dependency that "
        "replaced the stale mode-marker read)."
    )

# Contract meta-validation stays green for the feature.
result = validate_feature(FEATURE_DIR)
if not result.passed:
    fail(f"validate_feature reported errors: {result.messages}")

print("All checks passed.")
