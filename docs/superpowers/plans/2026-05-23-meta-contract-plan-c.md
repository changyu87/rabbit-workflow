# Plan C — rabbit-cage Dispatcher Rewrite

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rewrite rabbit-cage from a per-feature-aware monolith into a thin dispatcher service that enumerates features and invokes their declared MANIFEST / RUNTIME / CONFIGURATION API calls via the contract API libraries.

**Architecture:** Three dispatcher hooks (Stop / SessionStart / UserPromptSubmit) iterate every feature's `feature.json runtime[event]` array, invoke each API via `contract.lib.runtime`, partition results, and emit one Claude Code JSON object per invocation. `install.py` enumerates every feature's `feature.json manifest` and invokes each call via `contract.lib.publish`. PreToolUse remains `scope-guard.py` (unchanged). All other rabbit-cage behavior collapses into rabbit-cage's own `feature.json` declarations.

**Tech Stack:** Python 3 stdlib only. Imports from `.claude/features/contract/lib/{publish,runtime,mutation,producers}.py`.

**Reference docs:**
- `docs/superpowers/specs/2026-05-23-meta-contract-architecture-design.md` (North Star — section "Concrete Migration: rabbit-cage" has the worked example for MANIFEST/RUNTIME/CONFIGURATION)
- `docs/superpowers/specs/2026-05-23-housekeeping-protocol.md` (binding audit criteria)
- `.claude/features/rabbit-cage/docs/spec/spec.md` (the existing 892-line spec — to be substantially rewritten)
- `.claude/features/contract/lib/runtime.py`, `publish.py`, `producers.py`, `mutation.py` (the Plan B APIs — do not modify; file a bug if buggy)

---

## File Structure (target end state)

**rabbit-cage feature directory:**

- `feature.json` — full MANIFEST + RUNTIME + CONFIGURATION declarations (per design doc)
- `hooks/scope-guard.py` — UNCHANGED (PreToolUse owner)
- `hooks/_dispatcher_lib.py` — NEW: shared helper for the three event dispatchers
- `hooks/stop-dispatcher.py` — NEW: Stop-event entry point
- `hooks/session-start-dispatcher.py` — NEW: SessionStart-event entry point
- `hooks/user-prompt-submit-dispatcher.py` — NEW: UserPromptSubmit-event entry point
- `install.py` — REWRITTEN: copies tree, then enumerates feature.json `manifest` calls
- `policy-header.json` — KEPT (consumed by `generate-claude-md` producer args)
- `settings.json` — KEPT (consumed by `publish_settings` manifest call)
- `README.md` — KEPT (consumed by `publish_file` manifest call)
- `commands/rabbit-refresh.md`, `commands/rabbit-project.md` — KEPT (consumed by `publish_command`)
- `scripts/scope-guard-on.py` — KEPT (operator-facing revoke command)
- `scripts/repo-permissions.py` — KEPT (consumed via `run_feature_script` for `/rabbit-config permissions lock|unlock`)
- `scripts/rabbit-project.py`, `rabbit-project-consolidate.py`, `rabbit-project-map.py`, `rabbit-project-set-path.py`, `workspace-tree.py` — KEPT (user-facing auxiliary scripts referenced by `commands/rabbit-project.md`)
- `docs/spec/spec.md` — REWRITTEN to ~150 lines / 10–20 invariants
- `docs/spec/contract.md` — UPDATED to reflect post-rewrite surface
- `test/` — TRIMMED: only spec-only tests retained; new tests added

**Files DELETED:**

- `hooks/refresh.py`, `hooks/sync-check.py`, `hooks/session-init.py`, `hooks/_runtime_flags.py`
- `scripts/build.py`, `scripts/generate-claude-md.py`, `scripts/generate-claude-md-header.py`
- `publish.json` (rabbit-cage's; its declarations move into `feature.json manifest`)
- `skills/rabbit-config/` (moves to Plan D's rabbit-config feature)
- Most existing tests under `test/` (see Task 8 for the kept list)

**Outside-scope files (anti-scope — DO NOT TOUCH):**

- `.claude/features/contract/lib/*.py`
- Any other feature's `feature.json` / `publish.json` / spec / code

---

## Task 1: Dispatcher helper library

**Files:**
- Create: `.claude/features/rabbit-cage/hooks/_dispatcher_lib.py`
- Test: `.claude/features/rabbit-cage/test/test-dispatcher-lib.py`

### Module interface

```python
# _dispatcher_lib.py — shared helper for stop/session-start/user-prompt-submit dispatchers.
#
# Each dispatcher entry point calls:
#   payloads = dispatch_event("Stop" | "SessionStart" | "UserPromptSubmit", repo_root)
#   json_dict = render_emission(payloads)
#   if json_dict: sys.stdout.write(json.dumps(json_dict) + "\n")
#
# Functions:
#   enumerate_features(repo_root) -> Iterator[(name, feature_dir, feature_dict)]
#       Yields features in alphabetical order by name. Skips retired features
#       (feature.json status == "retired"). Skips malformed feature.json silently.
#
#   dispatch_event(event, repo_root) -> List[dict]
#       For each feature in enumeration order, reads feature_dict["runtime"].get(event, []),
#       and for each {api, args} entry invokes contract.lib.runtime.<api>(**args, repo_root=...
#       feature_dir=... where applicable) and appends results (single dict or list).
#
#   render_emission(payloads) -> Optional[dict]
#       Partitions payloads into prints / injects / oks / errors. Returns
#       {"systemMessage": ..., optionally "additionalContext": ...} or None
#       (no JSON emitted).
```

### Behavior

- `enumerate_features` walks `<repo_root>/.claude/features/*/feature.json`, alphabetical by directory name. Each `feature.json` is loaded as JSON. If it has `status: "retired"`, skip. If JSON load fails, skip silently (matches `contract.lib.runtime._enumerate_features`).
- `dispatch_event(event, repo_root)`:
  - For each feature in enumeration order:
    - `runtime = feature_dict.get("runtime") or {}`
    - `entries = runtime.get(event) or []`
    - For each entry in declaration order:
      - `api_name = entry["api"]`, `args = entry.get("args") or {}`
      - Look up `fn = getattr(contract.lib.runtime, api_name, None)`. If None: append an error_result and continue.
      - Pass `args` plus `repo_root=repo_root` and (if the API needs it) `feature_dir=feature_dir`. The fixed set of APIs that need `feature_dir`: `check_drift_regenerate` (per runtime.py signature).
      - Wrap call in try/except. On exception, append error_result(str(e)).
      - Result may be a single dict or a list. Extend payloads accordingly.
  - Return the full list of result dicts.
- `render_emission(payloads)`:
  - Prints: all dicts with `type == "print"` → rendered via `rabbit_print` and joined into systemMessage.
  - Injects: all dicts with `type == "inject"` → concatenated into `additionalContext`.
  - Oks: dropped.
  - Errors: written to stderr (one line per error), NOT surfaced.
  - If both prints and injects are empty: return None.
  - Otherwise return `{"systemMessage": <rabbit_block(prints)>, ["additionalContext": <concat>]}`.

### Rendering details

`contract.lib.runtime.print_result` returns `{"type": "print", "text": str, "icon": str, "color": str}`. The dispatcher renders each print via `rabbit_print.rabbit_print(text=..., icon=..., color=..., format="banner")` (the registry-decoupled call form per Plan B). Multiple print lines are joined via `rabbit_block(*lines)` (sole owner of the leading newline).

For SessionStart sub-line outputs (e.g., from `welcome_with_policy`), the print's `text` may already include newlines — render as-is, don't add a banner wrapper.

**Decision:** Use `rabbit_print.rabbit_print(text=..., icon=..., color=..., format="banner")` for top-level prints; if the print's text contains newlines, treat the first line as the banner and subsequent lines as sub-lines, rendered via `rabbit_subline()`. See Task 2 step 4 for the helper.

### Tests (TDD — write first, watch fail, implement)

- [ ] **Step 1: Write failing test for `enumerate_features`** — fixture: build a temp repo with `.claude/features/{a,b,c}/feature.json` and `.claude/features/retired/feature.json` (status: retired). Assert iteration yields `(a, b, c)` in order, skips `retired`. Also assert malformed JSON file is skipped silently.

- [ ] **Step 2: Run test, verify it FAILS** (module not yet defined). `python3 .claude/features/rabbit-cage/test/test-dispatcher-lib.py`

- [ ] **Step 3: Implement `enumerate_features`** in `_dispatcher_lib.py`.

- [ ] **Step 4: Run test, verify PASS.**

- [ ] **Step 5: Write failing test for `dispatch_event`** — fixture: a feature with `runtime: {"Stop": [{"api": "check_marker_alert", "args": {"path": ".m", "content": null, "alert": {"text": "X", "icon": "warn", "color": "red"}}}]}`. With the marker file present, dispatch should return one `print_result`. With it absent, should return one `ok_result`. Two features with Stop entries return them in alphabetical+declaration order.

- [ ] **Step 6: Run test, verify it FAILS.**

- [ ] **Step 7: Implement `dispatch_event`.**

- [ ] **Step 8: Run test, verify PASS.**

- [ ] **Step 9: Write failing test for `render_emission`** — partitioning: a payload list of `[print, inject, ok, error, print]` produces `{"systemMessage": <two prints rabbit_block'd>, "additionalContext": <inject content>}`. Empty input returns None. Only-oks input returns None. Errors are logged to stderr but do not appear in returned dict.

- [ ] **Step 10: Run test, verify it FAILS.**

- [ ] **Step 11: Implement `render_emission`.** Use `rabbit_print` module (already in `.claude/features/contract/scripts/rabbit_print.py`) with the same path discovery pattern that existing hooks use:
    ```python
    _HERE = Path(__file__).resolve().parent
    for _c in [_HERE, *_HERE.parents]:
        _m = _c / "features" / "contract" / "scripts"
        if (_m / "rabbit_print.py").is_file():
            sys.path.insert(0, str(_m))
            break
    from rabbit_print import rabbit_print, rabbit_block, rabbit_subline
    ```

- [ ] **Step 12: Run test, verify PASS.**

- [ ] **Step 13: Commit.**
  ```bash
  git add .claude/features/rabbit-cage/hooks/_dispatcher_lib.py .claude/features/rabbit-cage/test/test-dispatcher-lib.py
  git commit -m "feat(rabbit-cage): add dispatcher helper library (Plan C task 1)"
  ```

---

## Task 2: Three dispatcher hook entry points

**Files:**
- Create: `.claude/features/rabbit-cage/hooks/stop-dispatcher.py`
- Create: `.claude/features/rabbit-cage/hooks/session-start-dispatcher.py`
- Create: `.claude/features/rabbit-cage/hooks/user-prompt-submit-dispatcher.py`
- Test: `.claude/features/rabbit-cage/test/test-dispatchers.py`

### Entry point template

Each entry point is ~30 lines:

```python
#!/usr/bin/env python3
"""<event>-dispatcher.py — <event> hook dispatcher.

Enumerates every feature's runtime[<EVENT>] declarations, invokes each declared
API via contract.lib.runtime, partitions returns into print/inject/ok/error,
and emits at most one JSON object per invocation to stdout.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))
from _dispatcher_lib import dispatch_event, render_emission  # noqa: E402


def repo_root() -> Path:
    env = os.environ.get("RABBIT_ROOT")
    if env:
        return Path(env)
    here = Path(__file__).resolve().parent
    try:
        out = subprocess.check_output(
            ["git", "-C", str(here), "rev-parse", "--show-toplevel"],
            stderr=subprocess.DEVNULL,
        )
        return Path(out.decode().strip())
    except Exception:
        return here


def main() -> int:
    if len(sys.argv) > 1 and sys.argv[1] in ("-h", "--help"):
        sys.stdout.write(
            "<event>-dispatcher.py — Claude Code <Event> hook.\n"
            "Enumerates every feature's runtime[<Event>] declarations, invokes each "
            "via contract.lib.runtime, emits at most one JSON object.\n"
        )
        return 0
    # Consume stdin payload (Claude Code may pass JSON; we currently ignore content).
    try:
        sys.stdin.read()
    except Exception:
        pass
    root = str(repo_root())
    payloads = dispatch_event("<EVENT>", root)
    emission = render_emission(payloads)
    if emission is not None:
        sys.stdout.write(json.dumps(emission) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

Three files differ only in:
- module docstring `<event>` substitution
- the `dispatch_event("<EVENT>", root)` call: `"Stop"`, `"SessionStart"`, `"UserPromptSubmit"`

### Tests

- [ ] **Step 1: Write failing integration test** for `stop-dispatcher.py`. Fixture: a temp repo with `.claude/features/cage/feature.json` declaring one Stop entry (`check_marker_alert` with marker present). Run `python3 stop-dispatcher.py` with `RABBIT_ROOT` env set; assert stdout is a single JSON object with `systemMessage` containing the alert text rendered through `rabbit_print`.

- [ ] **Step 2: Run test → FAIL** (file not yet created).

- [ ] **Step 3: Implement `stop-dispatcher.py`** (chmod +x).

- [ ] **Step 4: Run test → PASS.**

- [ ] **Step 5: Write failing test for `session-start-dispatcher.py`.** Fixture: a feature with `runtime.SessionStart: [{"api": "welcome_with_policy", "args": {"policy_source": ".claude/features/policy/"}}]`. (`policy_source` is repo-root-relative; relies on the in-repo policy/ dir which the runtime API reads.) Assert stdout JSON contains both `systemMessage` (welcome banner) and `additionalContext` (concatenated policy *.md content).

- [ ] **Step 6: Run test → FAIL.**

- [ ] **Step 7: Implement `session-start-dispatcher.py`.** Run test → PASS.

- [ ] **Step 8: Write failing test for `user-prompt-submit-dispatcher.py`.** Fixture: a feature with `runtime.UserPromptSubmit: [{"api": "check_counter_threshold_refresh", "args": {"counter": ".cnt", "env_var": "RABBIT_REFRESH_EVERY", "source": ".claude/features/policy/"}}]`. Set `RABBIT_REFRESH_EVERY=1`. Pre-write `.cnt` with `0`. First invocation: counter goes to 1 == threshold, returns inject; assert stdout JSON has `additionalContext` containing policy text and no `systemMessage`. Below-threshold case: pre-write `.cnt` with `0` and set `RABBIT_REFRESH_EVERY=100`; assert stdout is empty (no JSON).

- [ ] **Step 9: Run test → FAIL. Implement → PASS.**

- [ ] **Step 10: Commit.**
  ```bash
  git add .claude/features/rabbit-cage/hooks/{stop,session-start,user-prompt-submit}-dispatcher.py .claude/features/rabbit-cage/test/test-dispatchers.py
  git commit -m "feat(rabbit-cage): add three event-dispatcher hooks (Plan C task 2)"
  ```

---

## Task 3: rabbit-cage feature.json MANIFEST/RUNTIME/CONFIGURATION

**Files:** Modify `.claude/features/rabbit-cage/feature.json`.

### What to add

Per the design doc's "Concrete Migration: rabbit-cage" section, add three top-level keys to feature.json:

**manifest** (15 entries):
1. `publish_hook(event=Stop, source=hooks/stop-dispatcher.py)`
2. `publish_hook(event=SessionStart, source=hooks/session-start-dispatcher.py)`
3. `publish_hook(event=UserPromptSubmit, source=hooks/user-prompt-submit-dispatcher.py)`
4. `publish_hook(event=PreToolUse, source=hooks/scope-guard.py)`
5. `publish_settings(source=settings.json)`
6. `publish_generated(target=CLAUDE.md, producer=generate-claude-md, args={policy_source: ".claude/features/policy/", header_source: "policy-header.json"})`
7. `publish_file(source=README.md, dest=README.md)`
8. `publish_file(source=install.py, dest=install.py)`
9. `publish_command(source=commands/rabbit-refresh.md)`
10. `publish_command(source=commands/rabbit-project.md)`

**runtime** (3 events):
- `Stop`: 5 entries (per design doc) — drift regen, manifest drift, scope override marker, scope override-used consume, skills-updated consume.
- `SessionStart`: 1 entry — welcome_with_policy.
- `UserPromptSubmit`: 1 entry — check_counter_threshold_refresh.

**configuration** (7 entries): human-approval, bypass-permissions, prompt-threshold, allowed-tools, bash-allow, permissions (per design doc worked example).

### Field updates

- `version`: bump to `5.0.0` (major: full architecture rewrite, breaking).
- `surface.skills`: set to `[]` (rabbit-config moves to Plan D).
- `tdd_state`: set to `"test-green"` after Task 9.
- `updated`: today's date `"2026-05-23"`.

### Steps

- [ ] **Step 1: Write the full new feature.json** — use design doc verbatim where applicable; ensure JSON is valid (round-trip via `python3 -c "import json; json.load(open(...))"`).

- [ ] **Step 2: Verify it parses cleanly** (no other action).

- [ ] **Step 3: Commit.**
  ```bash
  git add .claude/features/rabbit-cage/feature.json
  git commit -m "feat(rabbit-cage): author meta-contract declarations in feature.json (Plan C task 3)"
  ```

---

## Task 4: install.py rewrite

**Files:** Rewrite `.claude/features/rabbit-cage/install.py`. Test: `test/test-install-publish-loop.py`.

### Behavior

- Preserve the existing argparse interface: `install.py [TARGET] [--all]`.
- Preserve copytree behavior (download from URL or copy local).
- Replace the `subprocess.check_call(["python3", build.py, target])` with an in-process manifest enumeration loop:

```python
def run_publish_loop(target_root: str) -> int:
    """Enumerate <target_root>/.claude/features/*/feature.json, invoke every
    manifest API via contract.lib.publish. Returns count of failed calls.
    """
    sys.path.insert(0, os.path.join(target_root, ".claude/features/contract"))
    from lib import publish  # noqa
    failures = 0
    features_root = os.path.join(target_root, ".claude/features")
    for name in sorted(os.listdir(features_root)):
        fdir = os.path.join(features_root, name)
        fj = os.path.join(fdir, "feature.json")
        if not os.path.isfile(fj):
            continue
        try:
            with open(fj) as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError):
            continue
        if data.get("status") == "retired":
            continue
        for entry in (data.get("manifest") or []):
            api_name = entry.get("api")
            args = entry.get("args") or {}
            fn = getattr(publish, api_name, None)
            if fn is None:
                sys.stderr.write(f"install: feature {name} declares unknown API {api_name}\n")
                failures += 1
                continue
            try:
                result = fn(**args, feature_dir=fdir, repo_root=target_root)
            except Exception as e:
                sys.stderr.write(f"install: {name}::{api_name} raised: {e}\n")
                failures += 1
                continue
            if not getattr(result, "passed", False):
                for msg in getattr(result, "messages", []) or []:
                    sys.stderr.write(f"install: {name}::{api_name}: {msg}\n")
                failures += 1
    return failures
```

Replace the existing `subprocess.check_call(["python3", build.py, target])` block with `run_publish_loop(target)`; if it returns non-zero, exit non-zero (after the rollback the existing code already does).

### Tests

- [ ] **Step 1: Write failing test** — fixture: a temp dir with `.claude/features/cage/feature.json` declaring one trivial `publish_file` manifest entry plus a source file. Call `install.run_publish_loop(temp_dir)`. Assert returns 0 and the destination file exists with expected content. Second call: same fixture, assert still returns 0 (idempotent).

- [ ] **Step 2: Run test → FAIL** (function not yet defined).

- [ ] **Step 3: Implement the rewrite. Run test → PASS.**

- [ ] **Step 4: Add a second test** for failure reporting: a manifest entry with `api = "publish_nonexistent"` should cause `run_publish_loop` to return >= 1, write to stderr, but NOT raise.

- [ ] **Step 5: Run, verify FAIL → implement guard → PASS.**

- [ ] **Step 6: Commit.**
  ```bash
  git add .claude/features/rabbit-cage/install.py .claude/features/rabbit-cage/test/test-install-publish-loop.py
  git commit -m "feat(rabbit-cage): rewrite install.py to invoke manifest APIs (Plan C task 4)"
  ```

---

## Task 5: Delete superseded files

**Files DELETED:**
- `.claude/features/rabbit-cage/hooks/refresh.py`
- `.claude/features/rabbit-cage/hooks/sync-check.py`
- `.claude/features/rabbit-cage/hooks/session-init.py`
- `.claude/features/rabbit-cage/hooks/_runtime_flags.py`
- `.claude/features/rabbit-cage/hooks/__pycache__/` (and any other pycaches)
- `.claude/features/rabbit-cage/scripts/build.py`
- `.claude/features/rabbit-cage/scripts/generate-claude-md.py`
- `.claude/features/rabbit-cage/scripts/generate-claude-md-header.py`
- `.claude/features/rabbit-cage/publish.json`
- `.claude/features/rabbit-cage/skills/rabbit-config/` (whole tree)

Steps:

- [ ] **Step 1: `git rm` each path above.** (publish.json: the artifacts it declared are still on disk in `.claude/hooks/`, `.claude/commands/`, `.claude/skills/`; they will be re-asserted by Task 4's install loop. The new dispatchers replace the old hooks, so existing `.claude/hooks/{refresh,sync-check,session-init}.py` need to be re-deployed → these will be removed by `publish_hook` for the new dispatcher names but the OLD names remain until manually deleted.)

- [ ] **Step 2: Manually delete `.claude/hooks/{refresh,sync-check,session-init}.py`** from the deployed surface — they are no longer published by any manifest entry, so they would become orphans. Remove them, then also rewrite `.claude/settings.json` to remove their registrations (or run the install loop, which will register the NEW dispatchers; manually drop the old entries since publish_hook never removes prior entries).

  Plan: after the publish loop runs in Task 4 verification, run a one-time cleanup that drops legacy `.claude/hooks/{refresh,sync-check,session-init}.py` paths from `.claude/settings.json hooks.*` arrays. Implement as a tiny sanitizer step at the END of `install.py run_publish_loop` (3-4 lines hard-coded against the three legacy basenames) OR do it manually now.

  Decision: do the sanitization manually now (this is a one-time migration cost; the user already accepted no backwards-compat).

- [ ] **Step 3: Verify nothing references the deleted files** by grep:
  ```bash
  grep -RIn 'sync-check\|session-init\|refresh\.py\|generate-claude-md\|build\.py' .claude/features/rabbit-cage/ docs/ install.py 2>&1 | grep -v '\.pyc' | grep -v 'plans/'
  ```
  Any matches outside docs/plans/ require fixing.

- [ ] **Step 4: Commit.**
  ```bash
  git add -A .claude/features/rabbit-cage/
  git commit -m "chore(rabbit-cage): delete superseded hooks, scripts, publish.json, rabbit-config skill (Plan C task 5)"
  ```

---

## Task 6: Spec rewrite

**Files:** rewrite `.claude/features/rabbit-cage/docs/spec/spec.md`. Update `.claude/features/rabbit-cage/docs/spec/contract.md` to reflect the new surface.

### Target structure

Per the housekeeping protocol audit criteria, the new spec must be:

- Current-design only — no historical migration prose, no "per BUG-N"
- ~150 lines, 10–20 invariants
- Strict, confined, precise, focused, clear, well-written

**Outline:**

```markdown
---
feature: rabbit-cage
version: 5.0.0
owner: rabbit-workflow team
template_version: 2.0.0
deprecation_criterion: when Claude Code exposes native event dispatchers and artifact publishing that subsume this role
status: active
---

# rabbit-cage — Spec

## Purpose
rabbit-cage is the service dispatcher of the rabbit workflow. It exposes
four Claude Code event hooks (PreToolUse, Stop, SessionStart,
UserPromptSubmit) and a bootstrap installer. The three event dispatchers
enumerate every feature's `feature.json runtime[<event>]` declarations
and invoke each declared API via `contract.lib.runtime`; the installer
enumerates every feature's `feature.json manifest` and invokes each call
via `contract.lib.publish`. PreToolUse is owned outright by the
`scope-guard.py` hook.

## Surface
- `.claude/hooks/scope-guard.py` (PreToolUse)
- `.claude/hooks/stop-dispatcher.py` (Stop)
- `.claude/hooks/session-start-dispatcher.py` (SessionStart)
- `.claude/hooks/user-prompt-submit-dispatcher.py` (UserPromptSubmit)
- `.claude/settings.json` (Claude Code config; hook registrations)
- `CLAUDE.md` (regenerated via `generate-claude-md` producer)
- `README.md`, `install.py` (committed copies in the deployed workspace)
- `.claude/commands/rabbit-refresh.md`, `.claude/commands/rabbit-project.md`

## Meta-contract declarations
rabbit-cage declares its full MANIFEST / RUNTIME / CONFIGURATION in
`feature.json`. The dispatchers and installer consume those declarations
on the same code path as every other feature's declarations; rabbit-cage
holds no special-case integration logic for its own surface.

## Invariants

### Dispatcher behavior
1. Each event dispatcher (`stop-dispatcher.py`, `session-start-dispatcher.py`,
   `user-prompt-submit-dispatcher.py`) enumerates every feature directory under
   `.claude/features/` in alphabetical order, skips retired features, and invokes
   each entry in `feature.json runtime[<event>]` in declaration order.
2. For each entry `{api, args}`, the dispatcher invokes
   `contract.lib.runtime.<api>(**args, repo_root=<root>, feature_dir=<fdir>)`
   (feature_dir is forwarded only to APIs whose signature declares it).
3. Each dispatcher emits AT MOST ONE JSON object to stdout per invocation.
   `print` results are joined into `systemMessage` via `rabbit_block`; `inject`
   results are concatenated into `additionalContext`. `ok` results are dropped;
   `error` results are written to stderr and never surfaced. When no
   non-ok/non-error result is present, the dispatcher emits nothing (exit 0).

### Installer behavior
4. `install.py` first copies the source tree into TARGET, then enumerates every
   `<TARGET>/.claude/features/*/feature.json` in alphabetical order, skips
   retired features, and invokes each entry in `manifest` via
   `contract.lib.publish.<api>(**args, feature_dir=<fdir>, repo_root=<TARGET>)`.
5. The publish loop continues past failures and exits non-zero if any call
   failed (failure: `CheckResult.passed` is False, or the named API does not
   exist, or the call raised an exception). Failures are written to stderr.

### scope-guard semantics (preserved)
6. `scope-guard.py` is the sole PreToolUse hook. It DENIES (exit 2) any
   write inside the repo root unless one of: (a) target basename is on the
   filename allowlist (`settings.local.json`, `.gitignore`, `.rabbit-scope-override`),
   (b) target path is under an allowlisted prefix (`.claude/bugs/`,
   `.claude/backlogs/`, `.rabbit/`) or matches the path pattern
   `.claude/features/<feature>/docs/spec/spec.md`, (c) an active scope marker
   covers the target (`.rabbit-scope-active` global or
   `.rabbit-scope-active-<feature>` per-feature), or (d) a
   `.rabbit-scope-override` file at repo root with content `session` or
   `one-time` is present (the `one-time` form is consumed on read into
   `.rabbit-scope-override-used`).
7. When a per-feature or global scope marker names a feature that
   `find-feature.py` cannot resolve, `scope-guard.py` DENIES with a message
   naming the unresolvable feature.
8. When `scope-guard.py` reaches the default-deny path, the stderr message
   presents three explicit options: SESSION OVERRIDE, ONE-TIME OVERRIDE, and
   USE rabbit-feature-touch. Both override options require explicit
   in-conversation user confirmation before any marker is written;
   `scope-guard.py` itself never creates `.rabbit-scope-override`.
9. `scope-guard.py` is quote-aware: `extract_bash_targets()` strips
   single-quoted and double-quoted regions (the double-quote pass uses
   `re.DOTALL` for multi-line strings) from the full command string BEFORE
   splitting on `;|&` segment delimiters. The first quote-strip pass also
   removes heredoc bodies (matching both `<<` and `<<-` forms).

### Runtime artifacts
10. The following runtime markers are written under repo root and MUST be
    listed in `.gitignore`: `.rabbit-scope-active`, `.rabbit-scope-active-*`,
    `.rabbit-scope-override`, `.rabbit-scope-override-used`,
    `.rabbit-skills-updated`, `.rabbit-human-approval-bypass`,
    `.rabbit-prompt-counter`.
11. `scope-guard-on.py` at `scripts/scope-guard-on.py` is the operator-facing
    revoke: deletes `.rabbit-scope-override` if present and prints
    confirmation. No-op if absent.

### Tech stack
12. Every script under `hooks/` and `scripts/` is a standalone executable
    Python 3 file (`#!/usr/bin/env python3`), stdlib only. No `.sh` files
    appear in the rabbit-cage feature directory. Tests under `test/` are
    Python (`.py`); no `.sh` test files.

### Version alignment
13. `feature.json`, `docs/spec/spec.md` frontmatter, and `docs/spec/contract.md`
    frontmatter MUST declare the same `version`. Three-way drift is a
    constitution violation; the alignment is enforced by
    `test/test-version-alignment.py`.
```

(The above is the spec content target — Task 6 step 1 writes it; subsequent steps verify.)

### Steps

- [ ] **Step 1: Write the new spec.md** (overwrite). Verify YAML frontmatter parses.

- [ ] **Step 2: Update contract.md** to reflect the new `provides` (hooks: scope-guard.py, stop-dispatcher.py, session-start-dispatcher.py, user-prompt-submit-dispatcher.py; scripts: scope-guard-on.py, repo-permissions.py, rabbit-project*.py, workspace-tree.py). Bump its frontmatter version to `5.0.0`.

- [ ] **Step 3: Commit.**
  ```bash
  git add .claude/features/rabbit-cage/docs/spec/spec.md .claude/features/rabbit-cage/docs/spec/contract.md
  git commit -m "docs(rabbit-cage): rewrite spec to minimal-scope dispatcher service (Plan C task 6)"
  ```

---

## Task 7: Test suite rewrite

**Files:** rewrite `test/run.py`; delete most existing tests; create new spec-driven tests.

### Tests to DELETE (no longer apply after rewrite)

Effectively every test EXCEPT the scope-guard tests and a few foundational ones. Concretely DELETE:

- `test-claude-md.py`, `test-claude-md-header.py`, `test-generate-claude-md.py`
- `test-hook-enforcement.py`, `test-generated-surface.py`, `test-build-non-git-dir.py`
- `test-rabbit-cage-bug-96-surface-shape.py`, `test-split-validation.py`
- `test-RABBIT-CAGE-15-workspace-tree.py`, `test-RABBIT-CAGE-16-first-stop-no-false-drift.py`, `test-RABBIT-CAGE-17-quoted-strings.py` (move keep — quote tests are scope-guard tests; see KEEP below), `test-RABBIT-CAGE-21-plugin-change-alert.py`, `test-RABBIT-CAGE-22-stale-marker.py`
- All `test-RABBIT-CAGE-BACKLOG-*` files
- All `test-RABBIT-CAGE-BACKLOG18-*`, `BACKLOG-19-*`, `BACKLOG-20-*`, `BACKLOG-21-*`, `BACKLOG-22-*`, `BACKLOG-23-*`, `BACKLOG-25-*` (housekeeping), `BACKLOG-27-*`, `BACKLOG-28-*`
- `test-RABBIT-CAGE-WAVE*.py`
- `test-RABBIT-CAGE-BUG10-*`, `BUG123`, `BUG4`, `BUG89`, `BUG-97-*` (BUG-97 rabbit-config naming test goes with rabbit-config skill move-out)
- `test-no-embedded-python3.py`, `test-python-migration.py`
- `test-BACKLOG-11-rabbit-config-skill.py`, `test-rabbit-config.py`, `test-rabbit-config-permissions.py`, `test-RABBIT-CAGE-rabbit-config-help.py`, `test-rabbit-config-section-monotonic.py`
- `test-rabbit-workspace-map-wiring.py`, `test-team-wide-permissions.py`
- `test-rabbit-cage-scripts-enumeration.py`, `test-contract-provides-scripts-exist.py`
- `test-bug-95-skillmd-paths-resolve.py`, `test-backlog-27-runtime-flags-display.py`
- `test-POLICY-BACKLOG-1-session-init-branch.py`
- `test-RABBIT-CAGE-19-confirm-token-override.py` — keep as scope-guard test (delete or move to KEEP — see below)
- `test-RABBIT-CAGE-18-scope-alert-messages.py` — alert messages moved into RUNTIME declarations; tests now belong to dispatcher tests. Delete this one; coverage is in test-dispatchers.py.
- `test_helpers.py` if no remaining test uses it (audit at the end)

### Tests to KEEP (scope-guard surface, preserved by Plan C)

- `test-scope-guard-centralized.py`
- `test-scope-guard-allowlist.py`
- `test-scope-guard-deny-message.py`
- `test-scope-guard-rabbit-allowlist.py`
- `test-scope-per-feature-marker.py`
- `test-RABBIT-CAGE-BACKLOG10-override.py` (override marker semantics)
- `test-RABBIT-CAGE-17-quoted-strings.py` (quote-aware bash extraction)
- `test-RABBIT-CAGE-19-confirm-token-override.py` (three-option deny message)
- `test-repo-permissions.py` (repo-permissions script kept for `permissions lock|unlock`)
- `test-structure.py` (audit if it still applies to rabbit-cage's file layout; trim invariants that no longer hold; otherwise delete)

### Tests to CREATE

- `test-dispatcher-lib.py` (from Task 1)
- `test-dispatchers.py` (from Task 2)
- `test-install-publish-loop.py` (from Task 4)
- `test-version-alignment.py` (replaces `test-rabbit-cage-version-alignment.py`, kept as `test-version-alignment.py` for simpler name)
- `test-feature-json-validity.py` (new): parse rabbit-cage/feature.json, assert it has `manifest`, `runtime`, `configuration` keys typed as list/dict/list respectively, and every declared `api` exists in the appropriate `contract.lib.{publish,runtime,mutation}` module.

### Steps

- [ ] **Step 1: Audit existing tests** against the KEEP / DELETE list above by running each KEEP candidate first and confirming it passes. Trim assertions in `test-structure.py` if needed.

- [ ] **Step 2: Delete the DELETE list** via `git rm`.

- [ ] **Step 3: Write `test-version-alignment.py`** — reads feature.json, spec.md frontmatter, contract.md frontmatter; asserts all three `version` fields match. Run → PASS (assuming Task 3 and Task 6 used the same version).

- [ ] **Step 4: Write `test-feature-json-validity.py`** per spec above. Run → PASS.

- [ ] **Step 5: Rewrite `test/run.py`** to enumerate the new SUITES list:
    - test-scope-guard-centralized.py
    - test-scope-guard-allowlist.py
    - test-scope-guard-deny-message.py
    - test-scope-guard-rabbit-allowlist.py
    - test-scope-per-feature-marker.py
    - test-RABBIT-CAGE-BACKLOG10-override.py
    - test-RABBIT-CAGE-17-quoted-strings.py
    - test-RABBIT-CAGE-19-confirm-token-override.py
    - test-repo-permissions.py
    - test-structure.py (if kept)
    - test-dispatcher-lib.py
    - test-dispatchers.py
    - test-install-publish-loop.py
    - test-version-alignment.py
    - test-feature-json-validity.py

- [ ] **Step 6: Run `test/run.py`** → all pass.

- [ ] **Step 7: Commit.**
  ```bash
  git add .claude/features/rabbit-cage/test/
  git commit -m "test(rabbit-cage): trim suite to spec-only coverage; add dispatcher/install tests (Plan C task 7)"
  ```

---

## Task 8: Final verification and push

- [ ] **Step 1: Run the full rabbit-cage test suite.** `python3 .claude/features/rabbit-cage/test/run.py` — all suites pass.

- [ ] **Step 2: Run the contract test suite** as a smoke check that the API libs we depend on are still healthy. `python3 .claude/features/contract/test/run.py` — should be green (we did not touch contract).

- [ ] **Step 3: Revoke scope override.**
  ```bash
  python3 .claude/features/rabbit-cage/scripts/scope-guard-on.py
  ```

- [ ] **Step 4: Push to integration branch.**
  ```bash
  git push origin feature/meta-contract-api-libraries
  ```

- [ ] **Step 5: Capture report data** for the final wave output: status, commit list, files changed counts, test suite state, B/B items filed, audit verdict per criterion.

---

## Notes on alongside findings

Per the housekeeping protocol B/B filing rule: any issue detected OUTSIDE rabbit-cage's scope during this wave (e.g., a contract API misbehavior, a bug in a Plan B library) MUST be filed via `rabbit-file` rather than fixed inline. Maintain a running list during execution and flush at the wave end before reporting status.

If a contract API bug blocks completion, return `blocked` status with the B/B reference; do NOT modify contract code.
