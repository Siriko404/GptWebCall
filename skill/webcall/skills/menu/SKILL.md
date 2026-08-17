---
name: menu
description: Every GPT Web Call action other than installing and preparing — status, health, finish, recover, repair, stop, delete, clone, manual fallback, watch, local responder. Use only when the user explicitly invokes this workflow.
disable-model-invocation: true
---

# `/webcall:menu`

Read [OPERATING_CORE](../../references/OPERATING_CORE.md). Treat the first
argument as the action. With no argument, print only this list and ask which:

`status` · `health [smoke]` · `finish <id>` · `recover <id>` · `repair <id>` ·
`stop <id>` · `delete <id>` · `clone <id>` · `manual <id>` · `watch <id>` ·
`local <id>`

Run `active` and `list` before any action that changes something. When more than
one call is in flight, name the exchange — never guess.

## Actions

### `status [id]`
`active`, `list`, and `show --exchange <id>` when named. Summarise only what the
operator needs to decide: state, subject, request ID, expected filenames,
validation status. Do not dump private response content.

### `health [smoke]`
Check, in order: the four root files exist; the wrapper runs (`active` and
`list` both return `ok: true`); the `HKCU` registry value points at a host
manifest that exists and pins one extension origin; the side panel shows its
green dot. **There is no `gptwebcall.cmd health`** — `health` is a native-host
message the extension sends. Also report anything stale: records in
`state/active/` with no matching `ACTIVE` manifest, and a leftover
`state/PENDING_DOWNLOADS.json`, which nothing writes any more — the pool it
belonged to is gone and the file can be deleted. With `smoke`, run
[SMOKE_TEST](../../references/SMOKE_TEST.md).

If the panel reports the companion unavailable, the first remedy is the panel's
own **Reload extension** button, or a reload in `chrome://extensions` — a stale
service worker is the common cause. If that does not fix it, check the pinned
origin: `python scripts/extension_id.py` reports the ID Chrome has for this
checkout, and it must match `allowed_origins` in
`native-host\com.sina.gptwebcall.json`. Reinstalling with `python
scripts/setup.py` is the last remedy, not the first.

### `finish <id>`
Prefer the side panel's **Done and validate** once the expected files have
landed; it holds Done back until they do, and forcing it is a deliberate act.
`done --exchange <id>` is the equivalent without the extension, and it also
ingests from the Downloads folder. Then read the report: delivery `COMPLETE`
with responder `PARTIAL` or `BLOCKED` means read the limitations and do semantic
acceptance — not repair. Delivery `INCOMPLETE` means run `defects`.

**The panel will not tell you this part.** It shows the delivery state and
nothing else, deliberately: `response_status` and `manifest_verified` live in
`validation\VALIDATION_REPORT.json`, and reading them is your job, not the
panel's. A row saying `COMPLETE` means the files arrived intact — never that the
work is good.

### `recover <id>`
Run `active` first. If the request was never sent, use the panel's **Resume
attachment** and continue the same exchange. If it was sent, do not resend:
download the outputs, place them in the exchange if monitoring was lost, then
finish. One exchange at a time.

### `repair <id>`
`defects --exchange <id>` first. Repair only a mechanically `INCOMPLETE`
delivery. The panel's correction round reuses the same conversation and request
ID and never sends by itself. Refuse when there are no delivery defects, or when
the only complaint is an honest `PARTIAL`.

### `stop <id>`
Only for an active call the operator wants to abandon. Records `STOPPED` and
keeps every file.

### `delete <id>`
For a superseded call that is not running, to remove it and free its routing
names. Never on a running call. If a response has landed, refuse unless the
operator explicitly chooses to discard it, and only then pass `--force`.

### `clone <id>`
To ask the same question again. Builds a new `PREPARED` exchange from the
finished one's own inputs and leaves the original alone — its response is the
only copy of work the model already did, so nothing is overwritten. The copy is
not sent; that is a separate, deliberate **Go**.

This is the only way out of `STOPPED`, which `go`, `done` and `repair` each
refuse. The panel has it as **Prepare a copy** on a finished call's row.
Refused while the source is `PREPARED` or `ACTIVE`: it has not finished, and it
still holds the deliverable names the copy would need.

### `manual <id>`
For a `PREPARED` exchange: `show` it, upload the one archive in `attach_files`
with a typed line telling ChatGPT to open it and read `000_READ_ME_FIRST.md`
first, let the operator send and download, copy the returned files into
`response\` under their exact expected names, then `validate --exchange <id>`.
For an `ACTIVE` exchange with files already placed, `done --exchange <id>`.
Never silently overwrite different bytes.

### `watch <id>`
`wait --exchange <id>`, run in the background. It blocks and its **exit is the
notification** — the one way something that happens later reaches a session that
nothing can interrupt.

It reports every ending, not just the happy one: `COMPLETE`, `INCOMPLETE`,
`STOPPED`, `DELETED`, plus `REPAIR_OPENED` for a correction round (**not** an
ending — wait again) and `DOWNLOAD_FILING_FAILED` for a call still running whose
download could not be filed. Exit `0` an event, `1` your own timeout expired
(`STILL_WAITING`, which is not abandonment), `2` bad arguments, `3` the exchange
is unreadable — inspect, never treat as success.

Branch on `result.event`, never on the exit code alone. Being woken is not
permission to act: read the report and do semantic acceptance as usual. Use
`--after-current` to wait out a correction round on an already-`INCOMPLETE` call.
Never poll in a shell loop instead — the lifecycle rules live in one command so
they cannot drift per host.

### `local <id>`
Run a prepared exchange against an explicitly authorised local subagent instead
of ChatGPT Web. Do not arm a tab. The responder reads the loose snapshot files
under `request\`, writes the exact expected main JSON and optional outputs ZIP
into `response\`, computes real sizes and digests, and reports `PARTIAL` or
`BLOCKED` honestly. Write the main JSON as UTF-8 **without a BOM**:
`companion/repair.py` reads it as plain `utf-8` and a BOM breaks the correction
path. Then `validate --exchange <id>` and do semantic acceptance. Choose Web,
not a same-model local responder, whenever independence is the thing you are
buying.

## Always refuse

- Guessing which exchange is meant when several are live.
- Using mechanical repair to paper over a reasoning defect.
- Editing returned evidence so validation passes.
- Executing returned scripts or active content because validation passed.
- Retrying a failed download filing by guessing attribution. Filename is the
  only routing key; recover the file from the Downloads folder instead.
- Inventing a fifth user-facing command. Unknown action: show the list and read
  the matching section of the installed protocol.

## Proof it worked

Each action has an observable postcondition: `status` returns current JSON;
`health` names every check and its result; `finish` writes a validation report;
`recover` continues the same exchange; `repair` records a round only when
defects existed; `stop` records `STOPPED`; `delete` reports the freed names; `clone` returns a
new `PREPARED` manifest naming the call it came from;
`manual` validates the placed files; `watch` exits with one named event; `local`
validates a locally produced response.
