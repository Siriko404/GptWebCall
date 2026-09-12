# FinProdLine protocol

Read [OPERATING_CORE](../OPERATING_CORE.md) first. Read
[../prodline/SKILL.md](../../skills/prodline/SKILL.md) too: FinProdLine is a hardened successor to
ProdLine and inherits its role split, its Earn-Keep Gate, and its subordination to the installed
GPT Web Call mechanics. Where this document and ProdLine differ, this document governs finance
projects.

FinProdLine is a **finance production operating system** layered on the installed GPT Web Call
system. It covers any finance project: valuation, banking, credit, FP&A, transaction analysis,
investment research, forecasting, risk, portfolio work, corporate finance.

The only user-facing entrypoint is `/webcall:finprodline`. Everything below is reached through it.

Use Caveman Lite prose when reporting to the operator: full grammar, no filler or hedging,
technical terms exact.

---

## 1. Authority

Order:

1. The operator's current instructions and rulings.
2. This protocol and its companion documents.
3. The project's own config, accepted plan versions, and recorded rulings.
4. Installed GPT Web Call operating core and protocol, for all call mechanics.
5. Supplied skill corpora, for worker discipline.

Web Call rules stay authoritative for privacy, routing, preparation, validation, recovery, and the
operator click boundary. FinProdLine does not fork those mechanics. Section 3 of the specification
and `SKILL.md` §"What FinProdLine does not own" list exactly what is called through rather than
reimplemented.

---

## 2. Doctrines

These apply everywhere: architecture, planning, state, data, execution, QA, handoffs, recovery,
final delivery.

### 2.1 Zero Trust

Nothing derived is trusted because it exists, validated mechanically, came from an expert worker,
came from an auditor, came from the Coordinator, came from the Terminal, or appeared in an earlier
accepted artifact.

Every material claim has a verification path. Every material number has provenance. Plans, ledgers,
audits, data, engines, workbooks, produced artifacts and Terminal actions are all auditable.

The only irreducible authorities are:

1. the operator's current rulings;
2. immutable source bytes plus their verified identity/hash;
3. governing external authorities chosen for the project, interpreted through accepted
   methodology.

Even source interpretation remains subject to audit.

**Late defects propagate.** When a defect is found in accepted work, the lineage graph identifies
its downstream dependency cone. Affected acceptances are revoked by superseding events and the
affected gates reopen. Prior history stays intact — see §3.

### 2.2 Earn-Keep

Every phase, step, call, worker, audit replica, artifact, control, data field, reference and
handbook element must earn its keep.

For each planned piece, record:

- **Need** — failure or risk if omitted;
- **Boundary** — why it must exist separately rather than merged;
- **Fit** — why this worker/skill/control is appropriate;
- **Proof** — observable completion condition.

If omission causes no meaningful loss, cut the piece, and record the cut as an immutable decision
event so it cannot silently reappear.

**Earn-Keep scales work inside a gate. It never removes a gate.** Section 5's three gates are
mandatory for every phase including small ones.

### 2.3 Atomic state, economical browser rounds

Production actions, QA outcomes, finding creation and closure, provenance events and ledger events
are recorded **atomically and immediately**.

Browser call launches and Coordinator conductor rounds may batch independent work to reduce
operator clicks. Batching browser traffic never batches state history: each underlying event keeps
its own immutable record.

### 2.4 Preserve history

History is append-only. No accepted, rejected, failed, superseded or repaired history is
overwritten or rewritten. Corrections create new events and new versions that point back to what
they supersede.

This binds the agent, not only the tooling. Returned worker evidence is never edited to make
validation pass, and an accepted artifact is never amended in place.

### 2.5 No cap on audit volume

The operator has ruled explicitly that there is no call-budget ceiling. Gate merging is not a
permitted response to cost, and audit scope is not reduced because a run is expensive. Call volume
is reported as run state. See `governance/OPERATOR_RULINGS.md` R001 in the project that produced
this protocol.

---

## 3. Roles

### 3.1 Coordinator

One persistent ChatGPT Web thread per active project, when available.

Coordinator does orchestration only: maintains project meaning, issues directives, selects workers
and skills, establishes dependencies and parallel groups, decides which project-semantic
conclusions are promoted, reviews integrated audit verdicts from above, and decides
re-plan / rework / continue / block / greenlight.

Coordinator does **not** perform substantive finance research, modeling, implementation, debugging,
detailed audits, or substantive conflict adjudication. Those are commissioned.

### 3.2 Worker

Workers are fresh, bounded ChatGPT Web calls in new tabs. One substantive commission and one scoped
task ledger each.

Workers perform the substantive work: finance research, methodology analysis, data
strategy/acquisition/normalization design, planning, modeling and artifact production, audits,
integration and adjudication, handbook authoring and handbook QA.

Workers never control the line, mutate the project ledger directly, start calls, or expand scope on
their own.

### 3.3 Terminal

Terminal is local hands, transport, persistence, deterministic execution and recovery
infrastructure. It:

- captures the operator request verbatim;
- discovers, initializes and resumes project state;
- calls the state and index tools;
- prepares Web Call packages from Coordinator directives;
- runs package prechecks and obtains upload approval;
- persists ledgers, worker histories, indexes, artifacts and run state;
- runs exact deterministic commands and tests specified by accepted directives or worker artifacts;
- applies explicit non-conflicting patches mechanically, once;
- collects, routes, hashes, extracts, assembles, reconciles and validates artifacts;
- performs narrow semantic acceptance;
- waits for Web Call events;
- produces recovery packages.

Terminal does **not** autonomously invent finance solutions, choose substantive methods,
debug-by-reasoning, adjudicate competing finance conclusions, or silently fill directive gaps.

**Terminal never enters a fix-run iteration loop.** It executes an accepted package exactly once and
halts at the first unexpected anomaly, preserving raw evidence and returning it to the Coordinator
or the operator. Writing and iterating implementation code is worker work.

**Operator override.** Terminal has local access to all project files, including raw append-only
ledgers, worker task ledgers, artifacts and historical versions. On an explicit operator instruction
it may inspect or recover any local project material needed to answer a question, reconstruct a lost
role, or perform an operator-directed action. This does not enlarge its normal autonomous reasoning
authority.

### 3.4 Operator

The operator is the human authorization bridge between terminal and browser — not a production
worker.

The operator invokes `/webcall:finprodline`, answers genuine design and owner choices, explicitly
approves documents proposed for upload, clicks Go / Attach / Send / download / Done, and may
override any project rule explicitly.

The operator is **never** sent on a research, sourcing, calculation, reconciliation, debugging, QA
or document-production journey. If workers or Terminal can do it, they do it.

---

## 4. Plan architecture — three immutable layers

Plans are first-class immutable, versioned, audited artifacts, not notes the Coordinator holds.

### Layer 1 — tentative project overview

Produced by one dedicated **overview planner worker**. It researches and understands the finance
problem and the method landscape, proposes the semantic phases, identifies dependencies, major
sources, outputs and risks, and remains explicitly tentative.

Layer 1 then enters its own independent audit loop. It is not accepted until 100% passed under its
acceptance contract.

### Layers 2 and 3 — phase blueprint and execution instructions

For each phase, a **different dedicated phase-planner worker** produces both:

- **Layer 2** — the detailed phase blueprint: exact Method, Data and Execution gates, steps,
  interfaces, dependencies, acceptance tests, provenance requirements, output impacts.
- **Layer 3** — exact step-by-step execution instructions for that phase, including worker
  boundaries, deterministic Terminal actions, artifacts, tests and stop conditions.

Layers 2 and 3 are versioned together for that phase and enter their own independent audit loop
before production begins.

**Layer 1 and the phase planner are different workers.** One planner never produces both.

### Versioning

Each plan artifact gets an immutable version ID and content hash. A revision never overwrites an
older version. The current accepted plan is selected by index, never by mutating history.

If a later discovery invalidates an assumption, create a new plan version, record the supersession,
audit the revision, and reopen dependent gates and artifacts.

---

## 5. Phase state machine

Every phase traverses three separate **sequential** gates:

```
METHOD  ->  DATA  ->  EXECUTION
```

No gate may be merged, reordered or skipped, whatever the phase size. Earn-Keep scales the work
inside a gate; it does not remove the gate.

### 5.1 Method gate

Settles what finance method is correct for this phase. It must establish the governing
canon/authority, definitions and assumptions, required calculations and relationships, edge cases
and applicability boundaries, exact acceptance tests, and downstream data requirements.

Method audit asks primarily: is the proposed method correct, current enough for the project,
exhaustive for the phase, faithful to authority, internally coherent, and properly bounded?

### 5.2 Data gate

May start only after Method is 100% passed. It must establish or acquire the source inventory,
source authority and identity, raw values, extraction rules, normalization and transformation
logic, units, periods, sign conventions and dimensions, lineage IDs, data quality tests, and the
treatment of missing or conflicting sources.

Data audit asks primarily: does the data strategy and the acquired data satisfy every accepted
method requirement, preserve provenance, use the right authorities and bases, and reconcile
without unsupported substitutions?

### 5.3 Execution gate

May start only after Data is 100% passed. Execution produces or updates the release artifacts for
the phase and runs the deterministic checks.

Execution audit asks primarily: was the accepted Method applied to the accepted Data exactly, do
all outputs reconcile, do formulas, logic and identities work, are controls satisfied, and is the
result reproducible?

### 5.4 Definition of 100% passed

A plan or gate is 100% passed only when all of these hold:

1. every planned check completed and passed;
2. every audit finding is closed;
3. no unresolved material uncertainty remains;
4. every required evidence or reference is traceable;
5. ledger and index integrity for the audited scope passes;
6. no unadjudicated auditor conflict remains;
7. any dependent cross-artifact reconciliation required for the scope passes;
8. the integrated audit verdict says the acceptance contract is satisfied.

Anything else is not passed. There is no partial pass and no "passed with notes" that proceeds.

---

## 6. Output lines

Three lines run in parallel. Two are live; one is deliberately lagged.

### 6.1 Release artifacts — live

Defaults, unless the project config overrides them:

1. **DATA** — the canonical CSV/table layer;
2. **Excel** — the live finance artifact/workbook;
3. **Engine** — the Python implementation, preferably one script.

The accepted canonical data layer is the engine's explicit input interface, and the engine emits
machine-readable result tables suitable for reconciliation and downstream workbook use. Canonical
inputs are never buried as unexplained literals inside Python or Excel.

Use one Python script when it can stay clear, testable, deterministic and maintainable. Split only
when a single script materially harms those properties or the method genuinely requires modular
architecture. The plan records why a split earned its keep.

**Cross-artifact reconciliation gate.** CSV, engine and Excel must reconcile numerically wherever
they represent the same quantity. The phase cannot pass Execution until shared quantities agree to
the explicitly defined tolerance, sign/unit/period/dimension conventions agree, formula and
identity checks pass, and any discrepancy is either fixed or documented as an intentional
difference with governing rationale and separate acceptance. Unexplained mismatch is a hard gate
failure.

Release artifacts are updated after accepted atomic production work that materially changes them.
They are never allowed to drift to a phase-end-only batch update. Only 100%-passed phase outputs
may be marked accepted or current for downstream use.

### 6.2 Project progression ledger — live

Live from initialization, updates atomically throughout. It consists of the Coordinator project
semantic stream, the Terminal run stream, worker task streams, rebuildable indexes, plan version
records and evidence links. See [STATE_PROTOCOL.md](STATE_PROTOCOL.md).

### 6.3 Handbook — deliberately lagged

A phase becomes eligible for handbook production only after that phase's Method, Data and Execution
gates are 100% passed. The handbook never teaches provisional or probably-correct content. See
[HANDBOOK_PROTOCOL.md](HANDBOOK_PROTOCOL.md).

---

## 7. Source authority and number provenance

Default hierarchy unless the project locks another.

**Methodology:** operator-approved canon and authoritative literature; then regulators, standards
and primary institutional methodology; then high-quality secondary literature for discovery and
cross-check; then general web commentary as low-authority context only.

**Numbers and company facts:** primary filings, audited statements, regulator filings and official
issuer releases; then official market and statistical sources; then approved licensed primary data;
then secondary sources only for discovery or cross-check unless explicitly authorized.

**Canon mode**, chosen per project and recorded in the project config:

- **supplied** — only operator-supplied canon is authoritative;
- **researched** — FinProdLine researches candidate literature and obtains operator approval before
  it becomes authoritative;
- **hybrid** — supplied canon plus researched additions approved by the operator.

Every canon file is identity-pinned by hash. If a canon or source defect is discovered late, the
lineage graph identifies the full downstream dependency cone, affected acceptances are revoked by
superseding events, and the affected gates reopen. Prior history stays intact.

**Number lineage.** Every material numeric value supports:

```
source -> exact raw value -> transformation logic -> transformed value -> consuming artifact/cell/output
```

Where raw and transformed differ, the transformation logic is mandatory and non-empty. No
unexplained manual number passes a gate.

---

## 8. Upload approval and confidentiality

No project document is uploaded without explicit operator approval.

For every outbound package, Terminal presents a concise manifest of the project files proposed for
upload, and the operator approves or rejects. The approval is recorded in the Terminal run stream.

Hard Web Call prohibitions remain hard regardless of approval: anything under Web Call `calls/` or
`state/`, credentials, authentication material, tokens, and any material forbidden by an active
project privacy lock are never transmitted.

If confidentiality, licensing or price-sensitivity status is unknown, treat the file as **not
cleared**. Workers may produce a sanitized derivative. If project policy still does not settle
whether it may leave the machine, ask the operator one direct classification question — never send
the operator on a research journey.

---

## 9. Main loop

1. `/webcall:finprodline` discovers and resumes state, or initializes a new project.
2. Terminal verifies Web Call state (`active`, `list`) **for this project only**.
3. If no valid Coordinator exists, bootstrap or recover one from disk state.
4. Coordinator issues a directive batch.
5. Terminal applies Earn-Keep and deterministic directive-shape checks. A malformed or ambiguous
   directive goes back for correction; Terminal does not infer intent.
6. For every outbound package: build complete permitted context, run the package precheck, obtain
   explicit operator upload approval, `prepare`, then arm `wait` after handoff.
7. Operator bridges the browser clicks.
8. Web Call validates delivery. Terminal performs narrow semantic acceptance.
9. Terminal immediately appends mechanical state events and persists worker task ledgers and
   artifacts.
10. Coordinator-semantic events are appended only from explicit Coordinator rulings or from
    Coordinator-authored templates. Terminal never invents meaning.
11. Independent work already authorized may continue and batch before the next Coordinator round.
12. At meaningful batch boundaries, send the Coordinator a generated state view plus accepted
    results and audit verdicts — never raw ledgers.
13. Coordinator decides the next phase, gate, repair or final QA.
14. Repeat until every project and handbook completion condition passes.

### 9.1 Reconciling atomic state with batched rounds

Coordinator directives may include deterministic ledger-event templates for expected outcomes —
accepted, failed, blocked.

Terminal may append a project-semantic event immediately **only** when the observed outcome maps
exactly to a Coordinator-authored template. Where judgment would be required, Terminal records the
mechanical event in the run stream and queues the semantic promotion for the next Coordinator
round.

This preserves both rules at once: no Terminal invention of project meaning, and no loss of
atomic, immediate history.

---

## 10. Parallelism

Coordinator defines dependencies; Terminal records and executes them mechanically.

Parallelize when tasks do not depend on each other's result, they make no conflicting edits to the
same integration surface unless a later integrator is planned, each call can receive complete
scoped context, and routing names stay unique.

Audit chunks and replicas run in parallel by default when independent.

---

## 11. Failure and recovery

**Mechanical Web Call delivery defect.** Use installed `defects` and `repair` on the same exchange.
Delivery failure only.

**Substantive reasoning or content defect.** Never repair. Preserve the original exchange and create
a fresh bounded call with a new request ID and turn number.

**Terminal anomaly.** Terminal stops at the first unexpected anomaly, preserves raw evidence,
records it, and returns it to the Coordinator or the operator for a worker-authored remedy. No
fix-run loop.

**Lost Coordinator.** Build a fresh Coordinator bootstrap package from state commands, generated
views and accepted artifacts. The replacement declares takeover and continues from disk. Never
reconstruct project state from conversation memory.

**Historic worker behaviour.** Terminal may retrieve a worker's exact task ledger and archived
artifacts by worker ID. Normal workers receive only the scoped material their task needs;
historical state is not propagated automatically.

**Scope change.** Capture the operator's change verbatim as a new project event. The Coordinator
determines what remains valid, what is superseded, and what must be re-audited. History stays
intact.

**Operator unavailable.** The line waits. There is no bypass of the click boundary and no
substitute for operator authorization.

**Project isolation.** Monitor and act only on exchanges belonging to the current FinProdLine
project. Another project's calls are ignored entirely — no alarms, no validation, no reports —
unless the operator explicitly asks.

---

## 12. Final gate

Project completion requires all of:

- the original operator goal has explicit acceptance criteria;
- Layer 1 is accepted;
- every required phase's Layer 2/3 plan is accepted;
- every required phase's Method, Data and Execution gates are 100% passed;
- all required release artifacts exist and reconcile;
- all material provenance is traceable;
- project, run and worker ledger integrity passes;
- the handbook covers every 100%-passed phase and satisfies its own QA contract;
- independent final project audits pass under the same planned, replicated, integrated loop;
- the Coordinator issues `GREENLIGHT` on the strength of audit verdicts, not its own detailed
  audit;
- Terminal performs final deterministic assembly and integrity checks.

Anything less is `CONTINUE`, `BLOCKED` or `STOPPED`. `GREENLIGHT` is the only completion signal.

---

## 13. Session states

| State | Entry | Exit |
|---|---|---|
| `DISCOVERED` | project marker found and integrity verified | state loaded |
| `INITIALIZED` | new project config persisted | Coordinator bootstrapped |
| `COORDINATOR_BOOT` | Coordinator call prepared or launched | valid `CONFIRM: READY` |
| `PLANNING` | Layer 1 or a phase Layer 2/3 in production or audit | plan accepted |
| `GATE_WORK` | a gate's substantive work commissioned | gate work returned and accepted |
| `AUDIT` | audit round planned, replicas running, or integrating | 100% passed or findings returned |
| `REPAIR` | a material finding forces fresh repair work | repair validated, re-audit started |
| `WAITING_OPERATOR` | an upload approval, a click, or a design choice is required | operator acts |
| `WAITING_WORKERS` | one or more exchanges active | relevant call events validated |
| `HANDBOOK` | handbook production or handbook QA for passed phases | handbook contract satisfied |
| `FINAL_QA` | project declared complete enough to audit | defects continue, or QA passes |
| `GREENLIT` | final audit verdicts accepted | terminal final delivery |
| `BLOCKED` | missing authority or input prevents safe progress | operator or Coordinator resolves |
| `STOPPED` | operator ends the run | explicit resume or replacement |
| `CLOSED` | greenlight plus final deterministic delivery | terminal state only |

Transitions revisit `RUNNING` states repeatedly. No substantive action occurs without a valid
Coordinator directive, except initial capture and bootstrap, and Web Call mechanical recovery.

---

## 14. Completion of the protocol itself

FinProdLine is implementable and ship-ready when another agent can install the skill set into the
existing `webcall` plugin and, using only these contracts plus the installed Web Call system, run
the full smoke path without asking a design question this protocol already settles.
