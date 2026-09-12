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

- enumerate every audit dimension in scope;
- map every acceptance criterion to one or more checks;
- define chunks that can be audited independently;
- identify cross-chunk dependencies;
- define the evidence each check requires;
- define failure and materiality rules;
- define the ledger and state checks;
- record the replica count `N` selected by the operator;
- prove complete coverage of the target scope — every criterion mapped, no orphan check.

A plan that leaves any acceptance criterion unmapped is malformed and is returned, not executed.

---

## 3. Audit-plan QA, and the recursion boundary

The Audit Plan is itself audited by a fresh independent **Audit-Plan Reviewer** before execution.
Defects produce a revised Audit Plan and a re-review.

This meta-review follows a fixed protocol and **does not** recursively spawn another
audit-planning hierarchy. This is the recursion boundary: plan QA is one level, never a tower.

---

## 4. Parallel replicated auditors

After the Audit Plan passes:

1. Split the work by the accepted chunks.
2. For each chunk, spawn `N` independent fresh bounded auditor calls, `N` being the operator's
   recorded replica count.
3. Replicas auditing the same chunk receive the same authoritative context and acceptance
   contract, and **not** each other's conclusions.
4. Chunks and replicas run in parallel when dependencies permit.

If the full corpus is too large for one call, the Auditor Planner chunks so that each worker has
complete context **for its chunk** plus the global authority and index context needed to interpret
it. Completeness is never achieved by silently dropping source material.

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
4. Start a **new independent exhaustive audit round** — new Audit Planner, new plan review, new
   replicas, new integrator.
5. The new round reassesses the **entire relevant scope**, not only the previously known defects.
   A repair that fixes the named defects and breaks nothing else is still unproven until re-audited
   in full.
6. Repeat until 100% passed under §5.4 of the main protocol, or genuinely `BLOCKED`.

No silent repair. No producer self-audit. No reduction of scope because a round already ran.

---

## 9. Ledger and state audits

Ledger and state integrity is audited alongside every major plan and gate audit, and again at phase
closure.

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
