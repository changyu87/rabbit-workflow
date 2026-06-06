#!/usr/bin/env python3
"""Pin the native GitHub Issue Form that enforces feature:/priority: at the
human filing boundary.

`file-item.py` enforces required `feature:` and `priority:` labels for the
loop/CLI (programmatic) filing path, but a raw human web filing bypasses that
script entirely. GitHub Issue Forms are the native enforcement primitive for
the human boundary: a form with REQUIRED `feature` and `priority` dropdowns
forces a human to pick valid values, and a companion GitHub Actions workflow
(the native auto-label primitive) stamps the corresponding `feature:<x>` /
`priority:<y>` labels from the submitted answers. The script path stays
unchanged for bot/loop filings (a justified exception — forms do not cover
programmatic filings).

This guard pins the following so a future edit cannot silently erode the
human-boundary enforcement or let the form and the script drift apart:

  1. The Issue Form source exists under rabbit-issue's ownership and is a
     governed deployed surface (a `publish_file` manifest entry deploys it to
     repo-root `.github/ISSUE_TEMPLATE/`).
  2. The form declares REQUIRED `feature` and `priority` dropdowns with stable
     ids the auto-label workflow keys on.
  3. The `priority` dropdown's option set EXACTLY matches `file-item.py`'s
     `VALID_PRIORITIES` enum — code and form do not drift.
  4. The `feature` dropdown's option set EXACTLY matches the live feature set
     (the directories under `.claude/features/` carrying a `feature.json`) —
     so a form submission can only land a valid `feature:<name>` label, the
     same actionability boundary the script enforces.
  5. The auto-label workflow source exists and is a governed deployed surface
     (a `publish_file` manifest entry deploys it to repo-root
     `.github/workflows/`); it triggers on issue open and derives
     `feature:<x>` / `priority:<y>` labels from the form answers, so a
     submitted form is actionable by the same rule `file-item.py` upholds.

Plus a non-regression check: the programmatic path (file-item.py) keeps its
required `--feature` / `--priority` argparse contract and its
`VALID_PRIORITIES` enum, so the native human path is purely additive.

Static checks; runtime label behaviour of the script is exercised by
test-file-item.py.

Version: 1.0.0
Owner: rabbit-workflow team
Deprecation criterion: when rabbit-issue is retired
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import yaml

FEATURE_DIR = Path(__file__).resolve().parents[1]
FEATURES_ROOT = FEATURE_DIR.parent
FILE_ITEM = FEATURE_DIR / "scripts" / "file-item.py"
FEATURE_JSON = FEATURE_DIR / "feature.json"

# Source paths of the governed surfaces (feature-dir-relative); the manifest
# deploys them to the repo-root .github/ tree.
FORM_SOURCE_REL = "github/ISSUE_TEMPLATE/file-item.yml"
FORM_DEST_REL = ".github/ISSUE_TEMPLATE/file-item.yml"
WORKFLOW_SOURCE_REL = "github/workflows/issue-form-autolabel.yml"
WORKFLOW_DEST_REL = ".github/workflows/issue-form-autolabel.yml"

FORM_PATH = FEATURE_DIR / FORM_SOURCE_REL
WORKFLOW_PATH = FEATURE_DIR / WORKFLOW_SOURCE_REL


def _load_file_item():
    """Import file-item.py without running main()."""
    spec = importlib.util.spec_from_file_location("rabbit_issue_file_item", FILE_ITEM)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def live_feature_names() -> set:
    """The canonical feature set: directories under .claude/features/ that
    carry a feature.json (policy/ has none and is excluded)."""
    names = set()
    for child in FEATURES_ROOT.iterdir():
        if (child / "feature.json").is_file():
            names.add(child.name)
    return names


def _load_form():
    return yaml.safe_load(FORM_PATH.read_text())


def _dropdown(form: dict, field_id: str):
    for el in form.get("body", []):
        if el.get("type") == "dropdown" and el.get("id") == field_id:
            return el
    return None


def _manifest_has(source_rel: str, dest_rel: str) -> bool:
    import json

    data = json.loads(FEATURE_JSON.read_text())
    manifest = data.get("manifest", [])
    return any(
        isinstance(m, dict)
        and m.get("api") == "publish_file"
        and m.get("args", {}).get("source") == source_rel
        and m.get("args", {}).get("dest") == dest_rel
        for m in manifest
    )


def check_form_exists() -> list:
    fails = []
    if not FORM_PATH.is_file():
        fails.append(f"Issue Form source missing: {FORM_PATH}")
    return fails


def check_governed_surfaces() -> list:
    """Both the form and the auto-label workflow are governed deployed
    surfaces: publish_file manifest entries deploy them under repo-root
    .github/."""
    fails = []
    if not _manifest_has(FORM_SOURCE_REL, FORM_DEST_REL):
        fails.append(
            "feature.json manifest must include a publish_file entry deploying "
            f"{FORM_SOURCE_REL!r} -> {FORM_DEST_REL!r}"
        )
    if not _manifest_has(WORKFLOW_SOURCE_REL, WORKFLOW_DEST_REL):
        fails.append(
            "feature.json manifest must include a publish_file entry deploying "
            f"{WORKFLOW_SOURCE_REL!r} -> {WORKFLOW_DEST_REL!r}"
        )
    return fails


def check_required_dropdowns() -> list:
    fails = []
    form = _load_form()
    for field in ("feature", "priority"):
        dd = _dropdown(form, field)
        if dd is None:
            fails.append(f"Issue Form lacks a dropdown with id {field!r}")
            continue
        if dd.get("validations", {}).get("required") is not True:
            fails.append(f"Issue Form {field!r} dropdown is not REQUIRED")
    return fails


def check_priority_options_match_enum() -> list:
    fails = []
    mod = _load_file_item()
    dd = _dropdown(_load_form(), "priority")
    if dd is None:
        return fails  # already reported by check_required_dropdowns
    form_opts = tuple(dd.get("attributes", {}).get("options", []))
    if form_opts != tuple(mod.VALID_PRIORITIES):
        fails.append(
            f"Issue Form priority options {form_opts!r} != file-item.py "
            f"VALID_PRIORITIES {tuple(mod.VALID_PRIORITIES)!r}"
        )
    return fails


def check_feature_options_match_live_set() -> list:
    fails = []
    dd = _dropdown(_load_form(), "feature")
    if dd is None:
        return fails  # already reported by check_required_dropdowns
    form_opts = set(dd.get("attributes", {}).get("options", []))
    live = live_feature_names()
    if form_opts != live:
        missing = live - form_opts
        extra = form_opts - live
        detail = []
        if missing:
            detail.append(f"missing {sorted(missing)}")
        if extra:
            detail.append(f"stale {sorted(extra)}")
        fails.append(
            "Issue Form feature options drifted from the live feature set: "
            + "; ".join(detail)
        )
    return fails


def check_autolabel_workflow() -> list:
    """The companion workflow is the native auto-label primitive: it triggers
    on issue open and stamps feature:<x> / priority:<y> from the form
    answers."""
    fails = []
    if not WORKFLOW_PATH.is_file():
        fails.append(f"auto-label workflow source missing: {WORKFLOW_PATH}")
        return fails
    wf = yaml.safe_load(WORKFLOW_PATH.read_text())
    # `on:` parses to True (the YAML keyword) when bare; accept either key.
    on = wf.get("on", wf.get(True, {}))
    issues = on.get("issues", {}) if isinstance(on, dict) else {}
    types = issues.get("types", []) if isinstance(issues, dict) else []
    if "opened" not in types:
        fails.append("auto-label workflow does not trigger on issues: [opened]")
    # The workflow derives the labels from the form answers. Assert the label
    # prefixes and the form field ids appear in the workflow source so the two
    # surfaces stay wired together.
    src = WORKFLOW_PATH.read_text()
    for needle in ("feature:", "priority:"):
        if needle not in src:
            fails.append(f"auto-label workflow does not reference {needle!r}")
    return fails


def check_programmatic_path_unchanged() -> list:
    """The script path is purely additive: --feature / --priority stay
    required, and VALID_PRIORITIES keeps its closed enum."""
    fails = []
    mod = _load_file_item()
    if tuple(mod.VALID_PRIORITIES) != ("low", "medium", "high", "critical"):
        fails.append(
            f"file-item.py VALID_PRIORITIES changed: {mod.VALID_PRIORITIES!r}"
        )
    src = FILE_ITEM.read_text()
    for needle in (
        '"--feature", required=True',
        '"--priority", required=True, choices=VALID_PRIORITIES',
    ):
        if needle not in src:
            fails.append(
                f"file-item.py programmatic contract changed (missing {needle!r})"
            )
    return fails


def main() -> int:
    all_fails = []
    all_fails.extend(check_form_exists())
    all_fails.extend(check_governed_surfaces())
    # The form-parsing checks only run when the form exists.
    if FORM_PATH.is_file():
        all_fails.extend(check_required_dropdowns())
        all_fails.extend(check_priority_options_match_enum())
        all_fails.extend(check_feature_options_match_live_set())
    all_fails.extend(check_autolabel_workflow())
    all_fails.extend(check_programmatic_path_unchanged())
    if all_fails:
        for msg in all_fails:
            print(f"FAIL: {msg}", file=sys.stderr)
        return 1
    print("PASS test-issue-form-enforcement")
    return 0


if __name__ == "__main__":
    sys.exit(main())
