---
name: init
description: Install GPT Web Call from scratch, or recheck an existing installation, and finish with a freshly improvised live smoke test. Use only when the user explicitly invokes this workflow.
disable-model-invocation: true
---

# `/webcall:init`

Read [OPERATING_CORE](../../references/OPERATING_CORE.md) first. Read
[SMOKE_TEST](../../references/SMOKE_TEST.md) only when you reach step 9.

## Do

1. **Look for an existing installation before anything else.** Resolve the root
   the way the core describes. If one verifies, do not clone a second copy —
   recheck and repair that one.
2. **Confirm the host is supported.** Windows, Chrome 125+, Python 3.10+,
   Go 1.24+, PowerShell. macOS and Linux are not supported. Node is needed only
   to run the extension's tests. `[README.md "Requirements"]`
3. **If there is no checkout, clone to somewhere permanent.** Use a target the
   user names, otherwise `$HOME\GptWebCall` if free. Never a temporary
   directory: the generated host manifest stores absolute paths, and moving the
   repository means installing again. `[README.md "Install"]`
4. **Run the tests before writing any system state.**

   ```powershell
   go test ./... -race -count=1
   python -m unittest discover -s companion/tests
   npm --prefix extension test
   ```

   If a suite that can run fails, stop and report the exact command. Node being
   absent is a gap in verification, not a blocker to installing.
5. **Install both halves with one command.**

   ```powershell
   python scripts/setup.py
   ```

   It registers the native-messaging host and the skills. Every prerequisite is
   checked before anything is written, the Go launcher is built, the host
   manifest and `HKCU` key are written and then re-read. `--dry-run` shows the
   plan and changes nothing.

   **Never ask the operator for the extension ID.** It is derived from the
   extension's path, read from Chrome's own profile data when the extension is
   already loaded, and reported either way. `[scripts/extension_id.py]`
6. **If it warns that Chrome's download directory differs** from the companion's
   default, set exactly the `GPTWEBCALL_DOWNLOADS_DIR` value it prints, then
   restart Chrome.
7. **Ask the operator for the two steps nothing else can do.** Loading the
   unpacked extension from `<root>\extension` in `chrome://extensions` — or
   reloading it if it is already there — and restarting Claude Code if the
   skills were registered in this session.
8. **Confirm the pinned ID against Chrome, then the side panel.** Rerun
   `python scripts/extension_id.py`: once the extension is loaded, `source`
   becomes `chrome`, and that id must equal the one in
   `native-host\com.sina.gptwebcall.json`. If it does not, rerun the installer
   with `-ExtensionId` and the value Chrome reports. Then the side panel: a
   green dot means the companion answered the native `health` message. If it
   says unavailable, reload the extension before reinstalling — a stale service
   worker is the common cause.
9. **Run the improvised smoke test** in
   [SMOKE_TEST](../../references/SMOKE_TEST.md). Do not substitute anything from
   `tests/e2e/`: `README.md` records that it encodes an older request contract
   and is not a release gate.
10. **Report, then hand over the short guide.** Report the verified root, the
    prerequisite versions found, each suite's outcome, the resolved extension ID
    and where it came from, the native-health result, and the smoke exchange
    with its validation report. Keep every exchange local; never publish or
    transmit `calls/` or `state/`.

    Then give the operator this and nothing longer:

    > `/webcall:prep` — describe a task; it writes the request, freezes the
    > files, and hands you an exchange to launch.
    > `/webcall:menu` — everything else: status, health, finish, repair, stop.
    > In the panel: **Go** → ChatGPT's own **Attach files** → check what
    > attached → **Send** → download the one archive → **Done and validate**.
    > Those clicks are yours by design. The extension never sends and never
    > reads the reply page.

## Refuse

- Refuse to report success on macOS or Linux, with a missing runtime, with a
  failing suite that could run, with a pinned extension ID that Chrome
  contradicts, with a failed installer postflight, with native health still
  unavailable after a reload, or with a failed smoke test.
- Refuse to ask the operator to read an extension ID off `chrome://extensions`.
  It is resolved, and asking for it is how the step used to be got wrong.
- Refuse to click Go, Attach, Send, or Done for the operator, or to automate
  around them.
- Refuse to use a prepared package or a repository fixture as the smoke test.
- Refuse to include anything from `calls/` or `state/` anywhere.

## Proof it worked

A machine that has never run this passes `init` only when the installer's
postflight succeeds, the reloaded side panel shows native health, every
available unit suite passes, and a smoke exchange authored fresh in this session
validates `COMPLETE` with `response_status: COMPLETE`, `manifest_verified: true`,
and a receipt carrying the token and digest generated minutes earlier.
