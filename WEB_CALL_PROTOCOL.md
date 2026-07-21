# GPT Web Call Protocol

Canonical root: `C:\GptWebCall`

This file is the complete operating contract for any Codex or Claude Code session using the installed GPT Web Call system. Read it before operating the system. Do not infer workflow rules from old design files under `docs/history/`.

## Fresh-session contract

After reading this file, a new session must:

1. Treat the canonical root above as the system root and the filesystem there as operational authority.
2. Run `active` and `list` before preparing anything, so it does not collide with an existing call.
3. Classify the requested work before substantive reasoning.
4. Prepare a Web call only when the work is reasoning-heavy or Sina explicitly requests one.
5. Select only the context needed for that bounded call; never upload a repository or directory implicitly.
6. Explain to Sina what the prepared call will do, then let Sina control Attach, Send, downloads, and Done.
7. Treat the returned work as advisory even after deterministic file validation passes.
8. Preserve each exchange and record accepted conclusions in the external project's own ledger or artifacts.

There is one active call globally. The system is intentionally filesystem-only; `calls\`, `state\`, request snapshots, response files, manifests, and validation reports preserve continuity across sessions and compaction.

## Triage

Before substantive work, explicitly decide whether the task is reasoning-heavy.

Reasoning-heavy work includes planning or architecture, investigation or diagnosis, deep web research, high-stakes academic/technical/legal/financial judgment, synthesis across long or conflicting sources, ambiguous trade-offs, substantial artifact design, and audits that benefit from an independent reasoning pass.

Routine deterministic work includes direct file operations, mechanical formatting, running an approved plan, small unambiguous corrections, and exact lookups from a known authority.

- If reasoning-heavy: pause before the substantive reasoning and prepare a bounded Web call.
- If routine: proceed locally.
- If uncertain and the consequence matters: use a Web call.

Do not use a Web call to implement or repair GPT Web Call itself unless Sina explicitly requests that exception.

## Call decomposition and continuation

Do not mechanically pre-plan a long chain of calls when the correct reasoning process is itself uncertain. The first bounded call may be a planning/architecture call that asks ChatGPT Web to recommend the necessary reasoning stages, number and types of later calls, dependencies, and context required for each.

Codex or Claude Code then evaluates that advice and prepares only the next warranted exchange. Every later call is separately packaged and authorized by Sina. After each result, reassess whether to accept and integrate it, request criticism or correction, run another specialist call, or stop. ChatGPT Web may recommend the process, but it does not create active calls, choose private files, or bypass Sina's authorization.

## Roles and control boundary

- Codex or Claude Code classifies the work, chooses context, creates the request, prepares the exchange, checks the returned work, and integrates only accepted conclusions.
- ChatGPT Web performs the bounded assignment. It may reason, research when authorized, investigate, plan, or create requested artifacts.
- Sina authorizes every call. Sina clicks **Go**, ChatGPT's real **Attach files**, ChatGPT's native **Send**, each download control, and **Done and validate**.
- The extension never presses Send and never reads ChatGPT's response page.
- The companion moves only downloads deterministically bound to the active call. Unrelated downloads remain untouched.

## Status check and command location

Commands may be run from the canonical root:

```powershell
cd C:\GptWebCall
.\gptwebcall.cmd active
.\gptwebcall.cmd list
```

From another directory, invoke the wrapper by absolute path:

```powershell
& 'C:\GptWebCall\gptwebcall.cmd' active
```

Every CLI command emits one JSON object. `ok: true` contains `result`; `ok: false` contains `error` and exits nonzero.

## Exact request construction

Every call needs three things before preparation:

1. `WEB_REVIEW_REQUEST.json` — the intellectual assignment and authority contract.
2. `WEB_RESPONSE_SCHEMA.json` — the requested response structure supplied to ChatGPT.
3. A preparation spec — tells the local companion what to snapshot and what main filename to expect.

Use a unique, stable `request_id` in both the request and preparation spec. Use a concise, safe subject. Give every source an explicit packaged filename. Use absolute source paths. Never supply a prompt file: the companion generates `PROMPT_YYYY-MM-DD_HHMMSS.txt` itself.

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

### Preparation-spec template

Store this temporary spec anywhere safe. Operational scratch under `state\` is ignored by Git.

```json
{
  "subject": "Short call subject",
  "request_id": "unique-project-task-v1",
  "expected_main_json": "unique_project_task_response.json",
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

`created_at` is optional. Normally omit it so the companion uses the current local time. The companion verifies the two governing JSON files, checks `request_id`, copies only the enumerated files, hashes the snapshots, and publishes the exchange atomically.

Prepare and inspect:

```powershell
.\gptwebcall.cmd prepare --spec C:\absolute\path\prepare_spec.json
.\gptwebcall.cmd list
.\gptwebcall.cmd show --exchange YYYY-MM-DD_HHMMSS_short_subject
```

Before telling Sina to click Go, verify the manifest lists exactly the intended files, the subject and request ID are correct, and `expected_main_json` is unambiguous.

## Normal extension workflow

1. Sina opens the GPT Web Call side panel and selects the prepared call.
2. Sina clicks **Go**. The companion verifies the frozen request files; monitoring starts; ChatGPT opens.
3. The extension waits. Sina clicks ChatGPT's real **Attach files** control.
4. The extension assigns exactly the manifest-approved request files to that chooser and detaches its debugger immediately.
5. Sina reviews the filenames and clicks ChatGPT's native **Send**.
6. ChatGPT returns only downloadable files: the main JSON and any additional artifacts.
7. Sina manually downloads every output. Files may be downloaded in any order. Artifacts downloaded before the main JSON remain pending until the main JSON identifies them.
8. Sina clicks **Done and validate**. Monitoring stops first; the companion validates and writes `validation\VALIDATION_REPORT.json`.
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

ChatGPT Web output remains advisory. Sina retains final authority.

## Correction rounds

When validation reports `INCOMPLETE`, the cause is usually mechanical rather than intellectual: a declared SHA-256 that does not match the delivered bytes, an artifact named in the manifest but never downloaded, a `PARTIAL` status, or a `delivery` list that omits a created file. Reasoning again from scratch is the wrong response to that.

A correction round diagnoses the exact defects and sends them back into the same conversation.

1. `.\gptwebcall.cmd defects --exchange <exchange_id>` lists every defect as a structured record with `kind`, `target`, `expected`, and `observed`. It reads only; it changes nothing.
2. The side panel's **Send correction round** button calls `call.repair`. The companion writes `repair\ROUND_N_PROMPT.txt` and `repair\ROUND_N_DEFECTS.json` inside the exchange, records the round in the manifest, and re-arms monitoring with a fresh download baseline.
3. The extension types the correction prompt into the composer of the bound tab and stops. It never presses Send. Sina reviews the prompt and sends it. If the composer cannot be found, the prompt is still written to disk and shown in the side panel with a copy control.
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
.\gptwebcall.cmd stop
.\gptwebcall.cmd validate --exchange <exchange_id>
.\gptwebcall.cmd defects --exchange <exchange_id>
.\gptwebcall.cmd repair --exchange <exchange_id> --tab <tab_id>
```

- `prepare`: snapshot and hash one new call package.
- `list`: list calls currently in `PREPARED` state.
- `show`: read one exchange manifest.
- `active`: show the active-call record or `null`.
- `done`: stop and deterministically validate the active call without the extension.
- `stop`: abandon the active call and record `STOPPED` without deleting evidence.
- `validate`: validate files manually placed into a non-active prepared or incomplete exchange.
- `defects`: report every validation defect in a delivered response without changing anything.
- `repair`: open a correction round, write its prompt and defect record, and re-arm monitoring.

## Restart and interruption recovery

If Chrome or the extension restarts while a call is active:

- Before Sina sent the request: reopen the side panel and click **Resume attachment**. The extension opens a new ChatGPT tab, rebinds the same exchange, and waits for Sina's real Attach click. It never sends automatically.
- After Sina sent the request: do not resend it blindly. Download the outputs, place them manually if monitoring was lost, then use `done` for the active exchange.
- To abandon the interrupted call: use the side-panel Stop action or `.\gptwebcall.cmd stop`.

Always run `.\gptwebcall.cmd active` before recovery. Never create or start a second active call.

## Manual fallback

The permanent manual fallback keeps the workflow usable with the extension disabled.

For a call that is still `PREPARED`:

1. Use `list` and `show` to identify it.
2. Upload exactly the files listed in `request_files` from that exchange's `request\` directory.
3. Sina sends through ChatGPT and downloads the main JSON/artifacts.
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
