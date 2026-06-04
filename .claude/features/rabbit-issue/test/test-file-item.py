"""E2E tests for scripts/file-item.py.

Driven via subprocess so PATH-shimmed `gh` is the same one the script sees.
"""
import json
import os
import subprocess
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
FILE_ITEM = SCRIPTS / "file-item.py"


def _run(*args, env=None):
    return subprocess.run(
        [sys.executable, str(FILE_ITEM), *args],
        capture_output=True, text=True, env=env or os.environ.copy(),
    )


def test_file_bug_creates_gh_issue(gh_shim, fake_repo):
    r = _run(
        "--type", "bug",
        "--feature", "rabbit-cage",
        "--title", "login button broken on Safari",
        "--priority", "high",
        "--description", "steps: ...",
    )
    assert r.returncode == 0, r.stderr
    out = json.loads(r.stdout)
    assert out["number"] == 9001
    assert out["type"] == "bug"
    assert out["url"] == "https://github.com/test/repo/issues/9001"
    log = gh_shim.read_text()
    assert "issue create" in log
    for lbl in ("bug", "rabbit-managed", "feature:rabbit-cage", "priority:high"):
        assert lbl in log


def test_file_enhancement_uses_enhancement_label(gh_shim, fake_repo):
    r = _run(
        "--type", "enhancement",
        "--feature", "x",
        "--title", "t",
        "--priority", "low",
        "--description", "d",
    )
    assert r.returncode == 0, r.stderr
    assert "enhancement" in gh_shim.read_text()


def test_rejects_invalid_type(gh_shim, fake_repo):
    r = _run(
        "--type", "feature",
        "--feature", "x",
        "--title", "t",
        "--priority", "low",
        "--description", "d",
    )
    assert r.returncode != 0
    assert "type" in r.stderr.lower() or "invalid" in r.stderr.lower()


def test_rejects_invalid_priority(gh_shim, fake_repo):
    r = _run(
        "--type", "bug",
        "--feature", "x",
        "--title", "t",
        "--priority", "urgent",
        "--description", "d",
    )
    assert r.returncode != 0


def test_ensure_labels_called_before_create(gh_shim, fake_repo):
    r = _run(
        "--type", "bug",
        "--feature", "x",
        "--title", "t",
        "--priority", "low",
        "--description", "d",
    )
    assert r.returncode == 0, r.stderr
    log_lines = gh_shim.read_text().strip().split("\n")
    label_idx = next(i for i, l in enumerate(log_lines) if l.startswith("label create"))
    issue_idx = next(i for i, l in enumerate(log_lines) if l.startswith("issue create"))
    assert label_idx < issue_idx


def _created_labels(log_text):
    """Extract the comma-joined label set passed to `gh issue create`.

    The shim logs each gh invocation as a space-joined arg line; the labels
    follow the `--label` token as a single comma-joined argument.
    """
    for line in log_text.strip().split("\n"):
        if not line.startswith("issue create"):
            continue
        toks = line.split()
        idx = toks.index("--label")
        return set(toks[idx + 1].split(","))
    raise AssertionError("no `issue create` line with --label in gh log")


def test_filed_by_rabbit_adds_filed_by_rabbit_label(gh_shim, fake_repo):
    r = _run(
        "--type", "bug",
        "--feature", "rabbit-cage",
        "--title", "t",
        "--priority", "high",
        "--description", "d",
        "--filed-by", "rabbit",
    )
    assert r.returncode == 0, r.stderr
    labels = _created_labels(gh_shim.read_text())
    assert "filed-by:rabbit" in labels
    assert "filed-by:human" not in labels


def test_filed_by_autonomous_evolve_adds_matching_label(gh_shim, fake_repo):
    r = _run(
        "--type", "bug",
        "--feature", "rabbit-cage",
        "--title", "t",
        "--priority", "high",
        "--description", "d",
        "--filed-by", "autonomous-evolve",
    )
    assert r.returncode == 0, r.stderr
    labels = _created_labels(gh_shim.read_text())
    assert "filed-by:autonomous-evolve" in labels


def test_filed_by_omitted_stamps_no_filed_by_label(gh_shim, fake_repo):
    """Human is the untagged default: omitting --filed-by emits NO label."""
    r = _run(
        "--type", "bug",
        "--feature", "rabbit-cage",
        "--title", "t",
        "--priority", "high",
        "--description", "d",
    )
    assert r.returncode == 0, r.stderr
    labels = _created_labels(gh_shim.read_text())
    assert not any(lbl.startswith("filed-by:") for lbl in labels), labels


def test_filed_by_rejects_legacy_loop(gh_shim, fake_repo):
    r = _run(
        "--type", "bug",
        "--feature", "rabbit-cage",
        "--title", "t",
        "--priority", "high",
        "--description", "d",
        "--filed-by", "loop",
    )
    assert r.returncode != 0
    assert "filed-by" in (r.stderr + r.stdout).lower()
    assert "issue create" not in gh_shim.read_text()


def test_filed_by_rejects_explicit_human(gh_shim, fake_repo):
    """Human provenance is expressed by OMISSION, not an explicit value."""
    r = _run(
        "--type", "bug",
        "--feature", "rabbit-cage",
        "--title", "t",
        "--priority", "high",
        "--description", "d",
        "--filed-by", "human",
    )
    assert r.returncode != 0
    assert "issue create" not in gh_shim.read_text()


def test_filed_by_rejects_polluted_space_bearing_value(gh_shim, fake_repo):
    r = _run(
        "--type", "bug",
        "--feature", "rabbit-cage",
        "--title", "t",
        "--priority", "high",
        "--description", "d",
        "--filed-by", "tdd-subagent (#685)",
    )
    assert r.returncode != 0
    assert "issue create" not in gh_shim.read_text()


def test_filed_by_rabbit_is_additive_other_labels_unchanged(gh_shim, fake_repo):
    r = _run(
        "--type", "bug",
        "--feature", "rabbit-cage",
        "--title", "t",
        "--priority", "high",
        "--description", "d",
        "--filed-by", "rabbit",
    )
    assert r.returncode == 0, r.stderr
    labels = _created_labels(gh_shim.read_text())
    # The four base labels are present and unchanged; filed-by is additive.
    # rabbit-managed is still applied here (coexistence: removal is step 3).
    assert labels == {
        "bug",
        "rabbit-managed",
        "feature:rabbit-cage",
        "priority:high",
        "filed-by:rabbit",
    }


def test_omitted_filed_by_yields_base_labels_only(gh_shim, fake_repo):
    """Human filing carries exactly the four base labels, no filed-by."""
    r = _run(
        "--type", "bug",
        "--feature", "rabbit-cage",
        "--title", "t",
        "--priority", "high",
        "--description", "d",
    )
    assert r.returncode == 0, r.stderr
    labels = _created_labels(gh_shim.read_text())
    assert labels == {
        "bug",
        "rabbit-managed",
        "feature:rabbit-cage",
        "priority:high",
    }


def test_requires_auth(gh_shim, fake_repo, monkeypatch):
    env = os.environ.copy()
    env["GH_SHIM_AUTH_EXIT"] = "1"
    r = _run(
        "--type", "bug",
        "--feature", "x",
        "--title", "t",
        "--priority", "low",
        "--description", "d",
        env=env,
    )
    assert r.returncode != 0
    # auth failure must short-circuit before any issue create
    assert "issue create" not in gh_shim.read_text()
