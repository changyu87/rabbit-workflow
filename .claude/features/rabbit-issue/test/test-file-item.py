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
    for lbl in ("bug", "feature:rabbit-cage", "priority:high"):
        assert lbl in log
    # rabbit-managed application is retired (coexistence step 3 of #753, #760):
    # the label MUST NOT be applied to newly filed issues.
    assert "rabbit-managed" not in _created_labels(log)


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
    # The three base labels are present and unchanged; filed-by is additive.
    # rabbit-managed application is retired (step 3 of #753, #760) — it is
    # NOT in the applied set.
    assert labels == {
        "bug",
        "feature:rabbit-cage",
        "priority:high",
        "filed-by:rabbit",
    }


def test_omitted_filed_by_yields_base_labels_only(gh_shim, fake_repo):
    """Human filing carries exactly the three base labels, no filed-by.

    rabbit-managed is no longer applied (step 3 of #753, #760).
    """
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
        "feature:rabbit-cage",
        "priority:high",
    }
    assert "rabbit-managed" not in labels


def test_housekeeping_flag_adds_housekeeping_label(gh_shim, fake_repo):
    r = _run(
        "--type", "bug",
        "--feature", "rabbit-cage",
        "--title", "t",
        "--priority", "medium",
        "--description", "d",
        "--housekeeping",
    )
    assert r.returncode == 0, r.stderr
    labels = _created_labels(gh_shim.read_text())
    assert "housekeeping" in labels


def test_housekeeping_omitted_stamps_no_housekeeping_label(gh_shim, fake_repo):
    r = _run(
        "--type", "bug",
        "--feature", "rabbit-cage",
        "--title", "t",
        "--priority", "medium",
        "--description", "d",
    )
    assert r.returncode == 0, r.stderr
    labels = _created_labels(gh_shim.read_text())
    assert "housekeeping" not in labels


def test_housekeeping_is_additive_other_labels_unchanged(gh_shim, fake_repo):
    r = _run(
        "--type", "bug",
        "--feature", "rabbit-cage",
        "--title", "t",
        "--priority", "high",
        "--description", "d",
        "--housekeeping",
    )
    assert r.returncode == 0, r.stderr
    labels = _created_labels(gh_shim.read_text())
    # The three base labels are present and unchanged; housekeeping is additive.
    assert labels == {
        "bug",
        "feature:rabbit-cage",
        "priority:high",
        "housekeeping",
    }


def test_housekeeping_composes_with_filed_by(gh_shim, fake_repo):
    """A housekeeping sub-issue filed by a non-human filer carries both."""
    r = _run(
        "--type", "bug",
        "--feature", "rabbit-cage",
        "--title", "t",
        "--priority", "medium",
        "--description", "d",
        "--filed-by", "rabbit",
        "--housekeeping",
    )
    assert r.returncode == 0, r.stderr
    labels = _created_labels(gh_shim.read_text())
    assert "housekeeping" in labels
    assert "filed-by:rabbit" in labels


def test_parent_links_child_as_sub_issue(gh_shim, fake_repo, monkeypatch):
    """--parent creates the child AND establishes the GitHub sub-issue link.

    The shim returns a child database id (424242) distinct from the issue
    number (9001); the POST body MUST carry the resolved id, not the number.
    """
    monkeypatch.setenv("GH_SHIM_CHILD_ID", "424242")
    monkeypatch.setenv("GH_SHIM_CHILD_NUMBER", "9001")
    r = _run(
        "--type", "enhancement",
        "--feature", "rabbit-issue",
        "--title", "child task",
        "--priority", "medium",
        "--description", "d",
        "--parent", "7000",
    )
    assert r.returncode == 0, r.stderr
    out = json.loads(r.stdout)
    assert out["number"] == 9001
    # On a successful link the optional `parent` field is emitted.
    assert out["parent"] == 7000
    log = gh_shim.read_text()
    api_lines = [l for l in log.strip().split("\n") if l.startswith("api ")]
    # A GET resolves the child id, then a POST establishes the link on the
    # PARENT's sub_issues collection carrying the resolved id (not the number).
    assert any("issues/9001" in l and "sub_issues" not in l for l in api_lines), api_lines
    post = [l for l in api_lines if "issues/7000/sub_issues" in l]
    assert post, api_lines
    assert "424242" in post[0], post[0]


def test_parent_already_linked_is_idempotent(gh_shim, fake_repo, monkeypatch):
    """Re-linking an already-linked child does not error (idempotent)."""
    monkeypatch.setenv("GH_SHIM_CHILD_ID", "424242")
    monkeypatch.setenv("GH_SHIM_SUBISSUE_POST_EXIT", "1")
    monkeypatch.setenv(
        "GH_SHIM_SUBISSUE_POST_STDERR", "gh: sub-issue already exists (HTTP 422)"
    )
    r = _run(
        "--type", "enhancement",
        "--feature", "rabbit-issue",
        "--title", "child task",
        "--priority", "medium",
        "--description", "d",
        "--parent", "7000",
    )
    assert r.returncode == 0, r.stderr
    out = json.loads(r.stdout)
    assert out["number"] == 9001


def test_no_parent_is_byte_identical_no_extra_api(gh_shim, fake_repo):
    """Without --parent: same {number,url,type} JSON, no `parent`, no api calls."""
    r = _run(
        "--type", "enhancement",
        "--feature", "rabbit-issue",
        "--title", "standalone task",
        "--priority", "medium",
        "--description", "d",
    )
    assert r.returncode == 0, r.stderr
    out = json.loads(r.stdout)
    assert out == {
        "number": 9001,
        "url": "https://github.com/test/repo/issues/9001",
        "type": "enhancement",
    }
    # No link path means NO `gh api` calls at all.
    log = gh_shim.read_text()
    assert not any(l.startswith("api ") for l in log.strip().split("\n")), log
    # And no `parent` field leaks onto the no-parent path.
    assert "parent" not in out


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
