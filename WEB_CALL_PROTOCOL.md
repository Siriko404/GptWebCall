# GPT Web Call Protocol

System root: the directory containing this file. Every path and command below is relative to it.

This file is the complete operating contract for any Codex or Claude Code session using the installed GPT Web Call system. Read it before operating the system.

## Fresh-session contract

After reading this file, a new session must:

1. Treat the directory containing this file as the system root and the filesystem there as operational authority.
2. Read "RULE #1 OF PROMPT ENGINEERING: never bias the call" before writing any prompt, request or response schema.
3. Run `active` and `list` before preparing anything, so it does not collide with an existing call.
4. Read "Filenames are the routing key" before writing any preparation spec.
5. Classify the requested work before substantive reasoning.
6. Prepare a Web call only when the work is reasoning-heavy or the operator explicitly requests one.
7. Select only the context needed for that bounded call; never upload a repository or directory implicitly.
8. Explain to the operator what the prepared call will do, then let the operator control Attach, Send, downloads, and Done.
9. Treat the returned work as advisory even after deterministic file validation passes.
10. Preserve each exchange and record accepted conclusions in the external project's own ledger or artifacts.

Several calls may be active at once, each bound to its own ChatGPT tab. A single-call workflow remains the common case, and every command that acts on one active call still works without naming it when exactly one active call exists. The system is intentionally filesystem-only; `calls\`, `state\`, request snapshots, response files, manifests, and validation reports preserve continuity across sessions and compaction.

## RULE #1 OF PROMPT ENGINEERING: never bias the call

**This is the first rule, above every other consideration in this document, and it applies to every prompt written anywhere, not only to Web calls.**

> Your job is to define the **persona** and the **instructions** of an agent that has exactly the expertise you need and knows how to navigate the task professionally and in depth.
> Your job is **not** to smuggle your own answer into the prompt and get it echoed back.

You are commissioning an expert precisely because you expect a better answer than your own. Every candidate solution you put in the prompt destroys that. The model will anchor on it, elaborate it, and return it wearing your words — and you will read your own reasoning back and mistake the agreement for confirmation. A call that mirrors you cost a full budget and taught you nothing.

**Contamination is irreversible inside a call.** A model cannot un-see a suggestion. There is no recovering the independent answer once the prompt contains yours.

### The dividing line

| Belongs in the prompt | Never belongs in the prompt |
|---|---|
| **Measured facts** — sizes, counts, hashes, addresses you verified | **Your conclusions drawn from those facts** |
| **Verbatim quotes** of what the owner actually said | Your paraphrase of what they "really meant" |
| **Environment constraints** — no MSVC toolchain, stateless calls, filename routing | The workaround you invented for that constraint |
| **The outcome required** and how it will be judged | The structure, architecture, or method you think produces it |
| **Evidence standard** — what counts as proof | Which specific things you expect to be proven |
| **Failure history**, with evidence of each failure | Your theory of the root cause |
| **The persona** — the expertise the task demands | A worked example that becomes the template |

### Bias vectors that hide in plain sight

These are the ones that slip past, because they look like helpfulness or rigour:

1. **Candidate lists.** "Suggested roles: A, B, C, D, E — adopt, reject or replace." The escape hatch is decoration. You will get A–E back, lightly reworded.
2. **Enum fields in the response schema.** `"mechanism": {"enum": ["deliberate-overlap", "interface-contract", "seam-owner-rule"]}` pre-enumerates the entire solution space. A better fourth answer becomes literally inexpressible.
3. **Solution-shaped schema fields.** If your required fields are named after your design, the schema *is* your design and no other answer can validate.
4. **Deliverable filenames encoding structure.** Demanding `R2_ROLE<N>_*.md` presupposes round 2 is organised by roles.
5. **Analytical asides.** "Weight is effort, not bytes — 22 MB of disassembly is mostly inert." That is the expert's job, done for them and no longer testable.
6. **Named traps and warnings.** "The trap here is X." You just told them what to conclude.
7. **Architecture diagrams of the thing being designed.** The most direct form of the disease.

### The test to apply before sending

Read your own prompt and schema and ask:

> **Could an answer substantially better than mine — and structurally different from mine — be expressed in this format and validate against this schema?**

If no, the call is biased. Rewrite it. Prefer schema fields that describe *outcomes and evidence* (`what was decided`, `why`, `what it is checked against`) over fields that describe *your mechanism*.

### What a well-formed ask looks like

Specify, in this order: **who the agent is**, **what must be true of the answer**, **what is forbidden**, **what evidence is required**, **the facts they need**. Then stop. Let the expertise navigate.

Constraints imposed by the owner or by the environment are not bias — state them plainly and completely. The distinction is authorship: a requirement handed down from the owner, or a fact measured from the world, belongs in the prompt; a solution you thought of does not.

---

## Two files up, two files down

**Every exchange is exactly two files in each direction. This is not a style preference; it is enforced at preparation and it changes how you write a spec.**

Up:

| File | What it is |
|---|---|
| `PROMPT_YYYY-MM-DD_HHMMSS.md` | Generated by the companion from `prompt_text`. Markdown. Never supplied by you. |
| `<subject_slug>_inputs.zip` | Built by the companion. Contains every file listed in `input_files`, at the archive root, under its packaged name. |

Down:

| File | What it is |
|---|---|
| `<pass>_response.json` | The main response, exactly as before. |
| `<pass>_outputs.zip` | Every other returned file, inside one archive. |

`expected_artifacts` is therefore either empty, when the call returns nothing but the main JSON, or a single `.zip`. `prepare` refuses anything else. Two artifacts, or one artifact that is not an archive, is an error at preparation rather than a surprise at download.

You still enumerate `input_files` normally. The companion copies each one into `request/` and then packs them. Both the loose files and the archive stay on disk: the loose files are the provenance record whose hashes are verified, and the archive is what is uploaded. Only the prompt and the archive are handed to the file chooser.

The archive is byte-identical for identical inputs. Zip entries normally carry a modification time, which would make the digest change on every preparation and defeat verifying the archive against its own manifest record, so entry timestamps and ordering are fixed.

**Say the rule in the prompt as well.** The companion cannot make ChatGPT return one archive; only the prompt can. Every prompt must state that the reply is exactly two downloadable files, name them, and say that every additional file goes inside the archive rather than beside it.

**One thing this rule costs you.** Natively attached files are read directly. An archive has to be extracted with the code tool first, and a model that extracts carelessly can skim rather than read. For any call where thoroughness is the point, make the prompt require an inventory: unzip, list every extracted file with its byte size, and echo that list before answering. A shallow read then shows up in the reply instead of hiding in it.

## Delivery integrity is not work completeness

**These are two different facts and the validator reports them separately. Conflating them was a real bug that fired on every honest response.**

`status` in `VALIDATION_REPORT.json` describes the **delivery**: every promised file arrived and each one hashes to what the response said it would. That is objective, computable, and it is what `invalid_files` means. A name in `invalid_files` tells you to stop reading and repair.

`response_status` is the responder's **own account of its work**, one of `COMPLETE`, `PARTIAL` or `BLOCKED`, reported and never punished. `work_complete` is the convenience boolean.

A `PARTIAL` response delivered intact is therefore `status: COMPLETE`, `response_status: PARTIAL`. **Read it.** The files are perfect and the responder has told you where its gaps are.

The bug: any status other than `COMPLETE` used to put the main JSON into `invalid_files`, alongside corrupt downloads and hash mismatches. The exchange went to `INCOMPLETE` and every reader was told to repair a flawless response. The contradiction lived inside one module, since the parser accepted `PARTIAL` as a valid status and the validator then called the file invalid for carrying one.

What made it bite repeatedly is that prompts here explicitly ask for `PARTIAL` when something cannot be settled, because a partial answer that admits its gaps is worth more than a confident one built on a skim. So the system punished precisely the behaviour it requested, and did so on every such call. It shipped because no test covered a `PARTIAL` response that arrived intact.

The same principle governs the expected-artifact backstop. An artifact the call expected must arrive even when the main JSON forgets to declare it, so a dropped deliverable cannot validate as complete. But forgetting is not declaring: a response that names the artifact and marks it `MISSING` or `NOT_CREATED` has reported its absence rather than hidden it, and is not counted missing again.

**When you write a prompt, keep asking for `PARTIAL`.** It no longer costs anything.

## Filenames are the routing key

**This is the one rule that makes the whole system work. Read it before writing any preparation spec.**

Chrome does not tell an extension which tab produced a download. `chrome.downloads.DownloadItem` carries no tab id. The companion therefore decides which call a downloaded file belongs to **by its filename and nothing else**.

That has one absolute consequence:

> **No two calls that can still receive files may ever expect the same filename.**
> Not the same main JSON name. Not the same artifact name. Not a main JSON of one call matching an artifact of another. Comparison is case-insensitive.

A call can still receive files while it is `PREPARED` or `ACTIVE`. Once it is `COMPLETE`, `INCOMPLETE`, or `STOPPED` it releases its names and they may be reused.

A call that was prepared and then superseded therefore holds its names forever, because nothing moves a `PREPARED` call out of that state on its own and `stop` only works on an active one. Either give the corrected call distinct filenames, or `delete --exchange` the superseded one to release them.

This is enforced, not merely requested. `prepare` refuses a spec whose `expected_main_json` or any `expected_artifacts` entry is already claimed, and names the call that holds it. `core.py` repeats the check against running calls as a backstop for hand-edited manifests. A name that slips through both and is claimed by two running calls produces `AMBIGUOUS`, and the file is left in the downloads folder untouched rather than delivered to the wrong exchange.

**Declare the archive up front.** Add `expected_artifacts` to the preparation spec naming the single archive the call should return besides the main JSON:

```json
{
  "subject": "deck audit numbers pass",
  "request_id": "deck-audit-numbers-v1",
  "expected_main_json": "numbers_response.json",
  "expected_artifacts": ["numbers_outputs.zip"],
  "prompt_text": "...",
  "input_files": []
}
```

Declaring it buys three things: the collision is caught when you author the spec rather than mid-run, a promised archive that the main JSON silently drops is reported as missing instead of validating as complete, and the failure names the file rather than describing a symptom. Because artifacts are one archive, an exchange now exposes exactly two names to download routing.

**How to name files so collisions cannot happen.** Prefix every deliverable with the call's own short pass name, the same token used in the subject and request ID. `numbers_response.json`, `numbers_outputs.zip`. Never `result.json`, `response.json`, `report.md`, `findings.md`, or `output.json`; generic names are exactly the ones two calls will pick independently.

## Parallel calls

Several calls may run at once, each bound to its own ChatGPT tab.

- Each active call is bound to one tab, and a tab may drive only one call.
- An artifact downloaded before any main JSON waits in a shared pending pool and is released to whichever call's main JSON later names it. Distinct filenames are what make that release unambiguous.
- `done`, `stop`, and `repair` take `--exchange`. With exactly one active call the flag may be omitted; with several, omitting it is an error rather than a guess.
- Each armed tab shows Chrome's "being debugged" banner until its files are attached.
- The operator still drives every call by hand: Go, Attach, Send, download, Done, once per call. Parallel removes the waiting, not the clicking.

## Triage

Before substantive work, explicitly decide whether the task is reasoning-heavy.

Reasoning-heavy work includes planning or architecture, investigation or diagnosis, deep web research, high-stakes academic/technical/legal/financial judgment, synthesis across long or conflicting sources, ambiguous trade-offs, substantial artifact design, and audits that benefit from an independent reasoning pass.

Routine deterministic work includes direct file operations, mechanical formatting, running an approved plan, small unambiguous corrections, and exact lookups from a known authority.

- If reasoning-heavy: pause before the substantive reasoning and prepare a bounded Web call.
- If routine: proceed locally.
- If uncertain and the consequence matters: use a Web call.

Do not use a Web call to implement or repair GPT Web Call itself unless the operator explicitly requests that exception.

## Call decomposition and continuation

Do not mechanically pre-plan a long chain of calls when the correct reasoning process is itself uncertain. The first bounded call may be a planning/architecture call that asks ChatGPT Web to recommend the necessary reasoning stages, number and types of later calls, dependencies, and context required for each.

Codex or Claude Code then evaluates that advice and prepares only the next warranted exchange. Every later call is separately packaged and authorized by the operator. After each result, reassess whether to accept and integrate it, request criticism or correction, run another specialist call, or stop. ChatGPT Web may recommend the process, but it does not create active calls, choose private files, or bypass the operator's authorization.

## Roles and control boundary

- Codex or Claude Code classifies the work, chooses context, creates the request, prepares the exchange, checks the returned work, and integrates only accepted conclusions.
- ChatGPT Web performs the bounded assignment. It may reason, research when authorized, investigate, plan, or create requested artifacts.
- The operator authorizes every call. The operator clicks **Go**, ChatGPT's real **Attach files**, ChatGPT's native **Send**, each download control, and **Done and validate**.
- The extension never presses Send and never reads ChatGPT's response page.
- The companion moves only downloads deterministically bound to the active call. Unrelated downloads remain untouched.

## Agent call variant (Claude subagent instead of ChatGPT Web)

A prepared exchange may be executed by a local Claude Code subagent instead of a ChatGPT Web tab. The package, filename reservations, snapshots, hashes, and validation are identical; only the responder changes. This rides the manual fallback: the subagent plays the role of the operator who places response files by hand.

When to choose which responder:

- **Subagent**: throughput work — extraction, synthesis of supplied sources, artifact drafting — where zero clicking, native parallelism, and direct file reading outweigh cross-model independence. The orchestrating session picks the model per call (e.g. sonnet for mechanical extraction, opus for hard synthesis) and always spawns in background.
- **ChatGPT Web**: any call whose value is an independent reasoning pass — audits, red-teams, second opinions on Claude-produced work. A Claude subagent auditing Claude output shares its blind spots; do not route those to a subagent.

Workflow:

1. `prepare` the exchange exactly as for a Web call. Names are reserved; the request snapshot under `request\` is the provenance record. Do NOT arm the call (no Go, no tab binding); it stays `PREPARED`.
2. Spawn the subagent (background) with instructions to: read every file in the exchange's `request\` directory (the loose snapshot files, not the archive); perform the assignment per `WEB_REVIEW_REQUEST.json` and `WEB_RESPONSE_SCHEMA.json`; write the expected main JSON and the single outputs archive — exact expected filenames — into the exchange's `response\` directory; compute real byte sizes and SHA-256 hashes for every artifact and record them in `artifacts_manifest` using the schema's field names verbatim; report PARTIAL or BLOCKED honestly rather than inventing content.
3. Run `validate --exchange <exchange_id>` (works on a PREPARED exchange with manually placed files). Deterministic validation is unchanged: hashes, sizes, request ID binding, artifact accounting.
4. Semantic acceptance is unchanged and remains the orchestrating session's job. Subagent output is advisory exactly as Web output is.
5. Correction rounds: the extension repair flow does not apply. Diagnose with `defects --exchange`, then either continue the same subagent (send it the defect list) for mechanical delivery defects, or spawn a fresh subagent — new request ID, original exchange preserved — when the reasoning itself must be redone.

Rules that do not relax: one exchange per responder at a time, no filename collisions with any call that can still receive files, no silent edits to returned evidence, the operator authorizes each call before it is spawned, and never execute returned scripts or active content merely because validation passed.

## Status check and command location

Commands are run from the system root, the directory holding `gptwebcall.cmd`:

```powershell
cd <system root>
.\gptwebcall.cmd active
.\gptwebcall.cmd list
```

From another directory, invoke the wrapper by absolute path:

```powershell
& '<system root>\gptwebcall.cmd' active
```

Every CLI command emits one JSON object. `ok: true` contains `result`; `ok: false` contains `error` and exits nonzero.

## Exact request construction

Every call needs three things before preparation:

1. `WEB_REVIEW_REQUEST.json` — the intellectual assignment and authority contract.
2. `WEB_RESPONSE_SCHEMA.json` — the requested response structure supplied to ChatGPT.
3. A preparation spec — tells the local companion what to snapshot and what main filename to expect.

Use a unique, stable `request_id` in both the request and preparation spec. Use a concise, safe subject. Give every source an explicit packaged filename. Use absolute source paths. Never supply a prompt file: the companion generates `PROMPT_YYYY-MM-DD_HHMMSS.md` itself, and packs everything else into `<subject_slug>_inputs.zip`.

Name every returned file after the call itself and declare the artifacts in `expected_artifacts`. See "Filenames are the routing key" above; a generic name such as `result.json` will be refused as soon as a second call wants it.

### WEB_REVIEW_REQUEST.json template

The request may add task-specific fields, but it should normally contain:

```json
{
  "request_id": "unique-project-task-v1",
  "objective": "One bounded outcome",
  "why_this_call": "Why independent reasoning is useful",
  "authority_hierarchy": [
    "Highest-authority supplied file",
    "Secondary supplied context"
  ],
  "scope": {
    "included": ["Exact work to perform"],
    "excluded": ["Work or claims that are not authorized"]
  },
  "web_research": {
    "allowed": false,
    "rules": "If allowed, state source and recency requirements"
  },
  "requested_work": ["Concrete deliverable or reasoning task"],
  "questions": [
    {"id": "q1", "question": "Exact question to answer"}
  ],
  "required_artifacts": [],
  "acceptance_criteria": ["Observable completeness condition"],
  "stop_condition": "Return PARTIAL or BLOCKED instead of inventing missing evidence"
}
```

The request must distinguish source authority from permission to research online. For sensitive or source-closed work, explicitly prohibit outside facts. Never include credentials, API keys, cookies, authentication material, or unrelated private files.

### WEB_RESPONSE_SCHEMA.json template

ChatGPT receives this schema as an instruction. The companion independently enforces the core identity, status, artifact, delivery, size, and hash contract.

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "type": "object",
  "required": ["request_id", "status", "artifacts_manifest", "delivery"],
  "properties": {
    "request_id": {"type": "string"},
    "status": {"enum": ["COMPLETE", "PARTIAL", "BLOCKED"]},
    "results": {"type": "object"},
    "artifacts_manifest": {"type": "array"},
    "limitations": {"type": "array"},
    "delivery": {"type": "array", "items": {"type": "string"}}
  }
}
```

**The response schema is a hard contract. Pin every manifest field and tell ChatGPT to reproduce the field names verbatim.** The template above leaves `artifacts_manifest` as a bare array, which is a trap. ChatGPT will invent plausible but wrong keys for each entry (`name`, `type`, `contains`) instead of the ones the deterministic validator requires (`filename`, `status`, `media_type`, `size`, `sha256`). The result is `ARTIFACT_ENTRY_INVALID: filename null` and a false `INCOMPLETE` on work whose actual content is correct, which reads as the validator being broken when the real fault is a loose schema. Two mitigations, use both: (1) in `WEB_RESPONSE_SCHEMA.json`, fully specify the `artifacts_manifest` item with its `required` keys rather than typing it `"array"`; (2) in `WEB_REVIEW_REQUEST.json` and the prompt, instruct the model in one line to emit the response JSON using the schema's exact field names, verbatim, and to paraphrase nothing in the manifest. A model told only "follow the schema" paraphrases keys; a model told "reproduce these field names verbatim" does not.

### Preparation-spec template

Store this temporary spec anywhere safe. Operational scratch under `state\` is ignored by Git.

```json
{
  "subject": "Short call subject",
  "request_id": "unique-project-task-v1",
  "expected_main_json": "unique_project_task_response.json",
  "expected_artifacts": ["unique_project_task_outputs.zip"],
  "prompt_text": "Read every attached file. Follow WEB_REVIEW_REQUEST.json and WEB_RESPONSE_SCHEMA.json. Return no conversational text: deliver only the downloadable main JSON file and any artifacts listed in it. If blocked or incomplete, still return the main JSON with status PARTIAL or BLOCKED.",
  "input_files": [
    {
      "path": "C:\\absolute\\source\\WEB_REVIEW_REQUEST.json",
      "filename": "WEB_REVIEW_REQUEST.json"
    },
    {
      "path": "C:\\absolute\\source\\WEB_RESPONSE_SCHEMA.json",
      "filename": "WEB_RESPONSE_SCHEMA.json"
    },
    {
      "path": "C:\\absolute\\source\\relevant_context.md",
      "filename": "relevant_context.md"
    }
  ]
}
```

`created_at` is optional. Normally omit it so the companion uses the current local time. `expected_artifacts` is optional but strongly recommended: it reserves those filenames and turns a silently dropped artifact into a reported defect. The companion verifies the two governing JSON files, checks `request_id`, rejects any deliverable filename already claimed by a prepared or active call, copies only the enumerated files, hashes the snapshots, and publishes the exchange atomically.

Prepare and inspect:

```powershell
.\gptwebcall.cmd prepare --spec C:\absolute\path\prepare_spec.json
.\gptwebcall.cmd list
.\gptwebcall.cmd show --exchange YYYY-MM-DD_HHMMSS_short_subject
```

Before telling the operator to click Go, verify the manifest lists exactly the intended files, the subject and request ID are correct, and `expected_main_json` is unambiguous.

## Normal extension workflow

1. The operator opens the GPT Web Call side panel and selects the prepared call.
2. The operator clicks **Go**. The companion verifies the frozen request files; monitoring starts; ChatGPT opens.
3. The extension waits. The operator clicks ChatGPT's real **Attach files** control.
4. The extension assigns exactly the manifest-approved request files to that chooser and detaches its debugger immediately.
5. The operator reviews the filenames and clicks ChatGPT's native **Send**.
6. ChatGPT returns only downloadable files: the main JSON and any additional artifacts.
7. The operator manually downloads every output. Files may be downloaded in any order. Artifacts downloaded before the main JSON remain pending until the main JSON identifies them.
8. The operator clicks **Done and validate**. Monitoring stops first; the companion validates and writes `validation\VALIDATION_REPORT.json`.
9. The operating session reads the main response, validation report, and artifacts; it then performs semantic acceptance.

The extension accepts Chrome duplicate suffixes such as `name (1).json` only when they bind unambiguously to an expected filename. Existing different response bytes are never overwritten.

## Main response contract

The required main JSON has this minimum shape:

```json
{
  "request_id": "unique-project-task-v1",
  "status": "COMPLETE",
  "results": {},
  "artifacts_manifest": [
    {
      "filename": "requested_artifact.md",
      "status": "CREATED",
      "media_type": "text/markdown",
      "size": 123,
      "sha256": "64-lowercase-or-uppercase-hex-characters"
    }
  ],
  "limitations": [],
  "delivery": [
    "unique_project_task_response.json",
    "requested_artifact.md"
  ]
}
```

Rules:

- `request_id` must equal the exchange request ID.
- `status` is `COMPLETE`, `PARTIAL`, or `BLOCKED`.
- Every additional file is listed once in `artifacts_manifest`.
- Artifact status is `CREATED`, `MISSING`, or `NOT_CREATED`.
- Every `CREATED` artifact supplies exact filename, media type, byte size, and SHA-256.
- `delivery` accounts for the expected main JSON and every created artifact.
- A `PARTIAL` or `BLOCKED` response is preserved but deterministic validation reports the exchange incomplete.
- ChatGPT should emit no conversational acknowledgment, summary, markdown block, or pasted JSON outside the downloadable files.

## Semantic acceptance

`COMPLETE` in `VALIDATION_REPORT.json` proves only that the expected main JSON is structurally valid, bound to the request, reports `COMPLETE`, and that every created artifact is present with matching bytes. It does not prove the reasoning is correct.

After deterministic validation, Codex or Claude Code must:

1. Check that every requested question, work item, and acceptance criterion was actually answered.
2. Verify important claims against the declared authority and independently verify consequential web claims.
3. Identify unsupported inference, invented evidence, contradiction, or scope drift.
4. Decide whether to accept, partially use, reject, or request correction.
5. Integrate only warranted conclusions into the external project.

ChatGPT Web output remains advisory. The operator retains final authority.

## Correction rounds

When validation reports `INCOMPLETE`, the cause is usually mechanical rather than intellectual: a declared SHA-256 that does not match the delivered bytes, an artifact named in the manifest but never downloaded, a `PARTIAL` status, or a `delivery` list that omits a created file. Reasoning again from scratch is the wrong response to that.

A correction round diagnoses the exact defects and sends them back into the same conversation.

1. `.\gptwebcall.cmd defects --exchange <exchange_id>` lists every defect as a structured record with `kind`, `target`, `expected`, and `observed`. It reads only; it changes nothing.
2. The side panel's **Send correction round** button calls `call.repair`. The companion writes `repair\ROUND_N_PROMPT.txt` and `repair\ROUND_N_DEFECTS.json` inside the exchange, records the round in the manifest, and re-arms monitoring with a fresh download baseline.
3. The extension types the correction prompt into the composer of the bound tab and stops. It never presses Send. The operator reviews the prompt and sends it. If the composer cannot be found, the prompt is still written to disk and shown in the side panel with a copy control.
4. ChatGPT returns corrected files into the same conversation. Files that already validated are left alone.
5. Click **Done and validate** again.

Rules:

- A correction round is refused when the response has no defects.
- Corrected files never overwrite earlier bytes silently. A superseded file is moved to `response\superseded\round<N>\` before the replacement is stored, so every round remains auditable.
- Rounds accumulate. `repair_round` and a `repairs` array in the exchange manifest record what was wrong and when.
- The request ID never changes across correction rounds. Correcting a delivery is not the same as reasoning again; when the *reasoning* is wrong, create a new correction call with a new request ID as described under failure and correction rules.

## Command reference

```powershell
.\gptwebcall.cmd prepare --spec C:\path\spec.json
.\gptwebcall.cmd list
.\gptwebcall.cmd show --exchange <exchange_id>
.\gptwebcall.cmd active
.\gptwebcall.cmd done
.\gptwebcall.cmd done --exchange <exchange_id>
.\gptwebcall.cmd stop
.\gptwebcall.cmd stop --exchange <exchange_id>
.\gptwebcall.cmd delete --exchange <exchange_id>
.\gptwebcall.cmd delete --exchange <exchange_id> --force
.\gptwebcall.cmd validate --exchange <exchange_id>
.\gptwebcall.cmd defects --exchange <exchange_id>
.\gptwebcall.cmd repair --exchange <exchange_id> --tab <tab_id>
```

- `prepare`: snapshot and hash one new call package.
- `list`: list calls currently in `PREPARED` state.
- `show`: read one exchange manifest.
- `active`: show the active-call record, or the list of them when several are running, or `null`.
- `done`: stop and deterministically validate one active call without the extension.
- `stop`: abandon one active call and record `STOPPED` without deleting evidence.
- `delete`: remove one exchange from disk entirely and free the deliverable names it claimed.
- `validate`: validate files manually placed into a non-active prepared or incomplete exchange.
- `defects`: report every validation defect in a delivered response without changing anything.
- `repair`: open a correction round, write its prompt and defect record, and re-arm monitoring.

### Deleting a superseded call

`stop` is for a call that was started and must be abandoned. It requires an
active call and leaves the directory in place. Neither fits a call that was
prepared and then found wrong before it was ever sent — a payload missing a file
that its own primary question depends on, a request that asks the wrong thing, a
spec corrected after packaging. Such a call cannot be stopped, because it never
became active.

Left alone it is not inert. It stays `PREPARED` indefinitely, so it keeps
claiming its `expected_main_json` and artifact names, and the corrected call that
wants those names is refused (see **Filenames are the routing key**). It also
stays in the panel, one click away from sending the payload you already know is
wrong. `delete` removes the directory and releases the names.

Two refusals guard it, and only the second can be overridden:

- **A running call is never deleted.** The download monitor would keep writing
  into a directory that no longer exists. Stop it first, then delete it.
- **A received response is never discarded silently.** Once a file has landed in
  `response\`, that file is the only copy of work the model already did. Move it
  elsewhere, or pass `--force` to discard it deliberately. The result reports
  what was discarded under `discarded_responses`.

Prefer renaming deliverables over deleting when the superseded call still holds a
response worth keeping: a call whose state is not `PREPARED` or `ACTIVE` has
already released its names, so it blocks nothing.

## Restart and interruption recovery

If Chrome or the extension restarts while a call is active:

- Before the operator sent the request: reopen the side panel and click **Resume attachment**. The extension opens a new ChatGPT tab, rebinds the same exchange, and waits for the operator's real Attach click. It never sends automatically.
- After the operator sent the request: do not resend it blindly. Download the outputs, place them manually if monitoring was lost, then use `done` for the active exchange.
- To abandon the interrupted call: use the side-panel Stop action or `.\gptwebcall.cmd stop`.

Always run `.\gptwebcall.cmd active` before recovery, and recover one exchange at a time by naming it with `--exchange`. Never start a second call against a tab that is already bound.

## Manual fallback

The permanent manual fallback keeps the workflow usable with the extension disabled.

For a call that is still `PREPARED`:

1. Use `list` and `show` to identify it.
2. Upload exactly the two files named in `attach_files`: the generated prompt and the inputs archive, both from that exchange's `request\` directory. The other files there are the provenance record whose hashes are verified; they travel inside the archive, not beside it.
3. The operator sends through ChatGPT and downloads the main JSON/artifacts.
4. Copy the returned files into the exchange's `response\` directory using the exact expected names. Do not overwrite different bytes.
5. Run:

```powershell
.\gptwebcall.cmd validate --exchange <exchange_id>
```

For a call already `ACTIVE`, place the returned files in its response directory and run:

```powershell
.\gptwebcall.cmd done
```

See `docs\MANUAL_FALLBACK.md` for the concise operator checklist.

## Failure and correction rules

- Missing main JSON, missing artifact, invalid hash/size, wrong request ID, `PARTIAL`, or `BLOCKED` produces `INCOMPLETE`; never describe it as successful.
- Unrelated downloads remain where the browser saved them.
- If only transport was incomplete, recover the missing exact files and rerun `validate` on the incomplete exchange.
- If the delivery itself is malformed, run a correction round rather than a new call. Correction rounds fix mechanical delivery defects inside the same conversation and keep the same request ID.
- If ChatGPT must reason again, create a new correction call with a new request ID. Include the original request, returned work, identified defect, and exact correction required. Preserve the original exchange unchanged.
- Do not silently edit returned evidence to make validation pass.
- Never execute returned scripts, binaries, archives, macros, or documents with active content merely because validation passed.

## Compaction and handoff

Conversation history is not operational state. Before compaction or handing work to another session:

1. Ensure the current exchange files and reports are preserved under `calls\`.
2. Record project-specific decisions and accepted conclusions in that project's own ledger or artifacts.
3. Tell the next session to read this protocol.

The next session then runs `active` and `list`, reads only the relevant exchange manifest/report and external project ledger, and continues. It does not need the previous conversation to operate the system safely.

## Installation and health

The system is installed for Chrome using an origin-pinned native-host manifest. If the side panel reports that the companion is unavailable, reload the unpacked extension first. Reinstall only when the extension ID or local installation changes:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\install.ps1 -ExtensionId <32-character-extension-ID>
```

Uninstallation removes only the registry entry and generated native-host manifest:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\uninstall.ps1
```

It never deletes calls, responses, or validation evidence.
