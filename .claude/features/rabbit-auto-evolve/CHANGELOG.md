# Changelog

## 0.9.2 — 2026-06-02

- Fix #429: `scripts/merge-prs.py` now performs a DIRECT squash merge (`gh pr merge <#> --squash`) instead of `gh pr merge <#> --squash --auto`. The `--auto` flag requires the repo to have auto-merge enabled (`enablePullRequestAutoMerge`); on a repo without it, `gh pr merge --auto` succeeds only for an immediately-mergeable PR and fails for the rest with `Auto merge is not allowed for this repository`. During a real tick this was order-dependent and intermittent: the first ready PR merged, its siblings fell behind, and `--auto` then tried to ENABLE the auto-merge queue (which the repo rejects). Mergeability is already gated by the `base == dev` refusal plus `safety-check.py`, so a direct merge is correct and never depends on the repo's auto-merge setting. `--delete-branch` was intentionally NOT added so `cleanup-branches.py`'s `git push origin --delete` remains a real deletion (no behavior change to cleanup). `merge-prs.py` module version 1.1.0 → 1.2.0; feature versions bumped 0.9.1 → 0.9.2 across feature.json, spec.md, contract.md, SKILL.md. Spec Inv 6 step 3 and the public-surface table updated to spell out the no-`--auto` rule; new `test/test-merge-prs.py` regression asserts the recorded `gh pr merge` call does NOT contain `--auto` and still uses `--squash`.

## 0.9.1 — 2026-06-02

- Fix #397: `scripts/safety-check.py` Invariant 5 now rejects only on uncommitted modifications to TRACKED files (staged or unstaged), using two `git diff --quiet` calls (`git diff --quiet` for unstaged, `git diff --cached --quiet` for staged) instead of `git status --porcelain`. The old porcelain check counted `??` untracked files as dirtiness, which deadlocked the auto-evolve loop every time a new untracked runtime artifact appeared (e.g. `.rabbit-auto-evolve-*`, `.claude/scheduled_tasks.{lock,json}`) — untracked files cannot affect a merge, so the check was too strict. The check still protects against half-committed subagent work, manual interleaving, and hook-induced drift (all tracked-file modified states). Inv 5 short name and spec table row updated to "no uncommitted modifications to tracked files"; spec test obligations gained a tracked-vs-untracked discrimination bullet. `test/test-safety-check.py` Inv 5 negative test replaced with four scenarios: untracked file PASSES, tracked unstaged mod FAILS, tracked staged mod FAILS, clean tree PASSES. safety-check.py module version 1.0.0 → 1.1.0; feature versions bumped 0.9.0 → 0.9.1 across feature.json, spec.md, contract.md, SKILL.md.

## 0.7.7 — 2026-06-02

- Fix #386: SKILL.md `start` subcommand now routes on the `check-preconditions.py` report shape rather than dumping the failing checklist on every `all_pass: false` case. On fresh state (`active-marker` check `ok: false`) the skill automatically invokes `/rabbit-auto-evolve on` and surfaces the script's branded restart prompt before ending the turn — the user no longer has to manually run `on` first. When markers exist but `bypass-permissions` has not loaded (forgot-to-restart case), the skill emits a short branded reminder line instead of re-running `on`. The verbatim failing-checklist surface is now reserved for the genuinely unexpected fallback branch (partial corruption, manual tampering). Inv 10 in `docs/spec/spec.md` rewritten with the explicit routing table; SKILL.md `start` section rewritten in matching prose; `test/test-start-stop-skill.py` extended to assert the routing keywords are present and the pre-#386 blanket "surface each failing" instruction is absent. Versions bumped 0.7.6 → 0.7.7 across feature.json, spec.md, contract.md (provides.skills version), SKILL.md frontmatter.

## 0.7.6 — 2026-06-02

- Fix #384: `test/test-banner-suppression.py` synthetic tempdir now copies `scripts/banner-status.py` into `<td>/.claude/features/rabbit-auto-evolve/scripts/`. After PR #383 refactored `contract.lib.runtime.emit_auto_evolve_banner` to delegate line-1 and line-2 content to `banner-status.py` via subprocess, the test's synthetic `.claude/features/` tree lacked the script so the subprocess invocation returned non-zero (`No such file or directory`) and `emit_auto_evolve_banner` fell through to its best-effort `[]` failure path — scenarios S2/S3/S4 saw an empty banner. The fix copies the real `banner-status.py` (sourced via `__file__`-relative repo-root resolution) into the tempdir during `build_repo` so subprocess delegation resolves. No source-code change; spec Inv 14 unchanged.

## 0.7.5 — 2026-06-02

- Fix #380 (step 1 of 2): new `scripts/banner-status.py` owns the active-banner line-2 text variants. Emits `{active, line1, line2}` JSON on stdout; always exits 0; reads markers only (no `git`, no `gh`, no filesystem writes). Four line-2 variants with `aborted > restart-needed > running > default` precedence; the new `running` variant (`loop in progress`) is NOT yet surfaced at SessionStart — the current `contract.lib.runtime` `emit_auto_evolve_banner` implementation still inlines the three pre-existing variants. A follow-up cycle against the `contract` feature will refactor `emit_auto_evolve_banner` to invoke `banner-status.py` instead, at which point Inv 14 will defer line-2 ownership to Inv 22. Added spec Inv 22 + ownership-migration note on Inv 14; new `test/test-banner-status.py` covers all 4 variants + 3 precedence pairs + always-exit-0 contract.

## 0.7.4 — 2026-06-02

- Fix #377: `scripts/set-evolve-mode.py` `on`/`off` success now emits branded `rabbit_print` confirmation lines to stdout (matches SessionStart banner format). `on` emits two lines: red `AUTONOMOUS-EVOLVE MODE CONFIGURED — restart Claude Code to activate` (with `🚀` icon) + yellow `After restart, run: /rabbit-auto-evolve start` (with `👉` icon). `off` emits one green line: `Autonomous-evolve mode deactivated — full teardown complete` (with `✅` icon). All lines carry the `[🐇 rabbit 🐇]` brand prefix via the centralized renderer in `contract/scripts/rabbit_print.py`. SKILL.md `on`/`off` subcommand sections now instruct Claude to surface the script's stdout verbatim instead of paraphrasing — the prior flat `set-evolve-mode: on OK` line was easy to miss and the skill's paraphrase didn't match the visual weight of the rest of the rabbit surface. Extended spec Inv 1 with the branded-confirmation paragraph and two new test obligations; new test scenarios G and H in `test-set-evolve-mode.py` assert the brand prefix and key substrings appear on stdout for both `on` and `off`.

## 0.7.3 — 2026-06-02

- Fix #375: new `scripts/check-preconditions.py` emits structured JSON `{all_pass, checks: [{id, ok, detail}]}` reporting on the three `start` preconditions (`active-marker`, `approval-bypass`, `bypass-permissions`). Exit code is ALWAYS 0 — the verdict lives in `all_pass`. SKILL.md `start` section now invokes this script and routes on `all_pass`, replacing the prior narrative description that invited bare `ls .rabbit-auto-evolve-*` precondition checks (which emit ugly `ls: cannot access ...: No such file or directory` stderr noise on fresh clones where the markers legitimately do not yet exist). Added spec Inv 21; extended `test-start-stop-skill.py` to assert the script invocation IS present AND bare `ls .rabbit-auto-evolve-*` patterns are absent; new `test-check-preconditions.py` covers all-fail / all-pass / partial / malformed-settings scenarios.

## 0.7.2 — 2026-06-02

- Fix #373: tick lifecycle hardening. (1) `scripts/start-loop.py` now self-heals before writing the running marker — it deletes any stale `.rabbit-auto-evolve-stop-requested` (explicit `start` cancels a pending stop) and bootstraps `.rabbit/auto-evolve-state.json` with default content (atomic temp+rename, matching `update-state.py`) if the file is missing, empty, or fails JSON parse. A valid existing state file is left untouched. (2) New `scripts/end-tick.py` mirrors `start-loop.py`: it deletes `.rabbit-auto-evolve-running` and is idempotent (missing marker is a no-op). (3) `SKILL.md` tick documentation now invokes `end-tick.py` on EVERY exit path (normal completion, phase 0 halt, safety abort, error abort) — not just the happy path — so the running marker can never leak across sessions. Added spec Inv 19 (`start-loop.py` self-heal) and Inv 20 (`end-tick.py` mandatory at every exit); updated Inv 17 marker table to show start-loop.py writes / end-tick.py deletes `.rabbit-auto-evolve-running`. Extended `test/test-loop-markers.py` (start-loop self-heal scenarios + end-tick round-trip + idempotency) and `test/test-start-stop-skill.py` (SKILL.md must mention `end-tick.py` and the four named exit paths).

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
