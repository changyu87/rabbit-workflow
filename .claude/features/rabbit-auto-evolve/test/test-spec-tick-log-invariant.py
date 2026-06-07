#!/usr/bin/env python3
"""test-spec-tick-log-invariant.py — rabbit-auto-evolve Inv 37 (issue #404).

Inv 37 introduces the FULL per-tick observability log (`log-tick.py` →
`.rabbit/auto-evolve.log`) with on/off enable, three verbosity levels, a
<2KB per-line cap, and 5MB/3-file rotation, plus a new
`/rabbit-auto-evolve log on|off|level|path|tail|clear` subcommand group.

This e2e regression asserts:

  1. The spec carries the Inv 37 text (issue #404 cross-ref, the
     `log-tick.py` / `log-path.py` scripts, `.rabbit/auto-evolve.log`, the
     three verbosity levels, the 5 MB rotation, and the OWN-config storage).
  2. Inv 37 explicitly establishes COEXISTENCE with the minimal Inv 36
     `tick-log.py` (different file, different purpose) and states #404 does
     NOT modify `tick-log.py` / Inv 36.
  3. BOTH SKILL.md copies (source + deployed) document the
     `log on|off|level|path|tail|clear` subcommand group.
  4. All four versioned artifacts (feature.json, spec.md, contract.md,
     SKILL.md frontmatter) are bumped in lockstep to the SAME version
     (Inv 15).
"""

import json
import re
import sys
from pathlib import Path

FEATURE_DIR = Path(__file__).resolve().parents[1]


def _resolve_doc(name):
    """Dual-read (issue #399): prefer the flat docs/<name> layout, fall back
    to specs/<name>, then legacy docs/spec/<name>."""
    for candidate in (
        FEATURE_DIR / "docs" / name,
        FEATURE_DIR / "specs" / name,
        FEATURE_DIR / "docs" / "spec" / name,
    ):
        if candidate.is_file():
            return candidate
    return FEATURE_DIR / "docs" / name


SPEC_MD = _resolve_doc("spec.md")
CONTRACT_MD = _resolve_doc("contract.md")
FEATURE_JSON = FEATURE_DIR / "feature.json"

SOURCE_SKILL = FEATURE_DIR / "skills" / "rabbit-auto-evolve" / "SKILL.md"
REPO_ROOT = FEATURE_DIR.parents[2]
DEPLOYED_SKILL = REPO_ROOT / ".claude" / "skills" / "rabbit-auto-evolve" / "SKILL.md"

FAIL = 0


def fail(msg):
    global FAIL
    print(f"FAIL: {msg}", file=sys.stderr)
    FAIL = 1


def ok(msg):
    print(f"PASS: {msg}")


def norm(text):
    return re.sub(r"\s+", " ", text)


# --- (1) Spec carries Inv 37 ------------------------------------------
spec_raw = SPEC_MD.read_text()
spec = norm(spec_raw)
spec_low = spec.lower()

SPEC_REQUIRED = [
    "log-tick.py",
    "log-path.py",
    "auto-evolve.log",
    "quiet",
    "normal",
    "debug",
    "5 mb",
    "2 kb",
]
missing = [s for s in SPEC_REQUIRED if s.lower() not in spec_low]
if missing:
    fail(f"spec.md missing Inv 37 phrase(s): {missing!r}")
else:
    ok("spec.md carries the per-tick observability-log invariant (Inv 37)")

# The enable flag + level live in rabbit-auto-evolve's OWN config, NOT
# rabbit-cage's configuration array.
if "own config" in spec_low:
    ok("spec.md states the config lives in rabbit-auto-evolve's OWN config")
else:
    fail("spec.md does not state the OWN-config storage requirement")

# --- (2) Coexistence with Inv 36 tick-log.py --------------------------
if "tick-log.py" in spec_low and "distinct" in spec_low:
    ok("spec.md establishes coexistence with the minimal Inv 36 tick-log.py")
else:
    fail("spec.md does not establish Inv 36/37 coexistence (tick-log.py)")
if "does not modify" in spec_low or "not modify" in spec_low:
    ok("spec.md states #404 does NOT modify tick-log.py / Inv 36")
else:
    fail("spec.md does not state #404 leaves tick-log.py / Inv 36 untouched")


# --- (2b) Inv 50: observability-log attribution (issue #627) -----------
# tick/session_id must carry real, deterministic values derived from the
# running marker; the marker source is injectable for tests.
ATTR_REQUIRED = [
    "running marker",
    "rabbit_auto_evolve_running_marker",
    "session_id",
]
attr_missing = [s for s in ATTR_REQUIRED if s.lower() not in spec_low]
if attr_missing:
    fail(f"spec.md missing Inv 50 attribution phrase(s): {attr_missing!r}")
else:
    ok("spec.md carries the observability-log attribution invariant (Inv 50)")
# The no-stub guarantee must be explicit.
if "never stub" in spec_low or "never stubs" in spec_low:
    ok("spec.md states tick/session_id are never stubs (Inv 50)")
else:
    fail("spec.md does not state the no-stub guarantee for tick/session_id")


# --- (3) BOTH SKILL.md copies document the log subcommand group -------
LOG_SUBCMDS = ["log on", "log off", "log level", "log path", "log tail",
               "log clear"]


def check_skill_log(path, label):
    if not path.is_file():
        fail(f"{label} SKILL.md not found at {path}")
        return
    flat_low = norm(path.read_text()).lower()
    missing = [s for s in LOG_SUBCMDS if s not in flat_low]
    if not missing:
        ok(f"{label}: SKILL.md documents the log subcommand group "
           f"(on/off/level/path/tail/clear)")
    else:
        fail(f"{label}: SKILL.md missing log subcommand(s): {missing!r}")


check_skill_log(SOURCE_SKILL, "source")
check_skill_log(DEPLOYED_SKILL, "deployed")


# --- (4) Lockstep version across the four versioned artifacts ---------
def frontmatter_version(path):
    text = path.read_text()
    m = re.search(r"^version:\s*([0-9]+\.[0-9]+\.[0-9]+)\s*$",
                  text, re.MULTILINE)
    return m.group(1) if m else None


fj_version = json.loads(FEATURE_JSON.read_text()).get("version")
spec_version = frontmatter_version(SPEC_MD)
contract_version = frontmatter_version(CONTRACT_MD)
skill_version = frontmatter_version(SOURCE_SKILL)

versions = {
    "feature.json": fj_version,
    "spec.md": spec_version,
    "contract.md": contract_version,
    "SKILL.md": skill_version,
}
if None in versions.values():
    fail(f"could not parse version from all artifacts: {versions!r}")
elif len(set(versions.values())) == 1:
    ok(f"all four versioned artifacts in lockstep at "
       f"{next(iter(versions.values()))} (Inv 15)")
else:
    fail(f"version drift across artifacts: {versions!r}")

sys.exit(FAIL)
