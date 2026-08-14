---
name: prep
description: Prepare one GPT Web Call — an unsteered request, an explicit file list, unique routing names, and a pre-send check. Two modes, bounded and conductor. Use only when the user explicitly invokes this workflow.
disable-model-invocation: true
---

# `/webcall:prep`

Read [OPERATING_CORE](../../references/OPERATING_CORE.md) first, then prepare
exactly one exchange unless the user asks for several independent calls.

## Two modes

Ask which, or take it from the user's words. They differ in exactly one respect.

**Bounded** — the default, and everything below assumes it unless stated. A
fresh conversation that has been told nothing. The request must therefore carry
everything needed to answer it. This is the mode for an independent reasoning
pass, an adversarial audit, a second opinion.

**Conductor** — the call lands in a long-running thread that has accumulated
context deliberately, such as Matt's. Only the self-containment requirement
relaxes: the thread already knows the project, so restating it wastes the
request and invites a stale duplicate of what it has. Attach what is *new* since
it last looked.

Everything else is identical, and one thing especially: **the ban on steering
applies in both, without exception.** Conductor mode permits relying on shared
history. It never permits shipping a preferred conclusion. The thread having
context is not licence to tell it what to think.

Say in one line which mode you prepared, and set the side panel to match —
a conductor call sent to a new conversation arrives without the context it was
written to assume, and a bounded call sent into a live thread is answered by a
model that has already been argued with.

## Do

1. **Resolve the root, then run `active` and `list`** before authoring anything.
   If the system is not installed, refuse and send the user to `init`.
2. **State the call's purpose in one sentence** and say why an independent
   reasoning pass is worth it. Invoking `prep` authorises preparing; it does not
   authorise clicking Go or Send.
3. **Write the assignment unsteered.** Separate measured facts, authority order,
   scope, the exact questions, acceptance criteria, and what is unknown. Strip
   answer-shaped premises, candidate lists, enum fields named after a design,
   deliverable filenames encoding a structure, and analytical asides. Before
   sending, apply the protocol's own test: *could an answer substantially better
   than mine, and structurally different, be expressed in this format and
   validate against this schema?* If not, rewrite it. **This step is identical
   in both modes.** `[WEB_CALL_PROTOCOL.md:24-71]`

   In conductor mode the test still applies in full; only the assumed starting
   knowledge moves. Ask it as: could the thread, knowing what it already knows,
   still reach a better and structurally different answer than mine?
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
    set the destination to match the mode you prepared — *Send in a new
    conversation* for bounded, *Send in the conversation I am in* for conductor,
    with the intended thread focused — select the call, click **Go**. Attach,
    Send, downloads, and Done stay with the operator.

## Refuse

- Refuse to prepare a steered request, in either mode. Neutralise it first, and
  say what was removed — a conclusion does not survive merely because the user
  suggested it.
- Refuse to treat conductor mode as licence to steer. It relaxes what the
  request must restate, nothing else.
- Refuse to prepare a bounded call that leans on context it does not carry, and
  a conductor call whose thread you cannot name.
- Refuse private `calls/`/`state/` content, directories, secrets, duplicate
  packaged names, and generic deliverable names.
- Refuse to omit either governing JSON, or to invent a schema the request does
  not support.
- Refuse `validate` as a pre-send check. Refuse to send.

## Proof it worked

`prepare` returns `ok: true`; `show` reports `PREPARED`, bound to the intended
request ID, with unique expected deliverables; `attach_files` names exactly two
frozen files; and `active` still shows no call started.
