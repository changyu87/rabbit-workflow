# Philosophy: Logical Holes

A ruthless audit of `/home/cyxu/philosophy.md`. Each hole below is an attack
vector against the three principles:

1. Script Over Token: `script > CLI > spec > prompt`
2. AI Over Human (machine-first state and contracts)
3. Isolated Contract Interface (bounded scope, no boundary crossing)

---

## Hole 1: "Determinism" is undefined and overloaded
**Principle affected:** 1
**Description:** The principle equates "script" with "fully deterministic," but
real-world scripts are routinely non-deterministic: they read clocks, network
state, environment variables, file timestamps, RNGs, hash-iteration order,
parallel scheduling, cosmic-ray bit flips, flaky filesystems, and so on. A
script is no more inherently deterministic than an LLM call with `temperature=0`
and a fixed seed. The ranking pretends determinism is a property of the medium
when it is actually a property of the implementation.
**Scenario:** A "script" that calls `curl https://api.example.com` is ranked
above a `temperature=0, seed=42` LLM spec, despite the script being far less
reproducible across runs (network jitter, API drift, rate limits) than the LLM.
**Severity:** major

---

## Hole 2: Ranking ignores correctness, only ranks predictability
**Principle affected:** 1
**Description:** `script > CLI > spec > prompt` orders by determinism, not by
correctness. A deterministic wrong answer is preferred to a probabilistic right
answer. There is no principle that says "and the script must actually be
correct." Reproducible failure is celebrated as a virtue ("fails reproducibly")
but reproducible *wrongness* is the same thing dressed up.
**Scenario:** A regex-based parser (script) that mis-handles 8% of inputs is
chosen over an LLM that handles 99.9%. The script's failures are "locatable and
fixable" — but they are also more numerous and silent in production until
caught.
**Severity:** major

---

## Hole 3: Cost of building the script is not in the ranking
**Principle affected:** 1
**Description:** The hierarchy contains no notion of cost or amortization. A
one-shot exploratory task ("rename these 4 files based on their content") may
demand a 200-line script under a strict reading of the principle. The principle
gives no escape hatch for tasks where engineering cost vastly exceeds savings.
**Scenario:** Engineer needs to summarize three meeting notes for a one-off
email. Strict adherence: write a script, then a CLI, then a spec, only then a
prompt. Pragmatic answer: just prompt it. The principle as written prohibits the
pragmatic answer.
**Severity:** major

---

## Hole 4: "Script" can wrap a prompt, defeating the ranking
**Principle affected:** 1
**Description:** Any prompt can be put inside a `bash` script that calls an LLM
API. By the literal text of the rule, this is now a "script" and outranks a
"prompt." The classification is syntactic, not semantic, and trivially gameable.
**Scenario:** `claude_call.sh` is a 3-line wrapper over `anthropic` CLI. It is
nominally a script. By Principle 1 it is preferred over a direct prompt, even
though the AI involvement and predictability are identical.
**Severity:** major

---

## Hole 5: No principle for choosing *between* equally-ranked options
**Principle affected:** 1
**Description:** Two scripts may exist that both solve the problem; the
hierarchy gives no tiebreaker. Same for two CLIs. The ranking only orders
across tiers, not within. Engineers will reach opposite conclusions when picking
between, e.g., a 50-line bespoke script vs. a one-liner using an obscure CLI.
**Scenario:** Team A picks `awk` (CLI), Team B picks a Python script. Both
satisfy Principle 1. The philosophy provides no guidance and the teams diverge
permanently.
**Severity:** minor

---

## Hole 6: Spec is undefined; collapses into prompt
**Principle affected:** 1
**Description:** "Structured directives that tightly constrain what AI does" is
fuzzy. A prompt with bullet points and a JSON schema is a spec to one engineer
and a prompt to another. The threshold between spec and prompt is undefined,
making the third tier of the hierarchy unenforceable.
**Scenario:** Engineer writes a 400-word prompt with sections, examples, and an
output schema. Reviewer says "that's a spec." Author says "no, it's a prompt."
The philosophy cannot adjudicate.
**Severity:** major

---

## Hole 7: Principle 1 forbids the use of AI to write the script
**Principle affected:** 1, 2
**Description:** If the deterministic artifact is always preferred, and AI is
the lowest tier, then using AI to *generate* the script seems forbidden — yet
this is the modern workflow. The principle does not distinguish "AI in the loop
at runtime" from "AI in the loop at authoring time."
**Scenario:** Engineer asks Claude to write a script. Was Principle 1 violated
because a "prompt" was used, or honored because the result is a script?
Reasonable engineers split.
**Severity:** minor

---

## Hole 8: "Script" assumes a maintainer
**Principle affected:** 1
**Description:** "Code you own, version, and control" requires ongoing
maintenance. A script preferred today becomes a liability tomorrow when nobody
owns it. The principle has no decay model: scripts age, dependencies break,
ownership lapses. A six-year-old script can be *less* reliable than a fresh LLM
call.
**Scenario:** A 2019 Python 2 script is "preferred" by Principle 1 over a
prompt in 2026, even though the script no longer runs.
**Severity:** major

---

## Hole 9: AI Over Human contradicts AI-last in Principle 1
**Principle affected:** 1, 2
**Description:** Principle 2 designs every artifact for "machine consumption
first" — and the most capable, general-purpose machine consumer in 2026 is an
LLM. Principle 1 demotes LLMs to last resort. So we are designing all our state
files to be optimally consumed by the consumer we have ranked last. This is
internally incoherent: if we are confident enough in AI to make it the primary
audience, why are we afraid of it being the primary doer?
**Scenario:** Team designs JSON state files "for AI." Then refuses to let AI
read them at runtime, requiring a human-launched script in between. The state's
audience (AI) is not the actual reader (script).
**Severity:** critical

---

## Hole 10: "Machine-first" excludes the human in emergencies
**Principle affected:** 2
**Description:** When production is on fire at 3 a.m., a human needs to read
state *now* without first finding, understanding, and running a "script that
extracts and formats it." The principle as written makes the on-call engineer
strictly slower at the worst moment.
**Scenario:** Pager fires. Engineer SSHes in. State file is a 40MB protobuf
binary. Required formatter script lives in a repo on a different host. MTTR
balloons. A simple human-readable log line would have resolved the incident in
seconds.
**Severity:** critical

---

## Hole 11: Fixed-format schemas are rigid; reality is not
**Principle affected:** 2
**Description:** "Fixed-format schemas for every handoff — never free-form
text." This forbids the most informative payload of all: the unstructured error
message, the surprising stderr, the diagnostic trace. Real systems hit conditions
the schema designer never imagined; squeezing them into fixed fields drops the
information you most need.
**Scenario:** A subprocess crashes with a novel Rust panic. The schema has a
`status: "error"` enum and an `error_code: int`. The actual panic message —
which contains the only useful clue — has nowhere to go and is dropped.
**Severity:** major

---

## Hole 12: Schema versioning is unaddressed
**Principle affected:** 2, 3
**Description:** Fixed-format schemas evolve. The philosophy says nothing about
versioning, migration, backward compatibility, or how a v2 producer talks to a
v1 consumer. Without this, "fixed format" becomes "fixed forever or break
everything."
**Scenario:** Team adds a new required field to the contract. Old components
still emit v1; new components reject it. Whose fault per Principle 3? Both
honored their local contract.
**Severity:** major

---

## Hole 13: "Machine-first" blocks documentation and onboarding
**Principle affected:** 2
**Description:** New engineers cannot read protobuf binaries by eye. If every
artifact is machine-first, the cognitive ramp for humans is steep. The
principle does not budget for the human cost of pure machine-first design.
**Scenario:** New hire spends three days writing inspection scripts before they
can debug their first ticket, because no artifact is human-readable by default.
**Severity:** major

---

## Hole 14: Principle 2 conflates "structured" with "machine-readable"
**Principle affected:** 2
**Description:** Free-form text *is* machine-readable — LLMs eat it natively.
The implicit equation "machine-first == structured == fixed schema" is a 2015
assumption. In 2026, an LLM consumer often prefers prose. The principle is
calibrated to a pre-LLM world while claiming to be AI-first.
**Scenario:** A handoff between two LLM-driven agents would be more reliable as
markdown notes than as a brittle JSON schema. The principle forbids this.
**Severity:** major

---

## Hole 15: "Isolated Contract" forbids cross-cutting concerns
**Principle affected:** 3
**Description:** Logging, tracing, metrics, auth, retry, circuit-breaking,
feature flags — these *must* cross component boundaries to function. A literal
reading of "no boundary crossing" makes observability impossible.
**Scenario:** A request ID needs to thread through five components for a trace.
Per Principle 3, each component should "read nothing outside the contract."
Either the contract bloats to carry every cross-cutting field, or the principle
is silently violated.
**Severity:** major

---

## Hole 16: Contracts cannot be written without reading outside them
**Principle affected:** 3
**Description:** To design or change a contract, the designer must understand
both sides. The principle bars this — "Read nothing outside the contract" —
yet without it, contracts cannot evolve. The principle is self-stalling for
maintenance work.
**Scenario:** Engineer must change the API between `auth` and `billing`. They
need to read both. Principle 3 forbids it. Either the principle excludes design
work (then say so) or it is unworkable.
**Severity:** major

---

## Hole 17: "Bounded scope" is undefined; component is undefined
**Principle affected:** 3
**Description:** What counts as a component? A function? A module? A microservice?
A repo? A team? Two engineers will draw boundaries differently and reach
opposite conclusions about whether a given access "crosses" them.
**Scenario:** Engineer A treats a class as the boundary; Engineer B treats the
package. A helper call is a contract violation under A and a normal call under
B. Code review deadlocks.
**Severity:** major

---

## Hole 18: Strict isolation prevents debugging
**Principle affected:** 3
**Description:** Debugging a production issue often requires reading another
component's logs, internal state, or database. "Read nothing outside the
contract" makes root-cause analysis cross-component impossible without
violating the principle.
**Scenario:** Bug appears in component B but the cause is corrupt data in A's
private store. Per Principle 3, the engineer cannot look at A's store. They
must wait for A's owner — who is on PTO.
**Severity:** major

---

## Hole 19: Contract becomes a god-object
**Principle affected:** 3
**Description:** Because *all* communication must be contract-bound and
nothing outside it may be read, every new need adds a contract field. Contracts
inflate without bound, becoming the very god-object the principle was supposed
to prevent.
**Scenario:** Over two years, the request schema between two services grows from
8 fields to 230. Every cross-component need is "just one more field." The
"isolation" principle directly produced the entanglement.
**Severity:** major

---

## Hole 20: Principle 3 has no story for shared infrastructure
**Principle affected:** 3
**Description:** Databases, queues, filesystems, configuration stores, secrets
managers — these are *shared* by definition. Are they part of the contract?
Are they boundary crossings? The principle is silent.
**Scenario:** Two services read from the same Postgres table. Is that a contract
violation? If yes, every shared store is forbidden. If no, "no boundary
crossing" doesn't mean what it says.
**Severity:** major

---

## Hole 21: Three principles, no precedence
**Principle affected:** all
**Description:** When principles conflict, which wins? Asimov numbered his laws
to encode precedence. This philosophy numbers them but never says the numbering
*means* precedence. Conflicts are common and the philosophy provides no
arbitration.
**Scenario:** Most reliable solution is a prompt (violates 1) writing free-form
text for a human reader (violates 2) by reading two components' state (violates
3). The right call is unspecified.
**Severity:** critical

---

## Hole 22: No principle covers reversibility / blast radius
**Principle affected:** all
**Description:** None of the three principles addresses the cost of being
*wrong*. A deterministic script that destroys production data is worse than a
probabilistic prompt that drafts an email. The hierarchy is calibrated to
predictability, not to consequence.
**Scenario:** A script (highest tier) and a prompt (lowest tier) both have a
1% bug rate. The script writes to prod DB; the prompt writes to a draft folder.
Per the philosophy, the script wins. Per reality, the prompt wins.
**Severity:** critical

---

## Hole 23: No principle covers latency / time-to-answer
**Principle affected:** 1, 2
**Description:** A script that takes 3 hours to write loses to a prompt that
takes 30 seconds when the question is "what time does the meeting start?" The
philosophy has no temporal cost model.
**Scenario:** Engineer needs an answer in 60 seconds. Strict philosophy says
build a script. Pragmatic answer: ask the model. The philosophy points the
wrong way.
**Severity:** major

---

## Hole 24: "AI fails silently" is overstated; scripts also fail silently
**Principle affected:** 1
**Description:** The justification for Principle 1 hinges on "LLMs fail silently."
Scripts also fail silently (swallowed exceptions, off-by-one bugs, wrong-but-
plausible output). The asymmetry is overstated and used to justify a strong
ranking.
**Scenario:** A script with `try: ... except: pass` silently drops 5% of records
for two years. No one notices. The "deterministic" advantage was illusory.
**Severity:** minor

---

## Hole 25: "Identical input → different output" is solvable for LLMs
**Principle affected:** 1
**Description:** With `temperature=0`, fixed seeds, fixed model versions, and
prompt caching, modern LLMs return identical output for identical input. The
empirical claim used to justify Principle 1 is dated.
**Scenario:** A team pins model + temperature=0 and gets bit-identical output
across thousands of runs. The "drift" justification no longer applies, but the
ranking still demotes them.
**Severity:** minor

---

## Hole 26: No human override clause
**Principle affected:** all
**Description:** The philosophy has no explicit escape hatch for human judgment
overriding the rules. Every codified ethic — engineering or otherwise — needs
"and a senior engineer can override with cause." Its absence makes the document
read as dogma rather than guidance.
**Scenario:** A staff engineer sees that following Principle 3 will cause a
prod outage. There is no sanctioned mechanism to overrule.
**Severity:** major

---

## Hole 27: No principle for trust and provenance
**Principle affected:** 2, 3
**Description:** Machine-first state passed across contract boundaries needs
provenance: who produced it, when, with what version, signed by whom. The
philosophy is silent on trust between components, which becomes urgent the
moment any of them is AI-generated.
**Scenario:** Component B receives a malformed payload from "A." Was it really
A? Was it A v1.2 or A v1.3? Was it tampered with in transit? The contract has no
answer.
**Severity:** major

---

## Hole 28: No principle for failure recovery / idempotency
**Principle affected:** 3
**Description:** Contracts say what to send, not what to do when delivery fails.
Without idempotency, retry semantics, or dead-letter handling, "isolated
contract" is fragile in any real distributed system.
**Scenario:** Component A retries; B processes twice; the user is double-charged.
Each component honored its contract.
**Severity:** major

---

## Hole 29: No principle for observability of AI decisions
**Principle affected:** 1, 2
**Description:** When AI is used (the lowest tier), the philosophy gives no
guidance for capturing prompts, responses, model version, token counts, or cost
for later inspection. AI usage is treated as undesirable rather than as a
first-class citizen requiring auditability.
**Scenario:** Six months later, a regression appears. No record of which prompt
or which model produced the original answer. Root cause is unknowable.
**Severity:** major

---

## Hole 30: No cost / budget principle
**Principle affected:** 1
**Description:** Token cost, compute cost, engineer-hours, opportunity cost —
none are mentioned. The ranking is consequence-blind in dollars as well as in
correctness.
**Scenario:** Team builds a deterministic script that costs 200 engineer-hours
to save $4 of monthly LLM spend.
**Severity:** major

---

## Hole 31: No security principle
**Principle affected:** all
**Description:** Prompt injection, secret leakage through structured handoffs,
supply-chain risk in scripts, contract poisoning — all unaddressed. A workflow
philosophy in 2026 that does not name security has a critical gap.
**Scenario:** AI consumer of a "machine-first" state file is prompt-injected via
a user-controlled string in that file. Principle 2 actively widened the attack
surface.
**Severity:** critical

---

## Hole 32: No principle on testing
**Principle affected:** 1, 3
**Description:** Scripts and contracts are preferred but the philosophy says
nothing about testing them. An untested script is not safer than a careful
prompt; an untested contract is a mine.
**Scenario:** A "preferred" script ships untested and corrupts data on its first
real run.
**Severity:** major

---

## Hole 33: Slippery slope — total automation
**Principle affected:** 2
**Description:** Taken to its limit, "human is secondary" justifies removing the
human entirely. There is no floor on how far the human is demoted. The
principle reads as direction rather than position.
**Scenario:** Over time, every UI is replaced by APIs, every dashboard by JSON.
On-call engineers cannot intervene without writing tooling first. Mean
intervention time approaches infinity.
**Severity:** major

---

## Hole 34: Slippery slope — script monoculture
**Principle affected:** 1
**Description:** "Always prefer script" leads to forking a script for every task,
producing thousands of one-off scripts no one maintains, each subtly
inconsistent. The cure becomes the disease.
**Scenario:** `bin/` directory grows to 4,800 scripts in 18 months; nobody knows
which to use.
**Severity:** major

---

## Hole 35: Slippery slope — contract proliferation
**Principle affected:** 3
**Description:** Strict isolation forces every interaction to be formalized.
Internal call counts explode into RPCs; private helpers become "contracts." The
system becomes a distributed monolith.
**Scenario:** A team converts every internal helper to an RPC to satisfy the
"contract-bound" rule. Latency, ops burden, and on-call load triple.
**Severity:** major

---

## Hole 36: Principles assume a single agent / single trust domain
**Principle affected:** 3
**Description:** When two components are owned by adversarial parties (open-source
plugin + main app, two teams with different SLOs, vendor + customer), "contract"
needs trust boundaries the philosophy doesn't model.
**Scenario:** A third-party plugin claims to honor the contract but doesn't.
Principle 3 has no defense.
**Severity:** major

---

## Hole 37: No principle on data lifecycle / retention
**Principle affected:** 2
**Description:** Machine-first state files accumulate forever. The philosophy
has no story for TTL, GDPR, archival, or deletion. Machine-first becomes
machine-hoard.
**Scenario:** A user requests deletion of personal data. It is scattered across
seven "machine-first" state files in five components. Retention policy: none.
**Severity:** major

---

## Hole 38: "Generate nothing outside the contract" forbids logs and telemetry
**Principle affected:** 3
**Description:** Logs are outputs not in the contract. Metrics are outputs not in
the contract. Stack traces are outputs not in the contract. A literal reading
forbids all of them.
**Scenario:** Engineer adds a debug log line. Reviewer says: "not in the
contract." The principle as written wins; production becomes unobservable.
**Severity:** major

---

## Hole 39: Philosophy is silent about its own evolution
**Principle affected:** all
**Description:** Who can change the principles? Under what conditions? With what
review? A foundational document with no amendment process either ossifies or is
silently discarded.
**Scenario:** Three years pass; LLM capabilities have transformed. The
principles still say "AI last." No mechanism exists to revise them; teams
ignore them; the document becomes a fossil.
**Severity:** major

---

## Hole 40: "AI Over Human" title contradicts Principle 1's "AI last"
**Principle affected:** 1, 2
**Description:** The label of Principle 2 is "AI Over Human." The label of
Principle 1's hierarchy puts AI last. Casual readers will read the labels and
conclude the document contradicts itself in the table of contents.
**Scenario:** New hire reads the headings, asks "so do we prefer AI or not?"
Tech lead spends 20 minutes explaining the labels mean different things.
**Severity:** minor

---

## Hole 41: No notion of feedback loops / learning
**Principle affected:** all
**Description:** Nothing in the philosophy says "and we measure outcomes and
update." The principles are stated as eternal truths. Without a feedback loop,
the philosophy cannot detect when it is wrong.
**Scenario:** Following the principles produces worse outcomes for two
quarters. There is no mechanism to surface this; the principles still apply.
**Severity:** major

---

## Hole 42: No principle on concurrency / ordering
**Principle affected:** 2, 3
**Description:** Machine-first state across contract boundaries lives in a world
of races, partial writes, and out-of-order delivery. The philosophy is silent on
ordering guarantees, locking, and consistency models.
**Scenario:** Two components write to the same state file concurrently. Both
honored their contract. State is corrupt.
**Severity:** major

---

## Hole 43: No notion of "good enough" — the principle is binary
**Principle affected:** 1
**Description:** A 95%-correct prompt vs. a 100%-correct script is a meaningful
trade. The hierarchy presents itself as binary (deterministic > not), with no
threshold for "this is good enough, don't over-engineer."
**Scenario:** Team spends two weeks turning a working prompt-based summarizer
into a brittle script-based one to satisfy the principle. Quality drops.
**Severity:** major

---

## Hole 44: Principle 1's "AI last" precludes hybrid pipelines
**Principle affected:** 1
**Description:** Best-in-class systems mix scripts and AI (script for parse, AI
for understanding, script for action). The strict ranking discourages this
hybrid as "AI involvement" — yet it is provably the right architecture for many
tasks.
**Scenario:** OCR pipeline: script for image preprocessing, model for OCR,
script for post-processing. Engineer is told to "remove the AI step" per
Principle 1. Quality collapses.
**Severity:** major

---

## Hole 45: "Read nothing outside the contract" breaks emergent debugging
**Principle affected:** 3
**Description:** Modern debugging often requires correlating signals from many
components — distributed traces, multi-service log queries, cross-DB joins.
Strict isolation makes the *act of looking* a violation.
**Scenario:** SRE doing an incident review pulls logs from three services. By
Principle 3, this is a contract violation. The principle penalizes the very
act of incident response.
**Severity:** major

---

## Hole 46: No principle on autonomy limits for AI
**Principle affected:** 1, 2
**Description:** When AI *is* used (the lowest tier), there is no rule about
what it may do unsupervised. May it `rm -rf /`? May it call paid APIs? May it
push to main? "AI last" is not the same as "AI bounded." The philosophy treats
the question of *whether* to use AI but not *how far* AI may go when used.
**Scenario:** Engineer falls back to a prompt; the prompt produces an action
plan; nothing in the philosophy says the plan needs human approval before
execution. AI runs `git push --force` to main. Disaster.
**Severity:** critical

---

## Hole 47: "Script you own" is unverifiable in an LLM-authored world
**Principle affected:** 1
**Description:** "Code you own, version, and control. Zero AI involvement." In
2026, vast portions of "owned" code were authored by AI. The "zero AI
involvement" qualifier is either trivially false (AI helped write it) or
forbids the modern authoring workflow.
**Scenario:** Every script in the repo was drafted by an LLM and edited by a
human. Per the strict reading, none qualify as "script" under Principle 1.
The hierarchy collapses.
**Severity:** major

---

## Hole 48: Philosophy ignores network effects between principles
**Principle affected:** all
**Description:** Following all three principles together produces a workflow
that is *more* AI-shaped (machine-first, contract-bound, structured) than
following any one — yet the headline rule is "AI last." The interactions
between the rules push opposite to the rules' stated direction.
**Scenario:** A team that perfectly honors Principles 2 and 3 has built an
ideal substrate for AI agents to operate on, while Principle 1 forbids them
from doing so. The system is calibrated for an inhabitant it refuses to
admit.
**Severity:** major

---

## Hole 49: No definition of "handoff"
**Principle affected:** 2
**Description:** "Fixed-format schemas for every handoff" is unenforceable
without defining handoff. Function call? IPC? File write? In-memory pass?
Engineers will categorize differently and reach opposite conclusions.
**Scenario:** Engineer A treats a Python function return as a handoff requiring
a schema; Engineer B does not. Code style fragments.
**Severity:** minor

---

## Hole 50: The philosophy does not say what problem it is solving
**Principle affected:** all
**Description:** There is no stated goal — reliability? velocity? safety?
auditability? cost? — against which the principles can be evaluated.
Without a stated objective, conflicts cannot be resolved by appealing to
intent. The philosophy is a set of rules in search of a purpose.
**Scenario:** Two engineers debate whether a deviation honors "the spirit" of
the philosophy. Neither can win because the spirit is unstated.
**Severity:** critical

---

## Hole 51: "Locatable and fixable" assumes the maintainer is still around
**Principle affected:** 1
**Description:** A reproducible script error is only "locatable" if someone can
read the script. In a world of staff turnover and 10-year-old codebases, the
"fixable" assumption fails. Reproducibility without comprehension is just a
loud failure.
**Scenario:** A 12-year-old Perl script reproducibly errors. No one on the
current team can read Perl. The error is reproducible but unfixable.
**Severity:** minor

---

## Hole 52: No principle for graceful degradation
**Principle affected:** all
**Description:** When the preferred tier is unavailable (script broken, CLI
missing, spec server down), the philosophy does not say "fall back to the next
tier." The rule of order has no rule of fallback.
**Scenario:** The script crashes mid-run. Engineer wants to ask the model to
finish the job. Per Principle 1, this is a downgrade — but is it permitted?
Unclear.
**Severity:** minor

---

## Hole 53: "Contract" implies symmetry; reality is often asymmetric
**Principle affected:** 3
**Description:** Many real interactions are asymmetric: a privileged service
talks to an untrusted one, a publisher to many subscribers, a producer to a
queue. "Contract-bound" suggests a single bilateral artifact and does not model
multi-party or hierarchical interactions well.
**Scenario:** A pub/sub topic has 14 subscribers, each interpreting messages
differently. Whose contract is canonical? Per the principle, all of them — and
none.
**Severity:** minor

---

## Hole 54: No principle for human-in-the-loop checkpoints
**Principle affected:** 1, 2
**Description:** The philosophy treats AI as either present (worst) or absent
(best). It does not endorse the modern pattern of AI-proposes / human-approves,
which is neither pure AI nor pure script.
**Scenario:** Engineer wants AI to draft a migration plan that a human approves
before execution. The philosophy does not name this pattern, leaving it
ambiguous whether it is "AI use" (bad) or "human use" (fine).
**Severity:** minor

---

## Hole 55: No principle for tool / model deprecation
**Principle affected:** 1
**Description:** CLIs are deprecated, scripts' interpreters are removed,
models are retired. The philosophy assumes tooling is timeless. There is no
guidance for upgrade cycles or for what happens when a "preferred" tool
disappears.
**Scenario:** Python 2 is removed. Hundreds of "preferred" scripts no longer
run. Per the philosophy, what now?
**Severity:** minor

---

## Hole 56: Conflict between "no boundary crossing" and "AI Over Human"
**Principle affected:** 2, 3
**Description:** Designing artifacts for machine consumption (Principle 2)
implies a *consumer* — usually somewhere outside the producing component. That
implies cross-component reading, which Principle 3 bans.
**Scenario:** Component A writes a machine-first state file specifically so
that B (and any LLM agent) can consume it. B reading it is, per Principle 3,
"reading outside the contract" — unless we redefine the file *as* the contract,
which then re-introduces the god-object problem (Hole 19).
**Severity:** major

---

## Hole 57: Principle 1 confuses "AI" with "non-determinism"
**Principle affected:** 1
**Description:** Many AI workflows are bounded and verifiable (classifier with
a known confusion matrix). Many script workflows are unbounded and unverifiable
(scraper depending on third-party HTML). The principle uses "AI" as a proxy for
"unpredictable" and conflates two different axes.
**Scenario:** A 99.999%-precision classifier is demoted below a brittle scraper
because one is "AI" and the other is "script."
**Severity:** major

---

## Hole 58: No principle of least surprise / consistency
**Principle affected:** all
**Description:** Two components honoring all three principles can still expose
wildly inconsistent UX, naming, and behavior. The philosophy enforces
mechanical structure but not semantic consistency.
**Scenario:** Component A returns errors as `{error: ...}`; Component B as
`{err: ...}`; both honor Principle 2's "fixed schema." Consumers must learn
both. No principle prevents this.
**Severity:** minor

---

## Hole 59: "Bounded scope" without scope definition is circular
**Principle affected:** 3
**Description:** "Each component operates within its own bounded scope" — but
"bounded scope" is precisely what was being defined. The principle defines a
component as a thing with a bounded scope, and bounded scope as the thing a
component has. Circular.
**Scenario:** During architecture review, the question "is this two components
or one?" cannot be settled by appealing to the principle, because the principle
presupposes the answer.
**Severity:** minor

---

## Hole 60: The philosophy never names its enemy
**Principle affected:** all
**Description:** Every strong philosophy names what it opposes (chaos, waste,
ambiguity, drift). This one does not. Without a named enemy, principles cannot
be tightened against pressure; they can only be read literally.
**Scenario:** During pushback ("can we just do it the easy way this once?"),
the philosophy provides no weight to push back with — there is no "this is
exactly the kind of thing we are trying to prevent." The author has armed the
defense with rules but no reason.
**Severity:** major

---
