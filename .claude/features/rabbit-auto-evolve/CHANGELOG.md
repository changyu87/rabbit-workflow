# Changelog

## 0.7.1 — 2026-06-02

- Fix #371: `scripts/set-evolve-mode.py off` now performs a full teardown — it deletes the four loop-runtime markers (`.rabbit-auto-evolve-running`, `.rabbit-auto-evolve-stop-requested`, `.rabbit-auto-evolve-restart-needed`, `.rabbit-auto-evolve-aborted`) first (idempotent), then reverses the three activation mutations in inverse order. In v0.7.0 `off` only deleted `.rabbit-auto-evolve-active`, leaving the loop-runtime markers behind for the user to clean up manually (which scope-guard then denied because literal `rm`/`touch` of non-allowlisted markers is blocked). SKILL.md tick prose updated to reference `triage-batch.py` in the canonical `fetch-queue | triage-batch | plan-batch` pipe (Inv 18 follow-up from #369). Spec Inv 1 rewritten to detail the 4-step teardown and bumped to v0.7.1; `test-set-evolve-mode.py` extended with full-teardown and partial-state scenarios; `test-tick-skill.py` now asserts SKILL.md references `triage-batch.py`.

## 0.7.0 — 2026-06-02

- Fix #369: add `scripts/triage-batch.py` bridge so the standard tick pipe `fetch-queue | triage-batch | plan-batch` works end-to-end. `triage-batch.py` reads the raw `gh issue list` shape on stdin, invokes `triage-issue.py` per item, and emits the concatenated triage-object array on stdout. Per-issue failures are converted to `defer/triage-failed` entries so a single bad issue cannot abort the batch. `plan-batch.py` now silently drops items where `decision != "work"` (items without the `decision` key continue to pass through for backwards compatibility). Added spec Inv 18 and `test-triage-batch.py`; extended `test-plan-batch.py` to cover the unfiltered triage array case.

## 0.6.0 — 2026-06-02

- Fix #367: marker writes wrapped in scripts (`start-loop.py`, `stop-loop.py`, `mark-restart-needed.py`, `mark-aborted.py`) so scope-guard does not block them. SKILL.md's `start` and `stop` subcommand sections now instruct the dispatcher to invoke `python3 .claude/features/rabbit-auto-evolve/scripts/start-loop.py` / `stop-loop.py` rather than write the markers directly. Mirrors the proven `set-evolve-mode.py` pattern. Added spec Inv 17 plus `test-loop-markers.py`; extended `test-start-stop-skill.py` to assert SKILL.md contains the script invocations and forbids literal `touch .rabbit-auto-evolve-*` / `echo > .rabbit-auto-evolve-*`.

## 0.5.2 — 2026-06-02

- Fix #364: drop `model: opus` from SKILL.md frontmatter (default session model handles dispatch); `feature.json` prompts[0].inject now uses full repo-relative paths (`.claude/features/policy/<name>.md`) so the prompt dispatcher resolves them and the Stop-hook `prompt-injection failures: rabbit-auto-evolve` line goes away. Spec Inv 10 + Inv 12 refined; test-prompts-declared.py extended to assert (a) no `model:` key in SKILL.md frontmatter, (b) every inject entry is a full repo-relative path to an existing file (no bare names).

## 0.5.1 — 2026-06-02

- Fix #362: SKILL.md script references now use the full feature-relative path `.claude/features/rabbit-auto-evolve/scripts/<name>.py` (bare `scripts/<name>.py` was failing with file-not-found because Claude resolves SKILL paths relative to the deployed `.claude/skills/rabbit-auto-evolve/` location, which has no `scripts/` subdir). Added Inv 16 to spec; extended test-on-off-surface.py and test-tick-skill.py to assert feature-relative prefix.

## 0.5.0 — 2026-06-02

- Surface consolidation (#360): `/rabbit-auto-evolve` now owns `on`/`off` activation; `/rabbit-config` no longer dispatches the auto-evolve loop. Removed `configuration[auto-evolve]` from `feature.json`; added `### on` and `### off` subcommand sections to SKILL.md; bumped version to 0.5.0 across feature.json, spec.md, contract.md, SKILL.md.

## 0.4.0 — 2026-06-02

- Feature-shape compliance pass: aligned versions across feature.json, spec.md, contract.md, SKILL.md; added test-feature-shape.py guard.

## 0.3.0 — 2026-06-02

- Phase D Task 12 + Task 13 — SKILL.md (4 subcommands + 12-phase tick), feature.json wiring (manifest, configuration, prompts, runtime, surface.skills), cross-scope registration in workspace-structure.json, passthrough template, banner-suppression e2e test.

## 0.2.0 — 2026-06-02

- Phase C — all 10 scripts (set-evolve-mode, fetch-queue, triage-issue, plan-batch, safety-check, merge-prs, cleanup-branches, release-bump, classify-merge-restart, update-state) + auto-evolve-state.schema.json; spec invariants 1–9.

## 0.1.0 — 2026-06-01

- Scaffold + seed spec (PR #333).
