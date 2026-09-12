---
name: finprodline
description: FinProdLine — a finance production operating system over GPT Web Call. One command discovers or initializes a project, then runs an audited Method/Data/Execution line with replicated adversarial audits, three-layer planning, provenance, and synchronized CSV/Excel/engine and handbook output lines. Use when the user explicitly invokes this workflow.
disable-model-invocation: true
---

# `/webcall:finprodline`

Read [OPERATING_CORE](../../references/OPERATING_CORE.md) first — it governs privacy, routing, and
the operator boundary for everything below. Then read
[FINPRODLINE_PROTOCOL.md](../../references/finprodline/FINPRODLINE_PROTOCOL.md), which is this
skill's substance.

The other three documents are reached **only when their branch is active**, never read up front:

| document | reach for it when |
|---|---|
| [STATE_PROTOCOL.md](../../references/finprodline/STATE_PROTOCOL.md) | writing or reading state, running the state tool, recovering a lost role, auditing a ledger |
| [AUDIT_PROTOCOL.md](../../references/finprodline/AUDIT_PROTOCOL.md) | planning an audit, spawning replicas, integrating findings, or running a repair-and-re-audit round |
| [HANDBOOK_PROTOCOL.md](../../references/finprodline/HANDBOOK_PROTOCOL.md) | a phase has 100% passed and handbook production begins, or handbook QA runs |

This is the **only user-facing command** in FinProdLine. Planning, audits, state and ledger
behaviour are internal. Never tell the operator to run a second FinProdLine command.

---

## 1. Start here, every time

1. **Discover.** Run `fpl_state discover` from the working directory. It walks the current
   directory and its parents for a `.finprodline/` marker and stops at the first valid one whose
   integrity checks pass. Never scan siblings or the whole disk.
2. **Integrity first.** On a found project, run `verify-ledgers` before anything else. A broken hash
   chain is a hard stop: preserve the stream as found, record an anomaly, report to the operator. Do
   not repair history.
3. **Resume or initialize.**
   - Marker found and valid → resume from disk state. Do not re-ask anything already settled in
     `project.json` or the project stream.
   - No marker → initialize a new project in the current directory. Settle only the genuinely
     project-specific choices, once: goal and acceptance outcome, canon mode, audit replica count
     `N`, handbook learner preference, any release-artifact override, and any confidentiality or
     licensing restrictions.
4. **Check the installed system.** Confirm the Web Call root resolves and run `active` and `list`
   **for this project only**. If the root does not verify, refuse and send the operator to
   `/webcall:init`.
5. **Boot or recover the Coordinator.** If no live Coordinator exists, prepare a fresh bounded
   Coordinator call. If one was lost, `recover-coordinator` builds its bootstrap package from disk
   state — never from conversation memory.

---

## 2. What FinProdLine owns

Finance orchestration doctrine; project discovery, resume and init; finance project state and
ledgers; three-layer planning; the Method → Data → Execution gates; finance source authority and
provenance; audit planning, replicated adversarial audits, integration and closure loops;
cross-artifact numerical reconciliation; synchronized output lines; lagged handbook production and
handbook QA; finance-specific recovery and reinitialization.

## 3. What FinProdLine does not own — call through, never reimplement

Request packaging and deterministic snapshots; one inputs ZIP up and one outputs ZIP down; filename
collision control; browser routing and tab binding; the operator's Go / Attach / Send / Download /
Done boundary; download filing; deterministic response validation; `defects` and `repair` for
mechanical delivery failures; the semantics of `active`, `list`, `show`, `wait`, `validate`,
`defects`, `repair`, `clone`, `stop`, `delete`; and the absolute ban on transmitting anything under
Web Call `calls/` or `state/`, credentials, or tokens.

If something here looks like it needs reimplementing, it does not. Add it to this skill instead.

---

## 4. The line

For each phase, in order, with no merging and no skipping:

```
plan (Layer 2/3) -> audit -> METHOD work -> audit -> DATA work -> audit -> EXECUTION work -> audit
```

Every audit is itself planned by a fresh Audit Planner, reviewed by a fresh Audit-Plan Reviewer,
executed by `N` independent replicas per chunk, and integrated by a fresh adjudicator that never
repairs. A gate is passed only at 100% under FINPRODLINE_PROTOCOL.md §5.4. A material finding sends
the work to fresh repair, followed by a **fresh full audit round**, never a partial one.

Terminal never enters a fix-run loop. It executes an accepted package once and halts at the first
anomaly with raw evidence preserved.

## 5. Every outbound package

Build complete permitted context, run `fpl_precheck` on the spec, present the file manifest to the
operator for explicit upload approval, record the approval, `prepare`, then arm `wait` immediately
after handoff. Use `show`, never `validate`, as the pre-send check.

Before the precheck passes, confirm at minimum: request ID agreement everywhere; exact output ZIP and
main JSON names; no routing-name collision with any PREPARED or ACTIVE call; both governing JSONs
present under their exact basenames; no `000_READ_ME_FIRST.md` in `input_files`; every declared path
exists with a unique plain basename; nothing from Web Call `calls/` or `state/`; no credentials; and
that everything the commission claims to contain is actually packaged.

## 6. Reporting to the operator

Caveman Lite: lean prose, short sentences, bullets, no filler, exact paths. Lead with state and the
one action. Full detail lives in the on-disk state and evidence — point at it, do not inline it.

The operator is the authorization bridge, not a worker. Never route a research, sourcing,
calculation, reconciliation, debugging, QA or document-production journey to them. If workers or
Terminal can do it, they do it.

---

## Refuse

- Refuse to run a second user-facing FinProdLine command into existence. One command.
- Refuse to proceed on a broken hash chain, or to repair history by rewriting it.
- Refuse to merge, reorder or skip the Method / Data / Execution gates, at any phase size.
- Refuse to pass a gate without an integrated audit verdict, a closed finding register, and the
  cross-artifact reconciliation for that scope.
- Refuse to let a producer audit its own work, a planner audit its own plan, or an integrator repair
  what it adjudicated.
- Refuse to skip the fresh full re-audit after a repair.
- Refuse to accept a finding that states no evidence, no remediation and no closure test.
- Refuse to begin handbook production for a phase that has not 100% passed.
- Refuse to upload any project document without explicit operator approval.
- Refuse to transmit Web Call `calls/` or `state/`, credentials, tokens, or project material under
  an active privacy lock.
- Refuse to reconstruct project state from conversation memory.
- Refuse to reduce audit scope, merge gates, or drop replicas because a run is expensive. There is
  no cap and cost is not a reason.
- Refuse to act on another project's exchanges. Project isolation is absolute unless the operator
  asks otherwise.

## Proof it worked

- `fpl_state discover` returns the project marker or reports none, and never a sibling.
- `verify-ledgers` and `verify-indexes` pass, with recorded stream tail hashes.
- `project.json` records only settled choices, and a resume asks nothing already settled.
- Every call in the run stream has an exchange id, an approval record, a validation result and a
  semantic-acceptance record.
- Every gate in the project stream reached `100% passed` only via an integrated audit verdict.
- Every phase marked complete has CSV, engine and Excel artifacts that reconcile.
- The handbook covers exactly the 100%-passed phases and nothing else.
- `GREENLIGHT` was issued on independent audit verdicts, not on the Coordinator's own reading.
