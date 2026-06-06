"""Tests for scripts/_gh.link_sub_issue.

Covers the GitHub-native sub-issue linkage helper added for #933:
  - the POST body carries the resolved CHILD database id (NOT the issue
    number) — the API footgun;
  - the GET resolves the child id via repos/{slug}/issues/{child};
  - an already-linked child degrades gracefully (no raise) — idempotence.

Driven directly against the helper module with the gh CLI shimmed onto PATH.
"""
import importlib
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))


def _fresh_gh():
    """Drop cached _gh so per-test PATH/env changes take effect."""
    sys.modules.pop("_gh", None)
    import _gh  # noqa: F401
    return importlib.import_module("_gh")


def _api_lines(log_text):
    return [l for l in log_text.strip().split("\n") if l.startswith("api ")]


def test_link_resolves_child_id_via_get(gh_shim, fake_repo, monkeypatch):
    # The shim returns a database id (424242) deliberately different from the
    # issue number (9001); the helper MUST resolve and use the id.
    monkeypatch.setenv("GH_SHIM_CHILD_ID", "424242")
    monkeypatch.setenv("GH_SHIM_CHILD_NUMBER", "9001")
    gh = _fresh_gh()
    gh.link_sub_issue(7000, 9001)
    api = _api_lines(gh_shim.read_text())
    # A GET on the child issue endpoint to resolve .id.
    assert any("issues/9001" in l and "sub_issues" not in l for l in api), api


def test_link_posts_child_id_not_number(gh_shim, fake_repo, monkeypatch):
    """The POST body MUST carry sub_issue_id = the resolved id, not number."""
    monkeypatch.setenv("GH_SHIM_CHILD_ID", "424242")
    monkeypatch.setenv("GH_SHIM_CHILD_NUMBER", "9001")
    gh = _fresh_gh()
    gh.link_sub_issue(7000, 9001)
    api = _api_lines(gh_shim.read_text())
    post = [l for l in api if "sub_issues" in l]
    assert post, api
    post_line = post[0]
    # POSTs to the PARENT's sub_issues collection.
    assert "issues/7000/sub_issues" in post_line, post_line
    # The footgun guard: the resolved database id (424242) is in the body,
    # the bare issue number (9001) is NOT used as the sub_issue_id.
    assert "424242" in post_line, post_line
    assert "sub_issue_id=9001" not in post_line and '"sub_issue_id": 9001' not in post_line, post_line


def test_link_idempotent_when_already_linked(gh_shim, fake_repo, monkeypatch):
    """An already-linked child must NOT raise — degrade gracefully."""
    monkeypatch.setenv("GH_SHIM_CHILD_ID", "424242")
    monkeypatch.setenv("GH_SHIM_SUBISSUE_POST_EXIT", "1")
    monkeypatch.setenv(
        "GH_SHIM_SUBISSUE_POST_STDERR", "gh: sub-issue already exists (HTTP 422)"
    )
    gh = _fresh_gh()
    # MUST NOT raise even though the POST exits non-zero (already linked).
    gh.link_sub_issue(7000, 9001)
