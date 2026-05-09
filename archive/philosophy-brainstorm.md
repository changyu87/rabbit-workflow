# Philosophy: Brainstorm — Potential Additions

This document brainstorms what `/home/cyxu/philosophy.md` might be missing.
The existing three principles are:

1. Script Over Token: `script > CLI > spec > prompt`
2. AI Over Human (machine-first state and contracts)
3. Isolated Contract Interface (bounded scope, no boundary crossing)

Each candidate below is judged on whether it covers ground the existing three
do not. The philosophy aspires to be the workflow equivalent of the Three Laws
— so additions must be foundational, not tactical.

---

## Candidate 1: Reversibility Before Action
**Covers:** Blast radius and recoverability — the missing "consequence" axis
that none of the three principles addresses (Hole 22, Hole 46). Today the
hierarchy ranks predictability but is silent on what happens when the
predictably-wrong thing runs.
**Proposed wording:**
> Every action is preceded by a reversibility check. Prefer reversible
> operations; for irreversible ones, require explicit human confirmation, an
> undo path, or a recovery plan. Predictability without recoverability is not
> safety.
**Strength:** Names the consequence dimension the existing principles
ignore. Pairs naturally with Principle 1 (a script that can `rm -rf` is not
"safer" than a prompt that drafts a file). It is also the principle that lets
the hierarchy be relaxed safely: low-blast-radius tasks may use AI freely.
**Weakness:** Could be read as merely operational ("review before deploy") and
demoted to a checklist rather than a law. Risk of overlap with general
engineering practice.
**Verdict:** include — as Principle 4. This is the largest missing axis.

---

## Candidate 2: Auditability of Every Decision
**Covers:** Provenance, observability of AI decisions, schema versioning,
trust between components (Holes 12, 27, 29, 39). The existing principles say
nothing about *evidence* — what was decided, by whom (or what model), when,
and why.
**Proposed wording:**
> Every consequential decision — by human, script, or model — leaves a
> machine-readable record of input, output, actor, version, and timestamp,
> sufficient to reproduce or contest it.
**Strength:** Closes the loop on Principle 2 (machine-first state must include
machine-first *history*). Makes Principle 1's "AI last" optional rather than
necessary, because AI use becomes auditable. Addresses security, debugging,
and model-version drift in one stroke.
**Weakness:** Easily mistaken for "just add logging." Hard to enforce
uniformly without runtime support.
**Verdict:** include — as Principle 5. Without this, the other principles
cannot be inspected or improved.

---

## Candidate 3: Human Override With Cause
**Covers:** Hole 26 (no escape hatch), Hole 10 (3 a.m. emergencies),
Hole 33 (slippery slope to total automation). Acknowledges that the codified
rules will sometimes be wrong, and provides a sanctioned mechanism for
overriding them.
**Proposed wording:**
> Any principle here may be overridden by a human, on the record, with stated
> cause. The override and the cause become part of the audit trail.
**Strength:** Prevents the philosophy from ossifying into dogma. Names the
human as the final authority without contradicting "AI Over Human" (which is
about consumption, not authority).
**Weakness:** Risks being abused as a permanent loophole. Overlaps with
Candidate 2 (override-with-cause is a special case of auditable decision).
**Verdict:** merge-with-existing — fold into Candidate 2 (Auditability),
since "override on the record" is just an audited human decision. Do not
spend a principle slot on it.

---

## Candidate 4: Cost-Aware Tier Selection
**Covers:** Holes 3, 23, 30, 43 — the missing economic axis. The hierarchy
is consequence-blind in dollars, time, and engineer-hours.
**Proposed wording:**
> Tier selection accounts for total cost: build, run, maintain, and
> opportunity. Choose the lowest tier whose cost is justified by the task's
> value and lifetime.
**Strength:** Patches the most common failure of strict adherence to
Principle 1 (over-engineering one-shot tasks). Recognizes amortization.
**Weakness:** Vague — "justified" requires judgment that the philosophy
otherwise tries to remove. May be better expressed as a *clarification* of
Principle 1 than as a separate law.
**Verdict:** merge-with-existing — annotate Principle 1 with cost as a
tiebreaker, rather than promote to its own law. The Three Laws of Robotics
do not include "and be cost-effective."

---

## Candidate 5: Bounded Autonomy
**Covers:** Hole 46 — when AI *is* used (Principle 1's lowest tier), how far
may it go? Today the philosophy is silent: "AI last" is not the same as "AI
bounded."
**Proposed wording:**
> Every actor — script, AI, human — operates with explicit authority limits:
> what it may read, what it may write, what it may invoke, and where human
> approval is required. No actor exceeds its declared authority.
**Strength:** Generalizes beyond AI: scripts also need authority limits
(a script with sudo is more dangerous than a prompt without it). This makes
it a *systemic* principle rather than an AI-specific one. Closes the security
hole (Hole 31) by demanding least-privilege as a first-class concern.
**Weakness:** Strong overlap with Principle 3 (Isolated Contract). One could
argue authority limits are just another contract. But Principle 3 is about
*communication* boundaries; this is about *capability* boundaries — a real
distinction.
**Verdict:** include — as Principle 6, OR fold into a tightened Principle 3
that covers both communication and capability. Author's choice; either way
the substance must be added.

---

## Candidate 6: Evolution and Versioning of Contracts
**Covers:** Hole 12, Hole 39 — schemas evolve, and the philosophy itself
evolves. No story exists for either.
**Proposed wording:**
> Every contract carries a version. Changes are additive by default;
> breaking changes require a deprecation window during which old and new
> coexist. The philosophy itself is versioned and amendable on the record.
**Strength:** Without versioning, "fixed-format schemas" is an anchor, not
an asset. Pairs with Auditability.
**Weakness:** Operational rather than philosophical. Could be a corollary of
Principle 3 rather than its peer.
**Verdict:** merge-with-existing — bake into Principle 3 as a clarifying
clause. Do not spend a principle slot on versioning mechanics.

---

## Candidate 7: Feedback Loops and Measurement
**Covers:** Hole 41 — no mechanism for the philosophy to detect when it is
wrong. Without measurement, the principles are unfalsifiable.
**Proposed wording:**
> Outcomes are measured. The principles are evaluated against measured
> outcomes on a fixed cadence and revised when evidence demands it.
**Strength:** Keeps the philosophy alive. Distinguishes engineering ethic
from religion.
**Weakness:** Meta-principle, not object-level. Belongs in a preamble or
governance section rather than as a peer law.
**Verdict:** exclude as a numbered principle; include as a *governance
clause* of the document.

---

## Candidate 8: Determinism Is a Property, Not a Tier
**Covers:** Hole 1, Hole 25, Hole 57 — the conflation of "AI" with
"non-deterministic" and "script" with "deterministic."
**Proposed wording:**
> Determinism, verifiability, and reversibility are properties of an
> implementation, not of its medium. Rank by measured properties, not by
> medium.
**Strength:** Repairs the central category error of Principle 1.
**Weakness:** Effectively *replaces* Principle 1 rather than adds to it.
**Verdict:** merge-with-existing — rewrite Principle 1 to rank by properties
(determinism, verifiability, reversibility, cost) rather than by medium
(script/CLI/spec/prompt). Same spirit, defensible foundation.

---

## Candidate 9: Human Legibility Floor
**Covers:** Holes 10, 13, 33 — the missing lower bound on human readability.
Machine-first must not become human-impossible.
**Proposed wording:**
> Every machine-first artifact has a human-legible projection — a script,
> a CLI flag, a default rendering — available without prerequisite tooling.
> Machine-first does not mean human-locked-out.
**Strength:** Restores on-call viability, onboarding, and emergency
debugging. Resolves the most-cited objection to Principle 2.
**Weakness:** Could be folded into Principle 2 as a clarifying clause rather
than a peer law.
**Verdict:** merge-with-existing — amend Principle 2 to require a legibility
floor. Principle 2 currently overshoots; this rebalances it without adding
a slot.

---

## Candidate 10: Trust Boundaries and Provenance
**Covers:** Holes 27, 31, 36 — security, supply chain, multi-party systems.
**Proposed wording:**
> Every input is treated as untrusted unless its provenance is proven.
> Authority is granted to identities, not to channels. No contract is honored
> without authentication of its counterparty.
**Strength:** Brings the document into the security era. Makes Principle 3
robust against adversarial peers.
**Weakness:** Heavy domain language; risks being read as "do AuthN/AuthZ"
rather than as a workflow ethic.
**Verdict:** merge-with-existing — fold into Candidate 5 (Bounded Autonomy)
or Principle 3. Trust is the precondition for all the others; it does not
need its own slot if Bounded Autonomy is admitted.

---

## Candidate 11: Failure Is a First-Class Output
**Covers:** Holes 11, 28, 42, 52 — error payloads, retry/idempotency,
ordering, graceful degradation.
**Proposed wording:**
> Every contract specifies success and failure with equal rigor. Errors
> carry diagnostic payload. Retries are idempotent. Partial failure is a
> declared state, not an undefined one.
**Strength:** Patches the largest practical gap in Principle 3 — contracts
today are written as happy-path schemas.
**Weakness:** Operational rather than philosophical. Belongs as an annotation
to Principle 3.
**Verdict:** merge-with-existing — extend Principle 3.

---

## Candidate 12: Stated Purpose / Named Enemy
**Covers:** Holes 21, 50, 60 — no precedence between principles, no stated
goal, no named enemy.
**Proposed wording (preamble, not a numbered principle):**
> The purpose of this philosophy is [reliability under change / velocity
> without regret / safe autonomy]. When principles conflict, choose the
> action that best serves this purpose. The enemy is [drift / silent
> failure / unbounded coupling]; principles are tightened against it.
**Strength:** Resolves the most damaging holes — precedence, arbitration,
intent — at zero cost in numbered slots.
**Weakness:** Requires the author to commit to a single purpose, which they
may have deliberately left open.
**Verdict:** include — as a preamble. This is the highest-leverage edit
available. A philosophy with a stated purpose can absorb future principles
coherently; one without will fragment.

---

## Final Recommendation

Add at most **two** numbered principles, plus a preamble. The Three Laws
work because they are few and ordered. A six-principle document loses force.

Proposed final shape:

- **Preamble (Candidate 12):** stated purpose, named enemy, precedence rule.
- **Principle 1 (revised, Candidate 8):** rank by properties — determinism,
  verifiability, reversibility, cost — not by medium. Keep
  `script > CLI > spec > prompt` as a heuristic, not a law.
- **Principle 2 (revised, Candidate 9):** machine-first with a human
  legibility floor.
- **Principle 3 (revised, Candidates 6 + 11):** isolated, versioned, with
  failure as first-class.
- **Principle 4 (Candidate 1):** Reversibility Before Action.
- **Principle 5 (Candidate 2 + 3 + 10):** Auditability and Bounded Authority
  — every consequential decision is recorded; every actor operates within
  declared authority; overrides are on the record.

Five principles, one preamble, no orphan concerns. This is the mountain
no other mountain exceeds.

---
