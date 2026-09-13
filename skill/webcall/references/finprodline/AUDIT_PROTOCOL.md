# FinProdLine audit protocol

An audit is not one worker glancing at the work. Every audit round is itself planned, decomposed,
replicated, integrated, and repeated until closure.

The purpose is stated once and applies throughout: **a fresh bounded context is the independence
mechanism.** An auditor that shares the producer's commission, reasoning, or conclusions is not an
auditor. Replicas auditing the same chunk receive the same authoritative context and acceptance
contract, and no other replica's conclusions.

Cross-model diversity is **optional**. The operator has ruled that fresh bounded context is
sufficient independence and that the same model family is acceptable. Independence is a property of
the commission, not of the vendor.

There is **no cap** on audit volume (FINPRODLINE_PROTOCOL.md §2.5). Replica count is chosen by the
operator and audit scope is never reduced to save calls.

---

## 1. Audit types are distinct

Maintain separate disciplines for at least:

| type | proves |
|---|---|
| **plan audit** | a Layer 1 or Layer 2/3 plan is correct and complete for its phase |
| **Method audit** | the phase's finance method is correct, current, exhaustive, faithful, bounded |
| **Data audit** | the data strategy and acquired data satisfy the accepted method and preserve provenance |
| **Execution audit** | the accepted Method was applied to the accepted Data exactly, and it reconciles |
| **ledger/state audit** | recorded state matches actual artifacts, calls, findings, plan versions and gate decisions |
| **handbook audit** | the handbook is correct, teachable and control-faithful |
| **final project audit** | the whole assembled deliverable satisfies the original goal and acceptance criteria |

Do not substitute one for another. An execution audit does not prove the plan was good. A plan audit
does not prove the workbook is correct. A handbook audit does not prove the finance engine is
correct.

---

## 2. Audit Planner

Before any auditor launches, a fresh bounded **Audit Planner** worker receives the complete
permitted context and the acceptance contract, and produces an immutable Audit Plan.

The Audit Plan must:

- **research audit criteria and method exhaustively for its subject**, and plan from that research
  (§2.2);
- enumerate every audit dimension in scope;
- map every acceptance criterion to one or more checks;
- define **at most three** chunks that can be audited independently (§2.1);
- identify cross-chunk dependencies;
- define the evidence each check requires;
- define failure and materiality rules;
- define the **substantive** ledger and state checks — whether recorded state matches what actually
  happened (§2.2). Mechanical ledger integrity is proved by the state tool, not by a worker;
- record the replica count `N` selected by the operator;
- assess the **producer's declared acceptance-check specification** (FINPRODLINE_PROTOCOL.md §2.6)
  for coverage, strength and independence, and state what the audit adds beyond it;
- prove complete coverage of the target scope — every criterion mapped, no orphan check.

A plan that leaves any acceptance criterion unmapped is malformed and is returned, not executed.

The producer's declared checks are an **input to** the audit plan, never a substitute for it. An
audit that only re-runs them has audited nothing: it has confirmed that the producer's own
understanding of its contract is self-consistent, which is exactly what the producer already
asserted. Declared checks that are vacuous, tautological, self-fulfilling, or that map fewer than
every acceptance criterion are a material finding against the producer.

### 2.1 The audit is planned in at most three chunks

**An Audit Plan contains at most three chunks.** The round ceiling is therefore `3 × N` auditor
calls — with the operator's `N = 3`, **nine calls**.

Three is a **ceiling, not a target**. A plan may use one, two or three chunks, as its content
requires.

Chunks are thematic groupings, each independently auditable, and between them they still cover the
whole criterion map. **The cap never reduces coverage: every acceptance criterion is still mapped,
and every check is still executed.** If the subject cannot be covered in three chunks, the planner
**merges** them — it does not emit more chunks and leave the merge to the operator.

This is the standing shape of every audit round, not a concession granted for one round. The planner
designs inside it from the start.

### 2.2 The audit is about content; mechanical invariants are not checks

**The planner researches audit criteria and method exhaustively for the subject in front of it** —
what a sound audit of *this* kind of work actually requires — and builds the plan from that research.
A plan assembled from a generic template has not been planned.

A **check** exists to settle something only judgement can settle: whether the work is adequate,
sufficient, coherent, correctly scoped, correctly reasoned, or whether a control actually tests what
it claims to test.

**A question a script can decide from already-declared values is not a check, and must not appear in
an Audit Plan.** At minimum this excludes:

- hash, size and byte-identity comparison;
- file, artifact and routing names, and their presence or absence;
- counts, sequence numbers and ordering;
- envelope, schema and vocabulary conformance;
- graph resolution and acyclicity;
- agreement between a generated state view and the stream it is generated from.

These are **proved mechanically** — deterministically, by the platform's own tooling — and recorded
as run events. They are not delegated to a worker and they consume no replica.

Where one question mixes the two — a hash comparison **and** a judgement about whether the pinned
target is the right one — the plan keeps the **judgement** and drops the comparison.

**Excluding a check never silently deletes verification.** An invariant excluded from a plan is one
the platform must already prove. Where no tool proves it, closing that gap is a **tooling obligation
on Terminal**, recorded as such — not a check smuggled back into the plan.

---

## 3. Audit-plan QA, and the recursion boundary

The Audit Plan is itself audited by a fresh independent **Audit-Plan Reviewer** before execution.
Defects produce a revised Audit Plan and a re-review.

The reviewer **returns a plan without executing it** when the plan:

- contains more than three chunks (§2.1);
- contains any check a script could decide from declared values (§2.2);
- leaves an acceptance criterion unmapped, or carries an orphan check;
- shows no evidence of subject-specific research into criteria and method (§2.2).

These are rejection grounds, not advisory notes.

This meta-review follows a fixed protocol and **does not** recursively spawn another
audit-planning hierarchy. This is the recursion boundary: plan QA is one level, never a tower.

---

## 4. Parallel replicated auditors

After the Audit Plan passes:

1. Split the work across the accepted chunks — **at most three** (§2.1).
2. For each chunk, spawn `N` independent fresh bounded auditor calls, `N` being the operator's
   recorded replica count.
3. Replicas auditing the same chunk receive the same authoritative context and acceptance
   contract, and **not** each other's conclusions.
4. Chunks and replicas run in parallel when dependencies permit.

If the full corpus is too large for one call, the Auditor Planner chunks — **within the three-chunk
ceiling** (§2.1) — so that each worker has complete context **for its chunk** plus the global
authority and index context needed to interpret it. Completeness is never achieved by silently
dropping source material, and it is never achieved by adding chunks.

---

## 5. Complete context rule

Every auditor gets 100% of the permitted context that could bear on its assigned scope — originals,
not summaries or derived extracts, whenever originals are relevant.

The package carries a **context completeness manifest** listing what was included and, where
material was withheld, the rule that withheld it. The only permitted withholdings are the Web Call
transmission prohibitions and an active project privacy lock. "It seemed irrelevant" is not a
permitted withholding.

---

## 6. Findings contract

Every finding must state, explicitly:

| field | content |
|---|---|
| `finding_id` | unique, stable |
| `target` | the artifact, state object or claim audited |
| `severity` | materiality classification |
| `what_is_wrong` | the defect, stated plainly |
| `why_it_is_wrong` | the reasoning that makes it a defect |
| `evidence` | exact reference: file, line, cell, hash, source anchor |
| `violated` | the rule, authority or acceptance criterion breached |
| `impact` | the downstream dependency cone |
| `remediation` | the exact change required to fix it |
| `remediation_reasoning` | why that change fixes it rather than moving the problem |
| `closure_test` | the check that proves the defect is gone |
| `status` | open, closed, rejected, or unresolved-minority |

**A finding that only says "review", "improve", "consider" or "check" is malformed.** It is
returned to the auditor rather than accepted, because it cannot be closed and cannot be audited.

---

## 7. Integration and adjudication

A separate fresh **Audit Integrator/Adjudicator** worker receives all replica reports plus the
shared authority, and:

- deduplicates findings across replicas;
- reconciles auditor conflicts against the declared authority;
- rejects unsupported findings, recording why;
- preserves minority findings when they remain unresolved;
- produces the authoritative round finding register;
- determines pass or fail against the acceptance contract.

Where replicas disagree on a matter requiring domain judgment and the authority does not settle it,
the Integrator records the conflict as unresolved. It does not pick a side on taste.

The Integrator **does not repair the audited work.** A worker that repairs is not the worker that
audits, and the integrator that adjudicated the defect is not the one that fixes it.

---

## 8. Repair and re-audit loop

If any material defect remains:

1. Preserve all failed work and all audit evidence.
2. Commission fresh repair or revision worker(s) with the exact findings and closure tests.
3. Validate the returned repair mechanically.
4. **Re-bind the verified plan** to the repaired artifact identities (§8.1). This is a mechanical hash
   update. It is not a determination and it opens nothing.
5. **Audit the repaired work again, in full, against the same verified plan** — new replicas, a new
   integrator, the entire relevant scope reassessed, not only the previously known defects.
6. Repeat 2–5 until 100% passed under §5.4 of the main protocol, or genuinely `BLOCKED`.

No silent repair. No producer self-audit. No reduction of scope because a round already ran. **No
Audit Planner and no plan review, ever, after the plan is verified.**

**The verified plan is never reopened.** It is not revised, not re-reviewed, not re-planned and not
re-litigated — not on a repair, not on a finding, not on a later round's objection, and not because
someone now believes the plan has a hole. If the work does not satisfy the plan, **the work is
redone until it does.** That is the entire remedy.

### 8.1 A plan is bound, not re-validated

A verified plan's `review_state` does not change when it is re-bound. The plan was passed and it
remains passed; only its **binding** — the exact basenames, sizes and sha256 it executes against — is
replaced. Terminal performs the re-binding mechanically and records it as a `plan_binding_recorded`
run-stream event, exactly as it records a first binding.

Re-binding is a hash update. There is no assessor, no determination and no judgement in it, and
nothing about the plan's content is examined or questioned while it happens.

### 8.2 The verified plan is closed, and nothing reopens it

A plan that has passed its own independent review is **closed**. The following are all denied:

- a repair to the audited work;
- a finding raised in a later round;
- an uncovered-material objection from an integrator;
- a hole newly noticed in the plan's own method;
- a Coordinator's, auditor's or operator's later change of mind about the method.

**A hole in the plan's method is the plan-validation loop's job, and that loop runs before the plan
is ever used** (§3). Once it has passed the plan at 100%, the question is settled and is not asked
again. A method that can be re-litigated after it is verified has not been verified at all — the
validation would only be a pause before the next round of doubt, which is exactly the tower §3's
recursion boundary exists to forbid.

If the work cannot satisfy a verified plan, **the work is wrong**. Redo the work. If the work
genuinely cannot be redone to satisfy it, the line is `BLOCKED` and the Coordinator decides what
becomes of the work. **The plan is still not touched — not by the repairer, not by Terminal, not by
the Coordinator, not by anyone.**

---

## 9. Ledger and state audits

Ledger and state integrity is audited alongside every major plan and gate audit, and again at phase
closure.

The **mechanical** half of that integrity — sequence ranges, hash-chain proof, index source tails,
supersession links, orphan and missing references — is proved by the state tool's audit projection
and is **not** a plan check (§2.2). What the audit carries is the substantive question: whether the
recorded state matches what actually happened.

Because agents do not read raw JSONL in normal operation, the state tool produces complete,
chunkable audit projections carrying:

- event sequence ranges;
- hash-chain proof;
- index source tail hashes;
- referenced artifact identities;
- supersession links;
- orphan and missing-reference checks.

The ledger audit verifies that recorded state matches actual artifacts, calls, findings, plan
versions and gate decisions. A stream that says a gate passed while no integrated verdict exists is
a material finding, and the gate reopens.

---

## 10. Independence rules that do not relax

- A producer never audits its own work.
- A planner never audits its own plan.
- An integrator never repairs what it adjudicated.
- A repair is always followed by a fresh full audit round.
- Replicas never see each other's output before the integration step.
- Audit packages carry complete permitted context, with a completeness manifest.
- A finding without evidence, remediation and a closure test is not a finding.
- An audit never accepts a producer's declared checks as proof, and never lets them narrow its own
  scope. The declared checks are audited, not trusted.
- A verifier never authors the checks for work it did not produce. If the declared checks are
  missing or insufficient, that is a finding against the producer and a packaging defect against the
  package that omitted them — not a licence for the verifier to write its own.
- **A verified plan's validation is closed permanently.** Nothing reopens it. What moves when the
  audited work is repaired is the **binding** — a list of hashes — and that is a mechanical update
  performed by Terminal, not a judgement about the plan.
- **Failing work is redone until it satisfies the verified plan.** The remedy for a failing step is
  never an edit to the standard it failed. A system that re-plans when work fails has not gained
  assurance; it has moved the goalposts and called it quality.
- **A hole in a plan's method belongs to the plan-validation loop, which runs before the plan is
  used.** Discovering one later does not reopen the plan; it means the validation loop failed, and
  the plan stays closed regardless. There is no Coverage-Delta Assessor, no DELTA determination, and
  no plan revision after verification. If the work genuinely cannot satisfy a verified plan, the
  line is `BLOCKED` and the Coordinator decides what becomes of the work — not of the plan.
- **A plan carries at most three chunks (§2.1).** The round ceiling is `3 × N` calls — nine at
  `N = 3`. The cap never reduces coverage and is never passed to the operator to merge.
- **A plan carries no check a script could decide (§2.2).** Mechanical invariants are proved by
  platform tooling and consume no replica. Only judgement is audited by an auditor.
