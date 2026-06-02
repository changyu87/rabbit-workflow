#!/usr/bin/env python3
"""Tests for rabbit-file feature metadata (BUG-34).

Covers two spec invariants:
  - feature.json `surface.skills` MUST be a non-empty array containing
    the entry `rabbit-file`.
  - docs/spec/contract.md MUST exist with YAML frontmatter carrying
    {feature, version, template_version, owner, deprecation_criterion}
    and a top-level JSON block with provides/reads/invokes/manages/never
    keys.
"""
import json
import re
import sys
from pathlib import Path

FEATURE_DIR = Path(__file__).parent.parent
FEATURE_JSON = FEATURE_DIR / "feature.json"
CONTRACT_MD = FEATURE_DIR / "docs" / "spec" / "contract.md"

pass_ = 0
fail = 0


def assert_pass(msg):
    global pass_
    print(f"PASS: {msg}")
    pass_ += 1


def assert_fail(msg, reason):
    global fail
    print(f"FAIL: {msg} — {reason}")
    fail += 1


# --- feature.json surface.skills ---
if not FEATURE_JSON.is_file():
    assert_fail("feature.json exists", f"missing at {FEATURE_JSON}")
else:
    try:
        fj = json.loads(FEATURE_JSON.read_text())
    except json.JSONDecodeError as e:
        assert_fail("feature.json parses as JSON", str(e))
        fj = None

    if fj is not None:
        skills = fj.get("surface", {}).get("skills")
        if not isinstance(skills, list):
            assert_fail(
                "feature.json surface.skills is a list (BUG-34)",
                f"got {type(skills).__name__}",
            )
        elif len(skills) == 0:
            assert_fail(
                "feature.json surface.skills is non-empty (BUG-34)",
                "empty list while SKILL.md exists",
            )
        elif "rabbit-file" not in skills:
            assert_fail(
                "feature.json surface.skills contains 'rabbit-file' (BUG-34)",
                f"got {skills!r}",
            )
        else:
            assert_pass(
                "feature.json surface.skills is non-empty and contains 'rabbit-file' (BUG-34)"
            )

# --- contract.md ---
if not CONTRACT_MD.is_file():
    assert_fail(
        "docs/spec/contract.md exists (BUG-34)",
        f"missing at {CONTRACT_MD}",
    )
else:
    assert_pass("docs/spec/contract.md exists (BUG-34)")
    txt = CONTRACT_MD.read_text()

    # Frontmatter parse
    fm_match = re.match(r"^---\n(.*?)\n---\n", txt, re.DOTALL)
    if not fm_match:
        assert_fail(
            "contract.md has YAML frontmatter (BUG-34)",
            "no leading --- ... --- block found",
        )
    else:
        fm = fm_match.group(1)
        required_fm_keys = ["feature", "version", "template_version", "owner", "deprecation_criterion"]
        missing = [k for k in required_fm_keys if not re.search(rf"^{k}:", fm, re.MULTILINE)]
        if missing:
            assert_fail(
                "contract.md frontmatter has all required keys (BUG-34)",
                f"missing keys: {missing}",
            )
        else:
            assert_pass(
                "contract.md frontmatter has feature/version/template_version/owner/deprecation_criterion (BUG-34)"
            )

    # JSON block
    json_match = re.search(r"```json\n(.*?)\n```", txt, re.DOTALL)
    if not json_match:
        assert_fail(
            "contract.md has a ```json``` block (BUG-34)",
            "no fenced JSON code block found",
        )
    else:
        try:
            data = json.loads(json_match.group(1))
        except json.JSONDecodeError as e:
            assert_fail("contract.md JSON block parses (BUG-34)", str(e))
            data = None

        if data is not None:
            required_top_keys = ["provides", "reads", "invokes", "manages", "never"]
            missing = [k for k in required_top_keys if k not in data]
            if missing:
                assert_fail(
                    "contract.md JSON block has provides/reads/invokes/manages/never (BUG-34)",
                    f"missing keys: {missing}",
                )
            else:
                assert_pass(
                    "contract.md JSON block has provides/reads/invokes/manages/never (BUG-34)"
                )

print()
print(f"Results: {pass_} passed, {fail} failed")
sys.exit(0 if fail == 0 else 1)
