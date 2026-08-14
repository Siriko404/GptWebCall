---
name: menu
description: Every GPT Web Call action other than installing and preparing — status, health, finish, recover, repair, stop, delete, manual fallback, watch, local responder. Use only when the user explicitly invokes this workflow.
disable-model-invocation: true
---

# `/webcall:menu`

Read [OPERATING_CORE](../../references/OPERATING_CORE.md). Treat the first
argument as the action. With no argument, print only this list and ask which:

`status` · `health [smoke]` · `finish <id>` · `recover <id>` · `repair <id>` ·
`stop <id>` · `delete <id>` · `manual <id>` · `watch [id]` · `local <id>`

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
message the extension sends. Also report anything stale: entries in
`state/PENDING_DOWNLOADS.json` whose files no longer exist, and records in
`state/active/` with no matching `ACTIVE` manifest. With `smoke`, run
[SMOKE_TEST](../../references/SMOKE_TEST.md).

If the panel reports the companion unavailable, the first remedy is the panel's
own **Reload extension** button, or a reload in `chrome://extensions` — a stale
service worker is the common cause. Reinstalling is the second remedy, not the
first, and it needs the extension ID again.

### `finish <id>`
Prefer the side panel's **Done and validate** once the expected files have
landed; it holds Done back until they do, and forcing it is a deliberate act.
`done --exchange <id>` is the equivalent without the extension, and it also
ingests from the Downloads folder. Then read the report: delivery `COMPLETE`
with responder `PARTIAL` or `BLOCKED` means read the limitations and do semantic
acceptance — not repair. Delivery `INCOMPLETE` means run `defects`.

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

### `manual <id>`
For a `PREPARED` exchange: `show` it, upload exactly the two files in
`attach_files`, let the operator send and download, copy the returned files into
`response\` under their exact expected names, then `validate --exchange <id>`.
For an `ACTIVE` exchange with files already placed, `done --exchange <id>`.
Never silently overwrite different bytes.

### `watch [id]`
Run `python scripts/watch_exchange.py [id]` in the background when the agent
cannot click through the exchange itself. It prints nothing until a terminal
state, then one line. With several exchanges in flight and no ID, it refuses to
guess.

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
- Inventing a fourth user-facing command. Unknown action: show the list and read
  the matching section of the installed protocol.

## Proof it worked

Each action has an observable postcondition: `status` returns current JSON;
`health` names every check and its result; `finish` writes a validation report;
`recover` continues the same exchange; `repair` records a round only when
defects existed; `stop` records `STOPPED`; `delete` reports the freed names;
`manual` validates the placed files; `watch` emits one terminal line; `local`
validates a locally produced response.
