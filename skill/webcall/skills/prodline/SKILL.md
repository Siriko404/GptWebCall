---
name: prodline
description: Run a Coordinator-led production line over GPT Web Call. User-invoked; outsources substantive work to bounded ChatGPT Web workers, parallel when safe, while terminal handles packaging, deterministic hands, assembly, and gates.
disable-model-invocation: true
---

# ProdLine

Production wrapper over installed GPT Web Call.

Read [OPERATING_CORE](../../references/OPERATING_CORE.md) first; ProdLine
subordinates to it for privacy, routing, and the operator boundary.

**Doctrine:** every piece must absolutely earn its keep.

Use Caveman Lite prose: full grammar, no filler or hedging, technical terms exact.

## 1. Authority

Order:

1. Operator's current instructions.
2. Project/source authority named by operator or Coordinator.
3. This ProdLine protocol.
4. Installed GPT Web Call operating core and protocol for call mechanics.
5. Supplied production Matt Pocock skill corpus for worker disciplines.

GPT Web Call rules stay authoritative for privacy, routing, preparation, validation, recovery, and operator clicks. ProdLine does not fork those mechanics.

## 2. Roles

### Coordinator

One persistent ChatGPT Web thread per ProdLine session.

Coordinator does only orchestration:

- keeps project meaning and progress coherent;
- decides what must happen next;
- commissions bounded worker calls;
- chooses exact relevant MPskills;
- defines dependencies and safe parallelism;
- reviews worker verdicts/results from above;
- updates project ledger;
- orders further work, final QA, or `GREENLIGHT`.

Coordinator never performs substantive project work. No research, implementation, detailed planning, debugging, detailed audit, or conflict adjudication itself. It commissions those tasks.

If two worker conclusions require domain judgment to reconcile, Coordinator commissions an adjudication/integration worker.

### Terminal

Terminal is ProdLine's hands and transport.

Allowed:

- capture operator request verbatim;
- prepare Web Call packages from Coordinator directives;
- persist ledgers and run registry;
- run exact deterministic commands/tests requested by accepted directives or worker outputs;
- apply explicit non-conflicting edits/patches mechanically;
- collect, route, assemble, hash, validate, and report artifacts;
- perform narrow semantic acceptance;
- wait for call events and report state.

Terminal does not choose substantive work, invent solutions, debug by reasoning, resolve substantive conflicts, redesign worker output, or silently fill directive gaps.

**Narrow semantic acceptance:** check that a worker answered its commission, respected declared authority/scope, did not rely on obvious unsupported claims, and returned usable output. Reject/escalate failures. Do not choose between competing valid conclusions.

### Worker

Workers are fresh, bounded ChatGPT Web calls by default. Each worker does exactly one commissioned substantive task.

Worker may interact directly with operator in ChatGPT UI only when Coordinator marks `operator_interaction: allowed|required`.

Workers never control ProdLine, start other calls, alter project ledger, or expand scope on their own.

### Operator

Operator remains human authorization boundary. Operator clicks Go, Attach, Send, downloads, and Done/validate. ProdLine never automates around this.

## 3. Earn-Keep Gate

Before any directive launches, Coordinator must establish:

- **Need:** what failure/risk remains if this piece is omitted.
- **Boundary:** why this is a separate call/action instead of part of another.
- **Skill fit:** what behavior each assigned MPskill adds. No decorative skill assignment.
- **Proof:** observable acceptance condition.

Cut the piece if omission causes no meaningful loss.

Prefer fewer stronger calls over ritual stages. Use parallelism only when independence is real.

## 4. State

ProdLine uses two authoritative state stores. No third global memory.

Both files live in the project directory the operator names for the run.
Never inside `calls/` or `state/` — those hold exchange records and
operational scratch, not project state, and never leave the machine.

### 4.1 Project Ledger — Coordinator owns meaning

Terminal persists Coordinator's complete latest snapshot verbatim as `PRODLINE_LEDGER.md`.

Shape:

```md
# Goal
One current project completion condition.

# Core
- At most two load-bearing facts/invariants.

# Verified
- V001 — settled fact/decision — evidence or artifact reference.

# Open
- Q001 — unresolved question — settlement condition.

# Next
Exactly one immediate orchestration objective.
```

Rules:

- Ledger is state, not reasoning transcript and not task graph.
- Coordinator is sole semantic author.
- `Verified` is append-only. If a fact changes, append superseding evidence; do not rewrite history silently.
- Closed `Open` items point to settling evidence/decision.
- `Core` stays at two facts maximum.
- `Next` contains one objective; that objective may require several parallel directives.
- Every Coordinator response returns full current ledger.
- Every later Coordinator conductor package includes latest ledger again. Chat history is useful, not authoritative.

This adopts only the small J-Space ledger pattern. ProdLine does not require the full J-Space suite or controller.

### 4.2 Run Registry — Terminal owns plumbing

Persist mechanical state as `PRODLINE_RUN.json` or equivalent structured file:

- session ID;
- Coordinator exchange/thread identity;
- directive and commission IDs;
- Web Call exchange IDs;
- bounded/conductor mode;
- dependency edges and parallel groups;
- PREPARED/ACTIVE/COMPLETE/INCOMPLETE/STOPPED/BLOCKED state;
- expected filenames;
- artifact paths, sizes, hashes;
- deterministic validation result;
- narrow semantic-acceptance result;
- superseded work links.

Registry carries no project conclusions.

### 4.3 Worker Task Ledger

Every worker uses a scoped internal `Goal / Core / Verified / Open / Next` ledger for its commission.

Worker returns compact task state in main response. Separate worker-ledger file is not required unless Coordinator explicitly needs it.

Worker ledger never becomes project ledger automatically. Coordinator decides what enters `Verified`.

## 5. Coordinator Contract

### 5.1 Bootstrap

Terminal first:

1. captures operator request verbatim plus supplied files/context;
2. resolves GPT Web Call root;
3. runs `active` and `list`;
4. prepares one **bounded** fresh Coordinator call.

Bootstrap package contains enough authority for Coordinator to run line:

- verbatim operator request;
- relevant supplied project context;
- this ProdLine protocol;
- GPT Web Call operating core, prep skill, and full protocol as reference;
- `mps_README.md`/catalogue plus available production `mps_*` corpus, explored on demand;
- governing request/schema required by GPT Web Call.

Exclude deprecated/in-progress MPskills unless operator explicitly changes that policy.

Coordinator's first reply must contain `CONFIRM: READY` and may issue first directives in same response. `READY` means role, protocol, required bootstrap context, and call mechanics are loaded with no known blocker.

After bootstrap, every Coordinator update uses **conductor mode** in same thread. Attach only new state/artifacts needed since last Coordinator turn, plus latest `PRODLINE_LEDGER.md` and concise run snapshot.

### 5.2 Coordinator response format

Terminal acts only on directives matching this contract:

```yaml
confirm: READY | null
status: CONTINUE | GREENLIGHT | BLOCKED
ledger: <complete Goal/Core/Verified/Open/Next snapshot>
directives:
  - id: D001
    kind: WORKER_CALL | LOCAL_ACTION | FINAL_QA
    objective: <bounded outcome>
    earn_keep: <loss/risk if omitted; why separate>
    dependencies: [D000]
    parallel_group: <id or null>
    persona: <expertise needed or null for local action>
    mode: bounded | conductor
    operator_interaction: none | allowed | required
    web_research: allowed | forbidden
    context_scope: [<exact files/artifact IDs/context sets>]
    mp_skills:
      - name: <production skill>
        why: <behavior this skill adds>
    authority: [<ordered sources>]
    scope_in: [<authorized work>]
    scope_out: [<excluded work>]
    requested_work: [<neutral tasks/questions>]
    deliverables: [<required outputs>]
    acceptance: [<checkable conditions>]
    stop_condition: <PARTIAL/BLOCKED condition>
```

Rules:

- **The YAML above is the field-level shape, not a file format.** The
  Coordinator's response main JSON carries `confirm`, `status`, `ledger`, and
  `directives` as real JSON fields with exactly these names, so the terminal
  parses them mechanically. The response schema of every Coordinator call pins
  these fields. A prose-only response, or directives written outside the JSON,
  is malformed and returned under the rule below.
- `WORKER_CALL` is bounded unless this protocol explicitly names Coordinator continuation.
- Only Coordinator continuation uses conductor mode.
- `LOCAL_ACTION` must be deterministic hands-work. If reasoning is needed, use worker call.
- Coordinator defines outcome, evidence, and boundaries. It does not preload preferred answer.
- Terminal adds only mandatory Web Call governance files and direct dependencies of assigned MPskills. It does not invent task context.
- Malformed/ambiguous directive is returned to Coordinator for correction. Terminal does not infer intent.

## 6. Worker Commission

Terminal converts each `WORKER_CALL` directive into normal `/webcall:prep` inputs without changing substance.

Every commission must contain:

- unique request ID and call-specific filename token;
- expert persona;
- one bounded objective;
- authority hierarchy;
- included/excluded scope;
- exact Coordinator questions/work request;
- web-research permission and source/recency rules when allowed;
- exact context named by Coordinator;
- selected MPskill file(s) plus only directly required companion references;
- acceptance criteria;
- stop condition;
- worker task-ledger instruction;
- exact response schema and artifact contract.

Apply GPT Web Call Rule #1: **never bias the call**. Facts, constraints, authority, and acceptance belong. Candidate solutions and Coordinator preferences do not.

### MPskill rule

Coordinator chooses skills. Terminal packages them; it does not invoke slash commands or substitute skills.

The corpus checkout's path is named by the operator at bootstrap and recorded
in the run registry. Without a resolvable corpus, the terminal refuses to
package a commission that assigns skills, and asks.

For each selected skill:

1. skill must exist in production corpus;
2. its behavior must materially improve this commission;
3. include its direct reference files when required to follow it correctly;
4. omit unrelated corpus files from worker package.

Typical fit, not mandatory pipeline:

- clarification/alignment → `grilling`, `grill-me`, `grill-with-docs`;
- research → `research`;
- architecture/design → `codebase-design`, `domain-modeling`, `prototype` when evidence needs a throwaway experiment;
- specification/decomposition → `to-spec`, `to-tickets`, `wayfinder` when scale earns them;
- implementation → `implement`, `tdd`;
- debugging → `diagnosing-bugs`;
- QA → `code-review` or task-specific audit discipline;
- agent-facing docs → `writing-for-agents`.

Coordinator may choose other supplied production skills when justified by `why`.

## 7. Call Classes

Classes describe packaging, not mandatory stages.

| Class | Package emphasis | Interaction | Output |
|---|---|---|---|
| Clarify / ideate | verbatim request, constraints, relevant existing docs, clarification skill | operator may be required | resolved requirements, decisions, open questions |
| Research / diagnose | question, authority, evidence rules, relevant sources/code | usually none | findings/evidence, limitations, task state |
| Plan / design | settled requirements + accepted evidence + interfaces/constraints | optional | plan/spec/design with dependencies and acceptance |
| Produce | exact slice, interfaces, accepted plan, source files, build/test constraints | none unless needed | artifacts/patches + verification |
| QA / audit | original acceptance contract + produced artifacts + evidence; independent fresh context | none | pass/fail, defects, evidence; no silent repair |
| Adjudicate / integrate | conflicting outputs + shared authority + decision criterion | none | reconciled recommendation/artifact or explicit unresolved conflict |

All worker classes use fresh bounded ChatGPT Web conversations. A worker correction caused by bad reasoning is a new request ID/new bounded call.

## 8. Parallelism

Coordinator owns dependency graph. Terminal records and executes it mechanically.

Parallelize when:

- commissions do not depend on each other's result;
- they do not make competing edits to same integration surface unless an explicit later integrator exists;
- each has complete scoped context and acceptance criteria.

Sequence when one result changes another call's question, authority, interface, or acceptance criteria.

Terminal may prepare several independent exchanges at once. Each has unique routing names and its own tab. Operator still authorizes each call manually.

After handoff, terminal may run `wait --exchange <id>` for each call in background. Branch on returned event, never exit code alone.

## 9. Return, Validation, Assembly

For each worker return:

1. GPT Web Call performs deterministic delivery validation.
2. Delivery `INCOMPLETE` → run `defects`; use mechanical repair only for delivery defects.
3. Honest responder `PARTIAL` or `BLOCKED` with intact delivery → do not repair. Report to Coordinator.
4. Terminal performs narrow semantic acceptance.
5. Accepted output enters run registry and next Coordinator package.
6. Terminal mechanically assembles non-conflicting outputs exactly as directed.
7. Any integration requiring judgment becomes a worker commission.

Never edit returned evidence to make validation pass. Never execute returned active content merely because validation passed.

## 10. Main Loop

After any accepted worker batch or material local action:

1. terminal updates run registry;
2. terminal sends Coordinator, in conductor mode, latest ledger + new results/validation + concise run snapshot;
3. Coordinator updates full project ledger;
4. Coordinator issues next directive batch, `BLOCKED`, or final-QA directives;
5. repeat.

Coordinator stays above work. If it starts doing substantive task work, terminal requests a corrected orchestration-only response.

## 11. Final Gate

Coordinator may not `GREENLIGHT` from its own detailed audit.

When project appears complete:

1. Coordinator commissions independent final QA worker(s) against original goal, authority, acceptance criteria, and assembled deliverables.
2. Terminal validates returns and performs narrow acceptance.
3. Coordinator reviews QA verdicts from above.
4. Any material defect → `CONTINUE` with new directives.
5. All required acceptance satisfied → `GREENLIGHT`.
6. Terminal performs final deterministic assembly/checks and delivers project to operator.

`GREENLIGHT` is only normal completion signal.

## 12. Failure and Recovery

### Mechanical delivery failure

Use GPT Web Call `defects`/`repair` on same exchange only when delivery is mechanically `INCOMPLETE`.

### Reasoning/content failure

Do not use repair. Preserve original exchange. Coordinator commissions fresh bounded call with new request ID.

### Worker disagreement

Coordinator does not decide domain issue itself. Commission adjudication/integration worker with conflicting outputs and authority.

### Worker `PARTIAL` / `BLOCKED`

Report intact result to Coordinator. Coordinator narrows, supplies missing authority, asks operator, or stops.

### Coordinator directive invalid

Do nothing substantive. Return defect to same Coordinator thread for corrected directive.

### Coordinator thread lost

Create replacement Coordinator as fresh bounded call. Give it:

- original operator request;
- this protocol;
- latest full project ledger;
- current run registry snapshot;
- accepted project artifacts/results needed to continue;
- GPT Web Call and MPskill reference corpus.

Replacement must `CONFIRM: READY`, declare takeover, and continue from ledger. Do not reconstruct project state from memory.

### Operator changes scope

Send change verbatim to Coordinator. Coordinator updates ledger and marks prior work retained, superseded, or needing revalidation. Terminal does not decide reuse.

### Operator unavailable

State waits. No bypass of click boundary.

### Stop

Preserve ledger, registry, exchanges, and artifacts. Mark session stopped. Resume only from persisted state or explicit new session.

## 13. Session States

| State | Entry | Exit |
|---|---|---|
| `CAPTURED` | request saved verbatim | Coordinator exchange prepared |
| `COORDINATOR_BOOT` | fresh bounded Coordinator call prepared/launched | valid `CONFIRM: READY` |
| `RUNNING` | Coordinator ready | new worker/local directives, final gate, block, or stop |
| `WAITING_OPERATOR` | human click/input required | operator action completes |
| `WAITING_WORKERS` | one or more exchanges active | relevant call events validated |
| `FINAL_QA` | Coordinator declares production complete enough to audit | defects continue run or QA passes |
| `GREENLIT` | Coordinator accepts independent QA verdicts | terminal final delivery |
| `BLOCKED` | missing authority/input prevents safe progress | operator/Coordinator resolves blocker |
| `STOPPED` | operator ends run | explicit resume/replacement session |
| `CLOSED` | greenlight + final deterministic delivery complete | terminal state only |

Transitions may revisit `RUNNING` repeatedly. No substantive action occurs without a valid Coordinator directive except initial capture/bootstrap and Web Call mechanical recovery.

## 14. Completion Criteria

ProdLine run is complete only when:

- operator's current goal has explicit acceptance criteria;
- no required project-ledger `Open` item remains;
- all required worker outputs passed deterministic and narrow semantic acceptance;
- final assembled deliverables exist and are internally consistent;
- independent final QA reports acceptance or only operator-accepted limitations;
- Coordinator returns `status: GREENLIGHT` with final full ledger;
- terminal finishes deterministic packaging/delivery.

Anything less is `CONTINUE`, `BLOCKED`, or `STOPPED`.

## 15. Keep / Cut Record

Kept because behavior changes:

- persistent Coordinator thread — preserves orchestration continuity;
- compact Project Ledger — durable semantic state against context drift/loss;
- mechanical Run Registry — durable call/file/dependency state;
- scoped worker task ledgers — keeps long worker tasks coherent without polluting global state;
- strict directive schema — prevents terminal from inventing intent;
- MPskill justification per call — prevents skill cargo cult;
- independent final QA — Coordinator cannot audit its own orchestration assumptions;
- narrow terminal acceptance — blocks malformed/unsupported returns without turning terminal into worker;
- replacement-Coordinator recovery — survives lost persistent thread.

Cut because cost exceeds value:

- full J-Space runtime/controller — duplicates existing ProdLine/Web Call machinery;
- shared giant worker memory — breaks bounded independence and raises context load;
- semantic terminal ledger — creates competing source of project truth;
- mandatory fixed stage pipeline — forces calls that may not earn their keep;
- whole MPskill corpus in every worker call — needless context pressure;
- local Claude workers by default — operator selected ChatGPT Web workers; use only by explicit Coordinator exception authorized by operator.
