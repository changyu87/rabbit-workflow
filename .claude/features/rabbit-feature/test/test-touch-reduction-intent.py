#!/usr/bin/env python3
"""Inv 64 (issue #1198): reduction/intent-carrying feature-touch path.

For a housekeep spec-reduction wave the substantive spec edit must be authored
by the TDD subagent inside its OWN single RED->GREEN cycle, not pre-committed
by feature-touch Step 3. Pre-committing left the subagent's
`spec-update -> test-red` gate with no working-tree spec diff, forcing the
`--spec-no-change-reason` escape hatch. The clean design threads the
spec-reduction INTENT (computed by rabbit-spec-update's `--intent-only`
no-commit mode) into the Step-5 dispatch via the existing impl-suggestion
channel, and SKIPS the Step-3 pre-commit on this path.

This test locks the rabbit-feature half:

  * The companion `feature-touch.py is-reduction-wave "<request>"` subcommand
    detects the housekeep reduction signal and emits JSON {"reduction": bool}.
  * The companion `feature-touch.py persist-intent <feature-name>` subcommand
    reads the `--intent-only` payload from stdin and writes it to the
    impl-suggestion file the Step-5 dispatch consumes, WITHOUT editing or
    committing docs/spec.md.
  * The SKILL.md Step 3 documents the reduction/intent path: it invokes
    rabbit-spec-update in `--intent-only` mode, threads the intent via
    persist-intent, and does NOT pre-commit the spec for that path; the
    DEFAULT path (commit-spec) is unchanged.

Version: 0.1.0
Owner: rabbit-workflow team
Deprecation criterion: when feature-touch orchestration is natively handled
by the rabbit CLI or by Claude Code's native workflow mechanism.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]
SKILL_DIR = (
    REPO_ROOT
    / ".claude/features/rabbit-feature/skills/rabbit-feature-touch"
)
COMPANION = SKILL_DIR / "scripts/feature-touch.py"
SOURCE_SKILL = SKILL_DIR / "SKILL.md"
DEPLOYED_SKILL = REPO_ROOT / ".claude/skills/rabbit-feature-touch/SKILL.md"

# The exact signal rabbit-housekeep passes to rabbit-feature-touch for a
# measured reduction wave (rabbit-housekeep SKILL.md): the args are
# "<name> housekeep: measured reduction wave".
HOUSEKEEP_REDUCTION_REQUEST = "housekeep: measured reduction wave"


def _run(cwd: Path, *args: str, stdin: str | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(COMPANION), *args],
        cwd=cwd,
        input=stdin,
        capture_output=True,
        text=True,
    )


# ---------------------------------------------------------------------------
# is-reduction-wave: detects the housekeep reduction signal.
# ---------------------------------------------------------------------------
def test_is_reduction_wave_detects_housekeep_signal() -> None:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td).resolve()
        subprocess.run(["git", "init", "-q", str(root)], check=True)
        r = _run(root, "is-reduction-wave", HOUSEKEEP_REDUCTION_REQUEST)
        assert r.returncode == 0, f"is-reduction-wave failed: {r.stderr}"
        payload = json.loads(r.stdout)
        assert payload.get("reduction") is True, (
            f"the housekeep reduction request must be detected; got {payload!r}"
        )


def test_is_reduction_wave_negative_for_normal_request() -> None:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td).resolve()
        subprocess.run(["git", "init", "-q", str(root)], check=True)
        r = _run(root, "is-reduction-wave", "add a new invariant for X")
        assert r.returncode == 0, f"is-reduction-wave failed: {r.stderr}"
        payload = json.loads(r.stdout)
        assert payload.get("reduction") is False, (
            f"a normal feature request must NOT be a reduction wave; got {payload!r}"
        )


# ---------------------------------------------------------------------------
# persist-intent: writes the intent payload to the impl-suggestion file and
# edits/commits NOTHING in the feature spec.
# ---------------------------------------------------------------------------
_INTENT_PAYLOAD = {
    "schema_version": "1.0.0",
    "feature": "demo",
    "generated_at": "2026-06-13T00:00:00Z",
    "request_summary": "reduce demo spec",
    "spec_changes": "remove dead prose",
    "implementation_approach": "author the reduction + gating test in one cycle",
    "affected_files": [".claude/features/demo/docs/spec.md"],
    "key_invariants": ["behavior preserved"],
}


def _make_feature_repo(root: Path) -> Path:
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    subprocess.run(["git", "-C", str(root), "config", "user.email", "t@t"], check=True)
    subprocess.run(["git", "-C", str(root), "config", "user.name", "t"], check=True)
    feat = root / ".claude/features/demo/docs"
    feat.mkdir(parents=True)
    spec = feat / "spec.md"
    spec.write_text("# demo spec\nv1\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(root), "add", "-A"], check=True)
    subprocess.run(["git", "-C", str(root), "commit", "-q", "-m", "base"], check=True)
    return spec


def test_persist_intent_writes_impl_suggestion_file() -> None:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td).resolve()
        _make_feature_repo(root)
        r = _run(
            root, "persist-intent", "demo",
            stdin=json.dumps(_INTENT_PAYLOAD),
        )
        assert r.returncode == 0, f"persist-intent failed: {r.stderr}"
        # The impl-suggestion file the Step-5 dispatch consumes must now exist
        # and carry the intent payload verbatim.
        impl = root / ".rabbit" / "impl-suggestion-demo.json"
        assert impl.is_file(), (
            f"persist-intent must write the impl-suggestion file at {impl}"
        )
        written = json.loads(impl.read_text(encoding="utf-8"))
        assert written == _INTENT_PAYLOAD, (
            f"persisted intent must match the emitted payload; got {written!r}"
        )
        # The subcommand must print the impl-suggestion path so the SKILL body
        # can thread it into the dispatch.
        assert "impl-suggestion-demo.json" in r.stdout, (
            f"persist-intent must print the impl-suggestion path; got {r.stdout!r}"
        )


def test_persist_intent_does_not_edit_or_commit_spec() -> None:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td).resolve()
        spec = _make_feature_repo(root)
        before = spec.read_text(encoding="utf-8")
        head_before = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "HEAD"],
            capture_output=True, text=True,
        ).stdout.strip()

        r = _run(
            root, "persist-intent", "demo",
            stdin=json.dumps(_INTENT_PAYLOAD),
        )
        assert r.returncode == 0, f"persist-intent failed: {r.stderr}"

        # The spec must be byte-identical (intent-only: edit nothing).
        assert spec.read_text(encoding="utf-8") == before, (
            "persist-intent must NOT edit docs/spec.md (intent-only)"
        )
        # No new commit (intent-only: commit nothing).
        head_after = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "HEAD"],
            capture_output=True, text=True,
        ).stdout.strip()
        assert head_after == head_before, (
            "persist-intent must NOT create a commit (intent-only)"
        )


# ---------------------------------------------------------------------------
# SKILL.md Step 3 documents the reduction/intent path.
# ---------------------------------------------------------------------------
def _step3(text: str) -> str:
    m = re.search(
        r"^###\s+Step\s+3\s+[-—]\s+.+?\s*$(.*?)(?=^###\s|^##\s|\Z)",
        text,
        re.MULTILINE | re.DOTALL,
    )
    assert m, "SKILL.md is missing a 'Step 3' section"
    return m.group(1)


def test_skill_step3_documents_reduction_intent_path() -> None:
    for path, label in ((SOURCE_SKILL, "source"), (DEPLOYED_SKILL, "deployed")):
        assert path.exists(), f"missing SKILL.md: {path}"
        body = _step3(path.read_text(encoding="utf-8"))
        # The intent path must invoke rabbit-spec-update in --intent-only mode.
        assert "--intent-only" in body, (
            f"Step 3 ({label}) must invoke rabbit-spec-update in --intent-only "
            "mode for the reduction/intent path (Inv 64)"
        )
        # The reduction-path detection must be script-backed.
        assert "is-reduction-wave" in body, (
            f"Step 3 ({label}) must detect the reduction path via the "
            "script-backed is-reduction-wave subcommand (Inv 64, §4)"
        )
        # The intent must be threaded via persist-intent.
        assert "persist-intent" in body, (
            f"Step 3 ({label}) must thread the intent via the persist-intent "
            "subcommand (Inv 64)"
        )
        # The default path's commit-spec obligation must remain.
        assert "commit-spec" in body, (
            f"Step 3 ({label}) must still document commit-spec for the default "
            "(non-reduction) path (Inv 16 unchanged)"
        )


# ---------------------------------------------------------------------------
# Usage lists the new subcommands.
# ---------------------------------------------------------------------------
def test_usage_lists_new_subcommands() -> None:
    r = subprocess.run(
        [sys.executable, str(COMPANION)],
        capture_output=True,
        text=True,
    )
    assert r.returncode == 2, f"no-arg invocation must exit 2; got {r.returncode}"
    usage = r.stderr
    assert "is-reduction-wave" in usage, "usage must list is-reduction-wave"
    assert "persist-intent" in usage, "usage must list persist-intent"


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    fail = 0
    for t in tests:
        try:
            t()
            print(f"PASS {t.__name__}")
        except AssertionError as e:
            print(f"FAIL {t.__name__}: {e}", file=sys.stderr)
            fail += 1
        except Exception as e:  # noqa: BLE001
            print(f"ERROR {t.__name__}: {e}", file=sys.stderr)
            fail += 1
    sys.exit(0 if fail == 0 else 1)
