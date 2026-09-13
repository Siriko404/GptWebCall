# FinProdLine state protocol

Append-only JSONL streams, rebuildable indexes, and a deterministic command surface.

The governing rule is in [FINPRODLINE_PROTOCOL.md](FINPRODLINE_PROTOCOL.md) §2.4: **history is
append-only.** Nothing in this protocol may rewrite, reorder or delete a recorded event.

A second rule shapes everything here: **agents do not read raw ledgers in normal operation.** Raw
JSONL is immutable audit history, not model context. Agents obtain state through generated views.

---

## 1. Project marker and layout

### 1.1 Marker

A FinProdLine project is identified by a directory named `.finprodline/` containing a valid
`project.json`. Discovery walks the current directory and then its parents, stopping at the first
valid marker whose integrity checks pass. It never scans siblings or the whole disk.

### 1.2 Layout

Machine state is confined to the marker. Human-readable project material follows the established
project convention at the project root.

```
<project root>/
  .finprodline/                     marker + machine state
    project.json                    config, identity, locks
    streams/
      project.jsonl                 Coordinator semantic stream
      run.jsonl                     Terminal mechanical stream
      workers/<worker-id>.jsonl     one task stream per worker
    indexes/                        rebuildable caches (never authoritative)
    integrity.json                  last verified stream tails
  governance/                       operator rulings, protocol copies, acceptance reports
  plans/                            versioned Layer 1 and Layer 2/3 artifacts
  evidence/                         call evidence, extracted worker returns
  artifacts/                        accepted release artifacts
  work/calls/<token>/               per-call packages, as the installed convention
```

Nothing under `.finprodline/` is ever uploaded. It is project state, and it is subject to the same
transmission prohibitions as Web Call's own `calls/` and `state/`.

---

## 2. Event model

### 2.1 Common envelope

Every event in every stream carries exactly these fields:

| field | meaning |
|---|---|
| `schema_version` | integer, currently `1` |
| `seq` | integer, 1-based, contiguous within its stream |
| `event_id` | globally unique, `<stream>-<seq padded to 6>-<8 hex of the event hash>` |
| `timestamp` | RFC 3339 UTC |
| `actor` | `coordinator` \| `terminal` \| `worker:<worker-id>` \| `operator` |
| `event_type` | from the stream's vocabulary, §2.3 |
| `subject_id` | the object the event is about: a phase id, finding id, artifact id, call id, plan id, or `project` |
| `phase_id` | phase id, or `null` before phases exist |
| `gate` | `METHOD` \| `DATA` \| `EXECUTION` \| `null` |
| `payload` | event-type-specific object |
| `evidence_refs` | array of strings: artifact ids, file paths relative to the project root, exchange ids, or hashes |
| `supersedes` | array of `event_id` this event supersedes; empty when it supersedes nothing |
| `prev_event_hash` | the `event_hash` of the previous event in this stream, or 64 zeros for `seq` 1 |
| `event_hash` | see §2.2 |

### 2.2 Hash chain

`event_hash` is the lowercase hex SHA-256 of the event object **with `event_hash` removed**,
serialized as canonical JSON:

```
json.dumps(obj, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode('utf-8')
```

Any change to any byte of any earlier event breaks the chain at that point and at every event
after it. `fpl_state verify-ledgers` recomputes the whole chain and reports the first break.

`event_id` depends on `event_hash`, so it is computed last and is not itself hashed.

### 2.3 Event vocabularies

**Project stream (`project.jsonl`) — Coordinator semantic meaning.**
`goal_set`, `operator_ruling_recorded`, `plan_proposed`, `plan_accepted`, `plan_superseded`,
`phase_opened`, `gate_state_changed`, `finding_promoted`, `finding_closed`, `conclusion_accepted`,
`open_item_raised`, `open_item_settled`, `scope_changed`, `earn_keep_cut_recorded`,
`final_decision`.

**Run stream (`run.jsonl`) — Terminal mechanical plumbing.**
`session_started`, `project_initialized`, `marker_verified`, `coordinator_bootstrapped`,
`directive_received`, `directive_rejected_malformed`, `package_precheck_result`,
`upload_approval_recorded`, `exchange_prepared`, `exchange_armed`, `exchange_event_received`,
`delivery_validated`, `semantic_acceptance_recorded`, `artifact_persisted`,
`reconciliation_result`, `plan_binding_recorded`, `index_rebuilt`, `supersession_linked`,
`anomaly_recorded`, `recovery_event`.

`plan_binding_recorded` is the mechanical act of binding a verified plan to the exact artifact
identities it will execute against — basenames, sizes, sha256 — or of re-binding it after a repair. It
changes nothing about the plan: the plan was passed and remains passed, and it is never reopened. It
exists because a verified plan carries forward across repairs and only its **binding** moves, and a
re-binding is a hash update rather than a judgement. See AUDIT_PROTOCOL.md §8.1.

**Worker stream (`workers/<worker-id>.jsonl`) — one worker's scoped task.**
`task_started`, `input_pinned`, `step_performed`, `finding_recorded`, `output_produced`,
`issue_open`, `issue_closed`, `task_finished`.

The run stream carries no finance conclusion. It may quote an accepted external verdict only
mechanically, with the event id it came from.

### 2.4 Vocabulary extension

A stream may carry an event type not listed above only if the project config records it under
`event_vocabulary_extensions` with a one-line meaning. An unknown event type fails
`verify-ledgers` rather than being silently accepted.

---

## 3. The three streams

### 3.1 Project stream

The Coordinator is the semantic author; Terminal persists mechanically.

Terminal may append to this stream only in the two cases in FINPRODLINE_PROTOCOL.md §9.1: an
operator ruling recorded verbatim, and an outcome mapping exactly to a Coordinator-authored
template. Everything else waits for a Coordinator round.

### 3.2 Run stream

Terminal-owned. Mechanical state only: session and project ids, Coordinator identity, directive
ids, turn numbers, exchange ids, bounded/conductor mode, dependencies and parallel groups,
exchange states, expected names, upload approval records, artifact paths, sizes and hashes,
validation results, narrow semantic acceptance, reconciliation results, index rebuilds,
supersession links, recovery events.

### 3.3 Worker streams

Every worker maintains a scoped append-only task ledger for its commission and returns it inside
its one outputs archive. Terminal stores it under that worker's evidence directory and mirrors the
events into `workers/<worker-id>.jsonl`.

A worker task stream never becomes project truth automatically. Only a Coordinator ruling promotes
anything out of it.

---

## 4. Indexes

Indexes are **non-authoritative caches**, always rebuildable from the append-only streams plus
immutable artifacts. Every rebuild records the source stream tail hashes it was built from, and
`verify-indexes` rejects an index whose recorded tails no longer match the streams.

Required views:

| view | answers |
|---|---|
| `project-current` | current goal, active phase and gate, accepted plan versions, current operator locks |
| `open-items` | unresolved questions, findings and blockers, with settlement conditions |
| `plan-current` | accepted Layer 1 and the current phase's Layer 2/3 versions |
| `artifact-index` | artifact ids, hashes, versions, acceptance status |
| `lineage` | source -> raw -> transform -> output dependency graph |
| `calls-current` | active and relevant exchanges and routing state |
| `worker-history` | one worker's task ledger and artifacts by worker id |
| `audit-current` | audit plan, replica reports, integration verdict, open findings |
| `handbook-current` | completed phase coverage and handbook QA state |
| `audit-ledger-export` | a complete, chunkable projection for ledger audits |

An index never becomes an input to a decision on its own. Where an index and a stream disagree, the
stream is right and the index is rebuilt.

---

## 5. Command surface

The executable name is an implementation detail. The semantics are not. The shipped implementation
is `scripts/fpl_state.py`.

```
fpl_state discover  [--start <dir>]
fpl_state init      --root <dir> --goal <text> [--canon-mode supplied|researched|hybrid]
                    [--audit-replicas N] [--handbook-learner <text>] [--release-override <json>]
fpl_state get       <view> [--select <key=value> ...] [--project <dir>]
fpl_state append    --stream project|run|worker:<id> --event <file|-> [--project <dir>]
fpl_state worker    --id <worker-id> [--project <dir>]
fpl_state rebuild-index [<name>|all] [--project <dir>]
fpl_state verify-ledgers [--project <dir>]
fpl_state verify-indexes [--project <dir>]
fpl_state export-audit --scope <scope> [--chunk <n>] [--project <dir>]
fpl_state lineage   (--from <id> | --to <id>) [--project <dir>]
fpl_state recover-coordinator [--project <dir>]
```

Every command emits exactly one JSON object: `{"ok": true, "command": ..., "result": ...}` on
stdout with exit 0, or `{"ok": false, "command": ..., "error": ...}` on stderr with exit 2. This
matches the installed Web Call CLI so a session reads both the same way.

`append` computes `seq`, `prev_event_hash`, `event_hash` and `event_id` itself. A caller never
supplies them, and supplying one is an error rather than an override.

---

## 6. Integrity and recovery

### 6.1 Verification

`verify-ledgers` checks, per stream: contiguity of `seq`, correctness of every `prev_event_hash`
link, correctness of every `event_hash`, well-formedness of every envelope, known event types, and
that every `supersedes` target exists earlier in some stream.

`verify-indexes` checks that every index's recorded source tail hashes match the current streams.

### 6.2 Tamper and truncation

A modified or truncated stream is a hard failure. The line stops, preserves the stream as found,
records an `anomaly_recorded` event in the run stream, and returns the fact to the operator. State
is never silently repaired by rewriting history. Recovery is a new event stream that records the
damage and what was reconstructed from artifacts.

### 6.3 Lost Coordinator

`recover-coordinator` emits a bootstrap package assembled from the `project-current`, `plan-current`
and `open-items` views plus the accepted artifacts and the original operator request. The
replacement Coordinator declares takeover from that package. Conversation memory is never used.

### 6.4 Forensic access

On an explicit operator instruction, Terminal may read raw streams, worker task streams, artifacts
and historical versions directly. This is an operator-directed capability, not a normal input path,
and it is recorded as an operator-directed action in the run stream.
