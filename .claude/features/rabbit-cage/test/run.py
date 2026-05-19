#!/usr/bin/env python3
"""rabbit-cage test runner — executes all test scripts in sequence; exits non-zero on any failure."""
import os
import subprocess
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

SUITES = [
    "test-scope-guard-centralized.py",
    "test-structure.py",
    "test-claude-md.py",
    "test-obsolete-removed.py",
    "test-hook-enforcement.py",
    "test-generate-claude-md.py",
    "test-split-validation.py",
    "test-RABBIT-CAGE-15-workspace-tree.py",
    "test-generated-surface.py",
    "test-RABBIT-CAGE-16-first-stop-no-false-drift.py",
    "test-RABBIT-CAGE-BACKLOG7-visual-messages.py",
    "test-RABBIT-CAGE-BACKLOG9-green-messages.py",
    "test-RABBIT-CAGE-BACKLOG10-override.py",
    "test-RABBIT-CAGE-17-quoted-strings.py",
    "test-RABBIT-CAGE-18-scope-alert-messages.py",
    "test-scope-per-feature-marker.py",
    "test-RABBIT-CAGE-19-confirm-token-override.py",
    "test-scope-guard-allowlist.py",
    "test-scope-guard-deny-message.py",
    "test-scope-guard-rabbit-allowlist.py",
    "test-RABBIT-CAGE-BUG10-settings-json-allowlist.py",
    "test-rabbit-workspace-map-wiring.py",
    "test-POLICY-BACKLOG-1-session-init-branch.py",
    "test-build-non-git-dir.py",
    "test-rabbit-config.py",
    "test-rabbit-config-permissions.py",
    "test-BACKLOG-11-rabbit-config-skill.py",
    "test-RABBIT-CAGE-21-plugin-change-alert.py",
    "test-RABBIT-CAGE-23-rename-rbt-prefix.py",
    "test-no-rbt-refs.py",
    "test-no-embedded-python3.py",
    "test-RABBIT-CAGE-BUG123.py",
    "test-RABBIT-CAGE-BACKLOG-18-aggregation.py",
    "test-RABBIT-CAGE-BACKLOG-18-sync-check-aggregation.py",
    "test-RABBIT-CAGE-BACKLOG-18-session-init-single-json.py",
    "test-RABBIT-CAGE-BACKLOG-18-pure-renderer-no-side-effects.py",
    "test-RABBIT-CAGE-BACKLOG-19-renderer-adoption.py",
    "test-RABBIT-CAGE-BACKLOG-19-welcome-sublines.py",
    "test-RABBIT-CAGE-BACKLOG-19-first-run-removed.py",
    "test-RABBIT-CAGE-22-stale-marker.py",
    "test-RABBIT-CAGE-BUG4.py",
    "test-RABBIT-CAGE-BUG89.py",
    "test-python-migration.py",
    "test-repo-permissions.py",
    "test-team-wide-permissions.py",
    "test-RABBIT-CAGE-WAVE2-inv61-65.py",
    "test-RABBIT-CAGE-WAVE3-inv66-68.py",
    "test-RABBIT-CAGE-BACKLOG2-python-only.py",
    "test-RABBIT-CAGE-BACKLOG13-claude-md-gitignore-drift.py",
    "test-RABBIT-CAGE-WAVE4-bug-cleanup.py",
    "test-RABBIT-CAGE-WAVE5-cleanup.py",
    "test-RABBIT-CAGE-BACKLOG12-bypass-permissions.py",
    "test-claude-md-header.py",
    "test-RABBIT-CAGE-BACKLOG-20-leading-newline.py",
    "test-RABBIT-CAGE-BACKLOG-21-surface-drift-files.py",
    "test-RABBIT-CAGE-rabbit-config-help.py",
    "test-rabbit-cage-version-alignment.py",
    "test-RABBIT-CAGE-BUG-92-stale-invariants-removed.py",
    "test-RABBIT-CAGE-BACKLOG-22-cleanup.py",
    "test-RABBIT-CAGE-BUG-93-retired-refs.py",
]


def main() -> int:
    print("rabbit-cage test runner")
    print()
    total_fail = 0
    for suite in SUITES:
        print(f"=== {suite} ===")
        path = os.path.join(SCRIPT_DIR, suite)
        result = subprocess.run([sys.executable, path])
        if result.returncode != 0:
            total_fail += 1
        print()

    if total_fail == 0:
        print("ALL SUITES PASSED")
        return 0
    print(f"FAILED: {total_fail} suite(s) had failures")
    return 1


if __name__ == "__main__":
    sys.exit(main())
