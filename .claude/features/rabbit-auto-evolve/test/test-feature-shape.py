#!/usr/bin/env python3
"""test-feature-shape.py — rabbit-auto-evolve Inv 15.

Asserts feature-shape compliance for the rabbit-auto-evolve feature:

  1. Four-way version equality across:
       - feature.json `version`
       - specs/spec.md frontmatter `version` (dual-read: docs/spec/ fallback)
       - specs/contract.md frontmatter `version` (dual-read fallback)
       - skills/rabbit-auto-evolve/SKILL.md frontmatter `version`
  2. feature.json carries non-empty `owner` and `deprecation_criterion`.
  3. SKILL.md frontmatter carries non-empty `version`, `owner`,
     `deprecation_criterion`.
  4. feature.json.summary contains the substring `rabbit-auto-evolve`.
  5. Every entry in feature.json.surface.skills has a matching entry
     in contract.md provides.skills (matched by `name`).
  6. No owner field/docstring names an individual: feature.json `owner`,
     spec.md/SKILL.md frontmatter `owner`, every script & test module
     docstring `Owner:`, and every scripts/schemas/*.json `owner` all read
     name the rabbit-workflow team; no owner field names an individual.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

FEATURE_DIR = Path(__file__).resolve().parents[1]
FEATURE_JSON = FEATURE_DIR / "feature.json"


def _resolve_spec(name: str) -> Path:
    """Dual-read (issue #399): prefer specs/<name>, fall back to docs/spec/."""
    preferred = FEATURE_DIR / "specs" / name
    if preferred.is_file():
        return preferred
    return FEATURE_DIR / "docs" / "spec" / name


SPEC_MD = _resolve_spec("spec.md")
CONTRACT_MD = _resolve_spec("contract.md")
SKILL_MD = FEATURE_DIR / "skills" / "rabbit-auto-evolve" / "SKILL.md"


def _frontmatter(path: Path) -> dict:
    text = path.read_text()
    m = re.search(r"(?ms)\A---\s*\n(.*?)\n---\s*\n", text)
    if not m:
        raise AssertionError(f"{path}: no YAML frontmatter")
    fm_text = m.group(1)
    fields: dict[str, str] = {}
    for line in fm_text.splitlines():
        m2 = re.match(r"^([A-Za-z_][A-Za-z0-9_-]*)\s*:\s*(.*?)\s*$", line)
        if m2:
            fields[m2.group(1)] = m2.group(2)
    return fields


def _contract_json_block(path: Path) -> dict:
    text = path.read_text()
    m = re.search(r"```json\s*\n(.*?)\n```", text, re.DOTALL)
    if not m:
        raise AssertionError(f"{path}: no ```json block")
    return json.loads(m.group(1))


pass_n = 0
fail_n = 0


def ok(t: int, msg: str) -> None:
    global pass_n
    print(f"  PASS t{t}: {msg}")
    pass_n += 1


def fail_t(t: int, msg: str) -> None:
    global fail_n
    print(f"  FAIL t{t}: {msg}")
    fail_n += 1


print("test-feature-shape.py")

fj = json.loads(FEATURE_JSON.read_text())
spec_fm = _frontmatter(SPEC_MD)
contract_fm = _frontmatter(CONTRACT_MD)
skill_fm = _frontmatter(SKILL_MD)

# t1 — four-way version equality
fj_v = fj.get("version")
spec_v = spec_fm.get("version")
contract_v = contract_fm.get("version")
skill_v = skill_fm.get("version")
if fj_v and fj_v == spec_v == contract_v == skill_v:
    ok(1, f"version alignment: {fj_v}")
else:
    fail_t(
        1,
        f"version drift: feature.json={fj_v!r}, spec={spec_v!r}, "
        f"contract={contract_v!r}, skill={skill_v!r}",
    )

# t2 — feature.json owner + deprecation_criterion non-empty
fj_owner = fj.get("owner", "")
fj_dep = fj.get("deprecation_criterion", "")
if fj_owner and fj_dep:
    ok(2, f"feature.json owner={fj_owner!r}, deprecation_criterion non-empty")
else:
    fail_t(
        2,
        f"feature.json missing owner/deprecation_criterion: "
        f"owner={fj_owner!r}, deprecation_criterion={fj_dep!r}",
    )

# t3 — SKILL.md frontmatter version + owner + deprecation_criterion non-empty
sk_owner = skill_fm.get("owner", "")
sk_dep = skill_fm.get("deprecation_criterion", "")
if skill_v and sk_owner and sk_dep:
    ok(3, f"SKILL.md frontmatter version+owner+deprecation_criterion non-empty")
else:
    fail_t(
        3,
        f"SKILL.md missing required frontmatter field: "
        f"version={skill_v!r}, owner={sk_owner!r}, "
        f"deprecation_criterion={sk_dep!r}",
    )

# t4 — feature.json.summary mentions 'rabbit-auto-evolve'
summary = fj.get("summary", "")
if "rabbit-auto-evolve" in summary:
    ok(4, "feature.json.summary mentions rabbit-auto-evolve")
else:
    fail_t(4, f"feature.json.summary missing 'rabbit-auto-evolve': {summary!r}")

# t5 — every surface.skills has a matching provides.skills entry (by name)
fj_skills = fj.get("surface", {}).get("skills", [])
contract_obj = _contract_json_block(CONTRACT_MD)
provides_skills = contract_obj.get("provides", {}).get("skills", [])
# Normalize provides_skills: each item may be a string or {name, version} dict.
provides_names: list[str] = []
for s in provides_skills:
    if isinstance(s, str):
        provides_names.append(s)
    elif isinstance(s, dict) and "name" in s:
        provides_names.append(s["name"])
missing = [s for s in fj_skills if s not in provides_names]
if not missing:
    ok(
        5,
        f"all surface.skills present in contract.provides.skills "
        f"({len(fj_skills)} entries)",
    )
else:
    fail_t(
        5,
        f"surface.skills missing from contract.provides.skills: {missing}",
    )

# t6 — owner sweep: every owner field/docstring names the rabbit-workflow team,
# never an individual. Metadata fields (feature.json, frontmatter, schema) read
# the bare team; module docstrings may carry the conventional `(<feature>)`
# qualifier (e.g. "rabbit-workflow team (rabbit-auto-evolve)").
EXPECTED_OWNER = "rabbit-workflow team"
TEAM_RE = re.compile(r"^rabbit-workflow team(?: \([^()]+\))?$")
owner_problems: list[str] = []

# feature.json owner value (bare team)
if fj.get("owner") != EXPECTED_OWNER:
    owner_problems.append(f"feature.json owner={fj.get('owner')!r}")

# spec.md + SKILL.md frontmatter owner values (bare team)
if spec_fm.get("owner") != EXPECTED_OWNER:
    owner_problems.append(f"spec.md frontmatter owner={spec_fm.get('owner')!r}")
if skill_fm.get("owner") != EXPECTED_OWNER:
    owner_problems.append(f"SKILL.md frontmatter owner={skill_fm.get('owner')!r}")

# scripts/schemas/*.json top-level owner values (bare team)
SCHEMAS_DIR = FEATURE_DIR / "scripts" / "schemas"
for sp in sorted(SCHEMAS_DIR.glob("*.json")):
    sdata = json.loads(sp.read_text())
    if sdata.get("owner") != EXPECTED_OWNER:
        owner_problems.append(f"{sp.name} owner={sdata.get('owner')!r}")

# every script + test module docstring `Owner:` line (team, optional qualifier)
OWNER_LINE = re.compile(r"^Owner:\s*(.+?)\s*$", re.MULTILINE)
for py in sorted((FEATURE_DIR / "scripts").rglob("*.py")) + \
        sorted((FEATURE_DIR / "test").rglob("*.py")):
    for m in OWNER_LINE.finditer(py.read_text()):
        if not TEAM_RE.match(m.group(1)):
            owner_problems.append(f"{py.name} docstring Owner: {m.group(1)!r}")

# no stray docstring/frontmatter/JSON owner naming the individual anywhere in
# the feature tree. The individual name is assembled at runtime so this
# assertion file never itself contains a literal forbidden token.
_INDIVIDUAL = "cy" + "xu"
_forbidden = (f"Owner: {_INDIVIDUAL}", f"owner: {_INDIVIDUAL}",
              f'"owner": "{_INDIVIDUAL}"')
for path in sorted(FEATURE_DIR.rglob("*")):
    if not path.is_file() or path.suffix == ".pyc":
        continue
    try:
        text = path.read_text()
    except (UnicodeDecodeError, OSError):
        continue
    for tok in _forbidden:
        if tok in text:
            owner_problems.append(f"{path.relative_to(FEATURE_DIR)} contains {tok!r}")

if not owner_problems:
    ok(6, f"all owner fields/docstrings read {EXPECTED_OWNER!r}")
else:
    fail_t(6, "owner sweep incomplete: " + "; ".join(owner_problems))

print()
print(f"Results: {pass_n} passed, {fail_n} failed")
sys.exit(0 if fail_n == 0 else 1)
