---
feature: contract
version: 1.0.0
owner: rabbit-workflow team
deprecation_criterion: when the native-Workflow coexistence verdict is superseded by a contract feature-touch adopting a native governance-tier mechanism — at which point this record folds into that touch's CHANGELOG entry
status: accepted
---

# Decision: Coexist with Claude Code's native Workflow framework

## Status

Accepted. This is the written deliverable of the native-Workflow research
spike: study Claude Code's native `Workflow` orchestration tool and decide
whether rabbit-workflow should collapse into it, merge partially, coexist,
or stay independent.

## Context

Claude Code now ships a native `Workflow` orchestration tool: deterministic
JS scripts with `meta`/`phases`, `agent()` calls returning structured
`schema` outputs, `pipeline()`/`parallel()` composition, a `budget` cap,
`workflow()` nesting, worktree isolation, resume-from-journal, and an agent
registry with custom `agentType`. The hypothesis to test was that this native
mechanism shares enough structural DNA with rabbit — a dispatcher
orchestrating subagents, machine-first structured handoffs, phased execution,
determinism-first — that rabbit could be retired into it.

The investigation decomposes rabbit into two tiers:

- **Orchestration tier** — how work is dispatched, fanned out, phased,
  isolated, and resumed. This is what native Workflow provides.
- **Governance tier** — the guarantees that make rabbit's output
  *trustworthy*: the cross-feature contract gate, four-way version lockstep,
  contiguous invariant numbering, schema/template ownership, scope-guard
  PreToolUse enforcement, drift detection, policy re-injection, and
  designed-deprecation/ownership metadata. This is what native Workflow does
  NOT provide.

## Primitive-by-primitive mapping

| Claude Code Workflow primitive | rabbit concept | Native analog? |
| --- | --- | --- |
| `Workflow` tool (JS script, `meta`/`phases`) | dispatcher orchestration (the main session driving feature/bug/backlog work) | YES — orchestration tier |
| `agent()` + structured `schema` output | tdd-subagent dispatch + the fixed HANDOFF block | PARTIAL — native gives schema'd output; rabbit's 8-step TDD cycle (LOCK→…→UNLOCK) is rabbit-specific discipline layered on top |
| `pipeline()` / `parallel()` | sequential / concurrent feature touches | YES — orchestration tier |
| `budget` | (no direct rabbit equivalent; rabbit bounds by feature scope, not token budget) | NATIVE-ONLY |
| `workflow()` nesting | (rabbit forbids two-level subagent nesting; main → N parallel subagents only) | DIVERGENT — rabbit deliberately constrains what native allows |
| worktree isolation | per-subagent git worktree isolation | YES — rabbit already uses worktrees; native makes it first-class |
| resume-from-journal | (no rabbit equivalent; rabbit re-derives state from feature.json `tdd_state`) | NATIVE-ONLY (a possible future borrow) |
| agent registry / custom `agentType` | the tdd-subagent agent definition + publish system | PARTIAL — native registers agents; rabbit's `feature.json` manifest/publish governs *deployment* of skills/agents/commands with drift checks |
| (none) | `feature.json` manifest + publish/drift system | NO native analog — governance |
| (none) | runtime hooks (Stop/SessionStart/UserPromptSubmit/PreToolUse) | NO native analog — governance |
| (none) | scope-guard PreToolUse enforcement (scope-protected files, scope markers) | NO native analog — governance |
| (none) | policy re-injection (CLAUDE.md / coding-rules / philosophy / spec-rules) | NO native analog — governance |
| (none) | contract schemas + templates + cross-feature contract gate | NO native analog — governance |
| (none) | contiguous invariant numbering + four-way version lockstep | NO native analog — governance |
| (none) | drift detection (manifest drift, deployed-copy drift, generated-doc drift) | NO native analog — governance |
| (none) | designed-deprecation / ownership metadata (owner, version, deprecation_criterion) | NO native analog — governance |

The pattern is consistent: native Workflow covers the orchestration tier well
and even exceeds rabbit in places (`budget`, journaled resume). It has NO
equivalent for any governance-tier concept — precisely the surface contract
owns.

## Recommendation

**HYBRID / COEXIST.** Adopt nothing wholesale now. Treat native Workflow as
the orchestration tier and keep rabbit's governance layer intact. Concretely:

- Do NOT migrate the dispatcher, tdd-subagent, manifest/publish, or hook
  system onto native Workflow at this time.
- Native Workflow's determinism primitives (`pipeline`/`parallel`, journaled
  resume, first-class worktree isolation) are attractive but are a moving
  target on a brand-new harness feature; migrating core machinery onto it now
  trades rabbit's locatable-failure guarantees (script > CLI > spec > prompt)
  for upstream churn risk.
- The decisive asymmetry: collapsing rabbit into native Workflow would drop
  the governance guarantees that distinguish rabbit (scope-guard, drift
  detection, policy re-injection, contract gate, lockstep, ownership
  metadata) for which native has no analog. The cost (a non-trivial rewrite)
  buys a loss, not a gain.

This verdict is already reflected in contract's `deprecation_criterion`,
which was refined to fire only "when Claude Code exposes a native mechanism
that supersedes contract's governance surface … not merely when a native
orchestration/workflow primitive exists."

## Way IN (adoption trigger)

Flip toward adoption when native Workflow exposes a **governance-superseding**
mechanism — exactly the condition contract's `deprecation_criterion` names.
Specific triggers, any of which warrants re-evaluation:

- Native exposes an enforced cross-component contract/gate mechanism (typed,
  validated boundaries) that subsumes the contract gate and version lockstep.
- Native exposes scope-protection / PreToolUse-style enforcement and drift
  detection equivalent to scope-guard and the manifest/publish drift checks.
- Native exposes ownership/lifecycle metadata and policy-injection guarantees
  equivalent to rabbit's designed-deprecation surface.

A safe, high-value *first* hybrid step that does NOT require any governance
concession: pilot a single rabbit orchestration path (e.g. the TDD
fan-out) expressed as a native `Workflow` script while the governance layer
(scope-guard, contract gate, feature.json lockstep) runs unchanged around it.
This is tracked as a separate follow-up rather than executed here.

## Way OUT (off-ramp / rollback)

Because this decision adopts nothing, the off-ramp is trivial: the status quo
is the rollback. If a future hybrid pilot (the way-in first step) proves the
native mechanism unstable or governance-incompatible, abandon the pilot — the
dispatcher, tdd-subagent, and hook system remain the source of truth and need
no migration back. No data or contract surface is ceded by this decision, so
there is nothing to reverse. The trigger to exercise the off-ramp: a piloted
native-Workflow path fails the contract gate, breaks scope-guard enforcement,
or cannot carry ownership/lifecycle metadata.

## Follow-up

A follow-up enhancement captures the chosen path (coexist now; re-evaluate
when native exposes governance-tier primitives, and optionally pilot the
orchestration-only hybrid first step). See the follow-up issue referenced in
this change's CHANGELOG entry and PR.
