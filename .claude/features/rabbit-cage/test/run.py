#!/usr/bin/env python3
"""rabbit-cage test runner — executes every suite in declaration order;
exits non-zero on any failure."""

import os
import subprocess
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

SUITES = [
    "test-structure.py",
    "test-version-alignment.py",
    "test-feature-json-validity.py",
    "test-icon-glyphs.py",
    "test-claude-md-imports-resolve.py",
    "test-claude-md-no-stale-imports.py",
    "test-dispatcher-lib.py",
    "test-dispatchers.py",
    "test-deployed-hooks-execute.py",
    "test-install-publish-loop.py",
    "test-install-py-exports.py",
    "test-scope-guard-centralized.py",
    "test-scope-guard-allowlist.py",
    "test-scope-guard-deny-message.py",
    "test-scope-guard-rabbit-allowlist.py",
    "test-scope-per-feature-marker.py",
    "test-RABBIT-CAGE-17-quoted-strings.py",
    "test-repo-permissions-retired.py",
    "test-RABBIT-CAGE-BUG-104-hook-path-format.py",
    "test-write-mode-marker-wired.py",
    "test-mode-marker-root-consistency.py",
    "test-scope-guard-plugin-mode.py",
    "test-install-rewrites-settings.py",
    "test-session-start-alerts-if-rabbit-root-unset.py",
    "test-feature-includes-manifest-closure.py",
    "test-feature-includes-prompts-closure.py",
    "test-feature-includes-scripts-closure.py",
    "test-rabbit-project-consolidate-removed.py",
    "test-install-refuses-without-update.py",
    "test-install-update-mode.py",
    "test-install-update-changelog-summary.py",
    "test-install-update-idempotent.py",
    "test-install-sh-refuses-update-flag.py",
    "test-install-sh-error-points-to-install-py.py",
    "test-rabbit-issue-shipped-in-mvp.py",
    "test-install-sh-version-passthrough.py",
    "test-install-update-self-fetches-without-src.py",
    "test-install-update-infers-target-from-script-location.py",
    "test-install-update-rejects-non-rabbit-target.py",
    "test-install-update-network-failure.py",
    "test-install-update-explicit-src-skips-fetch.py",
    "test-install-deploys-check-release-update.py",
    "test-scope-guard-plugin-feature-spec-allowed.py",
    "test-scope-guard-plugin-feature-spec-denied-no-marker.py",
    "test-scope-guard-plugin-claude-still-denied.py",
    "test-scope-guard-plugin-rabbit-project-non-features-denied.py",
    "test-session-start-release-update-wired.py",
    "test-session-start-auto-resume-wired.py",
    "test-advisory-restart-surfaced.py",
    "test-plugin-scope-guard-allows-fresh-feature-spec-md.py",
    "test-plugin-scope-guard-denies-non-spec-write-without-marker.py",
    "test-plugin-scope-guard-mid-tdd-still-requires-marker.py",
    "test-standalone-spec-md-carveout-unchanged.py",
    "test-scope-guard-specs-dir-dual-read.py",
    "test-scope-guard-flat-docs-dual-read.py",
    "test-workspace-tree-flat-docs.py",
    "test-install-sh-default-ref-not-dev.py",
    "test-install-sh-resolves-latest-release.py",
    "test-plugin-scope-override-path-consistent.py",
    "test-plugin-stop-alert-fires-when-session-override-active.py",
    "test-plugin-sessionstart-alert-on-active-session-override.py",
    "test-plugin-sessionstart-alert-at-canonical-override-path.py",
    "test-standalone-override-path-unchanged.py",
    "test-install-py-default-ref-not-dev.py",
    "test-install-py-default-ref-matches-install-sh.py",
    "test-install-py-resolves-latest-release.py",
    "test-install-py-version-flag-overrides-default.py",
    "test-install-py-update-tag-ref.py",
    "test-install-py-update-no-downgrade.py",
    "test-install-py-channel-dev-opt-in.py",
    "test-install-py-channel-main-default.py",
    "test-install-update-self-reexec.py",
    "test-install-update-no-reexec-with-explicit-src.py",
    "test-install-update-reexec-loop-guard.py",
    "test-changelog-shape.py",
    "test-bypass-permissions-alert-text-inlines-revoke.py",
    "test-bypass-permissions-per-feature-alert.py",
    "test-bypass-permissions-on-demand-not-startup.py",
    "test-tdd-autonomous-relocated-out.py",
    "test-scope-guard-revoke-uses-rabbit-config.py",
    "test-scope-guard-agent-sentinel.py",
    "test-stop-timestamp-entry-present.py",
    "test-session-start-version-line.py",
    "test-runtime-banner-shape.py",
    "test-install-agent-path-rabbit-tdd-subagent.py",
    "test-install-agent-path-rabbit-spec-creator.py",
    "test-specs-layout.py",
    "test-rabbit-update-command.py",
    "test-rabbit-cage-config-command.py",
    "test-command-frontmatter-compliance.py",
    "test-scope-guard-file-scoped-override.py",
    "test-spec-housekeeping-682-dead-prose-removed.py",
    "test-invariants-contiguous-737.py",
    "test-scope-guard-cage-owned-root.py",
    "test-install-e2e-ready-to-run.py",
    "test-install-ships-skill-referenced-scripts.py",
    "test-install-closure-sources-exist.py",
    "test-install-no-drift-on-first-run.py",
    "test-show-mode-command.py",
    "test-scope-guard-decompose-context.py",
    "test-install-version-pin-local-src-not-unknown.py",
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
