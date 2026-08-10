---
name: prep
description: Prepare one bounded GPT Web Call — an unbiased request, an explicit file list, unique routing names, and a pre-send check. Use only when the user explicitly invokes this workflow.
disable-model-invocation: true
---

# `/webcall:prep`

Read [OPERATING_CORE](../../references/OPERATING_CORE.md) first, then prepare
exactly one exchange unless the user asks for several independent calls.

## Do

1. **Resolve the root, then run `active` and `list`** before authoring anything.
   If the system is not installed, refuse and send the user to `init`.
2. **State the call's purpose in one sentence** and say why an independent
   reasoning pass is worth it. Invoking `prep` authorises preparing; it does not
   authorise clicking Go or Send.
3. **Write the assignment unbiased.** Separate measured facts, authority order,
   scope, the exact questions, acceptance criteria, and what is unknown. Strip
   answer-shaped premises, candidate lists, enum fields named after a design,
   deliverable filenames encoding a structure, and analytical asides. Before
   sending, apply the protocol's own test: *could an answer substantially better
   than mine, and structurally different, be expressed in this format and
   validate against this schema?* If not, rewrite it.
   `[WEB_CALL_PROTOCOL.md:24-71]`
4. **Choose the smallest sufficient `input_files`.** Always the governing
   `WEB_REVIEW_REQUEST.json` and `WEB_RESPONSE_SCHEMA.json`; then only the
   regular files needed to answer. Never a directory, never credentials or
   tokens, never anything from `calls/` or `state/`.
5. **Pick a stable `request_id` and a short pass token.** Deliverables are
   `<pass>_response.json` and, when extra files are needed,
   `<pass>_outputs.zip`. Check `active` and `list`; `prepare` enforces the
   reservation and will name the call already holding a taken name.
6. **Write the request and the schema.** The request carries persona, objective,
   authority hierarchy, scope, questions, acceptance criteria, and a stop
   condition. Pin the schema fully — a bare `"artifacts_manifest": {"type":
   "array"}` invites the model to invent keys and produces a false `INCOMPLETE`
   on correct work. Tell it in one line to reproduce the field names verbatim.
7. **Get the two lists right.** `delivery` names only the downloadable files.
   `artifacts_manifest` names every created additional file, archive members
   included, each with exact size and SHA-256 — and never the main JSON, which
   the parser rejects as self-listing. Members that must be hash-verified need
   unique plain basenames with no path separators.
8. **Write the spec.** Non-empty `input_files`, the expected main JSON,
   optionally one outputs ZIP, and `prompt_text` that says the two attached
   files are the whole package, requires the inputs ZIP to be extracted, and —
   when thoroughness is the point — requires a file-by-file inventory with byte
   sizes before any analysis.
9. **Prepare, then inspect.**

   ```powershell
   & '<root>\gptwebcall.cmd' prepare --spec <spec>
   & '<root>\gptwebcall.cmd' show --exchange <id>
   ```

   Confirm: state `PREPARED`, the request ID, the expected names, `attach_files`
   exactly the prompt plus the inputs ZIP, and the packaged input names matching
   intent. Do not run `validate` — it refuses an unanswered call by design.
10. **Hand off.** Give the exchange ID and one next action: open the side panel,
    select the call, click **Go**. Attach, Send, downloads, and Done stay with
    the operator.

## Refuse

- Refuse to prepare a biased request. Neutralise it first, and say what was
  removed — a conclusion does not survive merely because the user suggested it.
- Refuse private `calls/`/`state/` content, directories, secrets, duplicate
  packaged names, and generic deliverable names.
- Refuse to omit either governing JSON, or to invent a schema the request does
  not support.
- Refuse `validate` as a pre-send check. Refuse to send.

## Proof it worked

`prepare` returns `ok: true`; `show` reports `PREPARED`, bound to the intended
request ID, with unique expected deliverables; `attach_files` names exactly two
frozen files; and `active` still shows no call started.
