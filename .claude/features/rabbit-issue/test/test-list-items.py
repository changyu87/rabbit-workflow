"""E2E tests for scripts/list-items.py (filtered listing with deterministic sort)."""
import json
import os
import subprocess
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
LIST = SCRIPTS / "list-items.py"


def _run(*args, env=None):
    return subprocess.run(
        [sys.executable, str(LIST), *args],
        capture_output=True, text=True, env=env or os.environ.copy(),
    )


def test_list_open_bugs_calls_gh_with_correct_labels(gh_shim, fake_repo):
    r = _run("--type", "bug")
    assert r.returncode == 0, r.stderr
    log = gh_shim.read_text()
    assert "issue list" in log
    assert "rabbit-managed" in log
    assert "--state open" in log
    # bug appears as a label filter
    assert "--label bug" in log


def test_list_all_types_omits_type_label(gh_shim, fake_repo):
    r = _run("--type", "all")
    assert r.returncode == 0, r.stderr
    log = gh_shim.read_text()
    assert "rabbit-managed" in log
    # type=all → no bug/enhancement label filter
    list_call = log.split("issue list", 1)[1]
    assert "--label bug" not in list_call
    assert "--label enhancement" not in list_call


def test_list_filters_by_feature(gh_shim, fake_repo):
    r = _run("--type", "bug", "--feature", "rabbit-cage")
    assert r.returncode == 0, r.stderr
    assert "feature:rabbit-cage" in gh_shim.read_text()


def test_list_state_closed(gh_shim, fake_repo):
    r = _run("--type", "all", "--status", "closed")
    assert r.returncode == 0, r.stderr
    assert "--state closed" in gh_shim.read_text()


def test_deterministic_sort_by_number_asc(gh_shim, fake_repo, tmp_path):
    fixture = tmp_path / "list.json"
    fixture.write_text(json.dumps([
        {"number": 17, "title": "t17", "state": "open",
         "labels": [{"name": "bug"}, {"name": "priority:high"},
                    {"name": "feature:rabbit-cage"}, {"name": "rabbit-managed"}]},
        {"number": 3, "title": "t3", "state": "open",
         "labels": [{"name": "bug"}, {"name": "priority:low"},
                    {"name": "feature:rabbit-cage"}, {"name": "rabbit-managed"}]},
        {"number": 9, "title": "t9", "state": "open",
         "labels": [{"name": "enhancement"}, {"name": "priority:medium"},
                    {"name": "feature:rabbit-cage"}, {"name": "rabbit-managed"}]},
    ]))
    env = os.environ.copy()
    env["GH_SHIM_LIST_RESPONSE"] = str(fixture)
    r = _run("--type", "all", env=env)
    assert r.returncode == 0, r.stderr
    lines = [l for l in r.stdout.strip().split("\n") if l.startswith("#")]
    assert len(lines) == 3
    assert lines[0].startswith("#3 ")
    assert lines[1].startswith("#9 ")
    assert lines[2].startswith("#17 ")


def test_output_format_includes_type_state_priority_feature(gh_shim, fake_repo, tmp_path):
    fixture = tmp_path / "list.json"
    fixture.write_text(json.dumps([
        {"number": 42, "title": "login broken", "state": "open",
         "labels": [{"name": "bug"}, {"name": "priority:high"},
                    {"name": "feature:rabbit-cage"}, {"name": "rabbit-managed"}]},
    ]))
    env = os.environ.copy()
    env["GH_SHIM_LIST_RESPONSE"] = str(fixture)
    r = _run("--type", "bug", env=env)
    assert r.returncode == 0, r.stderr
    line = r.stdout.strip().split("\n")[0]
    assert "#42" in line
    assert "bug" in line
    assert "open" in line
    assert "high" in line
    assert "feature:rabbit-cage" in line
    assert "login broken" in line
