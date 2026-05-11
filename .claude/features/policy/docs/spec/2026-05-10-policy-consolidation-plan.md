# Policy Consolidation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Strip exception clauses and enforcement cross-references from `workflow-rules.md` so policy is purely instructive — principles only, no operational carve-outs.

**Architecture:** Single-file edit to `workflow-rules.md` plus a new test file. All other policy files (`philosophy.md`, `spec-rules.md`, `coding-rules.md`) are already clean and untouched. Full TDD cycle via the rabbit workflow: force test-red → write failing test → confirm red → impl → confirm green → commit.

**Tech Stack:** Bash, rabbit TDD state machine (`tdd-step.sh`), scope-guard (`.rabbit-scope-active` marker).

---

## Files

| Action | Path | Responsibility |
|--------|------|----------------|
| Modify | `.claude/features/policy/workflow-rules.md` | Remove exception blocks and compress R1–R9 |
| Create | `.claude/features/policy/test/test-policy-consolidation.sh` | Assert absence of exception prose and script paths |
| Modify | `.claude/features/policy/test/run.sh` | Wire new test into the suite |

---

### Task 1: Force TDD state to test-red

**Files:** `.claude/features/policy/feature.json` (via tdd-step.sh)

- [ ] **Step 1: Force policy feature to test-red**

```bash
REPO_ROOT=$(git rev-parse --show-toplevel)
bash "$REPO_ROOT/.claude/features/tdd-state-machine/scripts/tdd-step.sh" \
  transition "$REPO_ROOT/.claude/features/policy" test-red --force
```

Expected output: `FORCED: test-green -> test-red`

- [ ] **Step 2: Set scope marker**

```bash
echo "policy" > "$REPO_ROOT/.rabbit-scope-active"
```

---

### Task 2: Write the failing test

**Files:**
- Create: `.claude/features/policy/test/test-policy-consolidation.sh`

- [ ] **Step 1: Write test file**

```bash
cat > "$REPO_ROOT/.claude/features/policy/test/test-policy-consolidation.sh" << 'TESTEOF'
#!/usr/bin/env bash
# test-policy-consolidation.sh
# Asserts workflow-rules.md contains no exception prose or script-path refs.
set -u

REPO_ROOT="$(git -C "$(dirname "${BASH_SOURCE[0]}")" rev-parse --show-toplevel)"
WF="$REPO_ROOT/.claude/features/policy/workflow-rules.md"
FAILURES=0

ok()   { echo "  PASS t$1: $2"; }
fail() { echo "  FAIL t$1: $2"; FAILURES=$((FAILURES + 1)); }

echo "test-policy-consolidation.sh"
echo ""

# t1: no 'Exception' keyword (capital E — marks exception carve-outs)
if ! grep -q 'Exception' "$WF"; then
    ok 1 "workflow-rules.md contains no 'Exception' clause"
else
    fail 1 "workflow-rules.md still contains 'Exception' — remove exception prose"
fi

# t2: no 'Exceptions' keyword (plural — marks the exceptions block header)
if ! grep -q 'Exceptions' "$WF"; then
    ok 2 "workflow-rules.md contains no 'Exceptions' block"
else
    fail 2 "workflow-rules.md still contains 'Exceptions' block — remove it"
fi

# t3: no 'enforced by scope-guard' — operational enforcement noise
if ! grep -q 'enforced by scope-guard' "$WF"; then
    ok 3 "workflow-rules.md contains no 'enforced by scope-guard' reference"
else
    fail 3 "workflow-rules.md still references scope-guard enforcement — remove it"
fi

# t4: no script paths (check-no-main-edits.sh is the canary)
if ! grep -q 'check-no-main-edits' "$WF"; then
    ok 4 "workflow-rules.md contains no script paths"
else
    fail 4 "workflow-rules.md still contains script paths in R1–R9 — compress to one-liners"
fi

# t5: R1 is present as a one-liner
if grep -q '^\- \*\*R1\*\*' "$WF"; then
    ok 5 "R1 present as one-liner bullet"
else
    fail 5 "R1 not found as one-liner bullet '- **R1**'"
fi

# t6: R9 is present as a one-liner
if grep -q '^\- \*\*R9\*\*' "$WF"; then
    ok 6 "R9 present as one-liner bullet"
else
    fail 6 "R9 not found as one-liner bullet '- **R9**'"
fi

# t7: 'Subagent-driven by construction' section still exists (no accidental deletion)
if grep -q '## Subagent-driven by construction' "$WF"; then
    ok 7 "'Subagent-driven by construction' section present"
else
    fail 7 "'Subagent-driven by construction' section missing — was it accidentally deleted?"
fi

# t8: 'Full TDD on every feature touch' section still exists
if grep -q '## Full TDD on every feature touch' "$WF"; then
    ok 8 "'Full TDD on every feature touch' section present"
else
    fail 8 "'Full TDD on every feature touch' section missing"
fi

echo ""
echo "Results: $((8 - FAILURES)) passed, $FAILURES failed"
if [ "$FAILURES" -eq 0 ]; then echo "ALL TESTS PASSED"; exit 0
else echo "$FAILURES TEST(S) FAILED"; exit 1
fi
TESTEOF
chmod +x "$REPO_ROOT/.claude/features/policy/test/test-policy-consolidation.sh"
```

- [ ] **Step 2: Run test — confirm it FAILS**

```bash
bash "$REPO_ROOT/.claude/features/policy/test/test-policy-consolidation.sh"
```

Expected: t1, t2, t3, t4, t5, t6 fail (t7, t8 pass — sections exist). Exit code 1.

---

### Task 3: Advance TDD state to impl

**Files:** `.claude/features/policy/feature.json` (via tdd-step.sh)

- [ ] **Step 1: Advance to impl**

```bash
bash "$REPO_ROOT/.claude/features/tdd-state-machine/scripts/tdd-step.sh" \
  transition "$REPO_ROOT/.claude/features/policy" impl
```

Expected output: `test-red -> impl`

---

### Task 4: Implement — edit `workflow-rules.md`

**Files:**
- Modify: `.claude/features/policy/workflow-rules.md`

Make four targeted edits. Read the file first, then apply each change surgically.

- [ ] **Step 1: Remove enforcement note from "Subagent-driven by construction"**

Find and remove this exact sentence (including the leading space and trailing newline):

```
This is not a convention — it is enforced by scope-guard (R8) and the sentinel check (R6).
```

The section body becomes a single sentence: "Every implementation touch goes through a dispatched subagent via `dispatch-feature-edit.sh`. The main session reads, decides, dispatches, and verifies. It does not write files."

- [ ] **Step 2: Remove Exceptions block from "Main Session Is a Dispatcher"**

Find and remove from the line `**Exceptions (direct calls allowed without subagent):**`
through the three bullet points beneath it (ending after the `Simple answers to questions that don't touch any file` line). Remove those lines entirely including any blank line separator above the block.

- [ ] **Step 3: Remove Exception sentence from "Full TDD on every feature touch"**

Find and remove this exact block (the blank line + the indented exception sentence):

```
  Exception: metadata-only writes (bug filing via file-bug.sh, backlog filing via file-backlog-item.sh) require schema compliance only — the scripts enforce format at write time. No TDD cycle needed for bookkeeping artifacts.
```

- [ ] **Step 4: Replace R1–R9 verbose entries with one-liners**

Replace the entire body of the `## Hard rules index (R1–R9)` section (from the `The rules below are operational add-ons...` preamble paragraph through `The full statement, rationale, and tests...` closing line) with:

```markdown
- **R1** — Branch per feature; never commit directly to main.
- **R2** — Use Opus for brainstorm, spec, plan, design, and architect subagents.
- **R3** — Tests are end-to-end and non-interactive — no `read` or `select`.
- **R4** — TDD state transitions go through `tdd-step.sh` only.
- **R5** — Features live anywhere; the same discipline applies everywhere.
- **R6** — Every Agent dispatch prepends the canonical policy block.
- **R7** — Vet every bug before closing — triage first, then close.
- **R8** — Every feature touch runs full TDD.
- **R9** — Project-level contract wins over rabbit contract at conflict.
```

---

### Task 5: Wire new test into run.sh

**Files:**
- Modify: `.claude/features/policy/test/run.sh`

- [ ] **Step 1: Add test-policy-consolidation.sh to the suite**

Read `run.sh` to find the pattern used to invoke other tests, then add:

```bash
bash "$SCRIPT_DIR/test-policy-consolidation.sh" || FAILURES=$((FAILURES + 1))
```

in the same style as existing test invocations.

---

### Task 6: Verify all tests pass

- [ ] **Step 1: Run the new test**

```bash
bash "$REPO_ROOT/.claude/features/policy/test/test-policy-consolidation.sh"
```

Expected: ALL 8 TESTS PASSED

- [ ] **Step 2: Run the full policy test suite**

```bash
bash "$REPO_ROOT/.claude/features/policy/test/run.sh"
```

Expected: no new failures.

---

### Task 7: Advance TDD to test-green and commit

- [ ] **Step 1: Advance to test-green**

```bash
bash "$REPO_ROOT/.claude/features/tdd-state-machine/scripts/tdd-step.sh" \
  transition "$REPO_ROOT/.claude/features/policy" test-green
```

Expected output: `impl -> test-green`

- [ ] **Step 2: Remove scope marker**

```bash
rm "$REPO_ROOT/.rabbit-scope-active"
```

- [ ] **Step 3: Stage and commit**

```bash
git add \
  .claude/features/policy/workflow-rules.md \
  .claude/features/policy/test/test-policy-consolidation.sh \
  .claude/features/policy/test/run.sh \
  .claude/features/policy/feature.json

git commit -m "refactor: strip exception prose from workflow-rules — policy as pure principle

Remove Exception/Exceptions blocks from Full TDD and Main Session sections.
Remove 'enforced by scope-guard' note from Subagent-driven section.
Compress R1-R9 from verbose paragraphs with script paths to single-line
rule statements. Scripts enforce exceptions at runtime; policy states principles.

Test: test-policy-consolidation.sh added (8/8); wired into run.sh."
```

- [ ] **Step 4: Push**

```bash
git push
```
