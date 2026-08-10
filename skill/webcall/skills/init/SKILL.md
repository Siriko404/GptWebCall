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
5. **Load the extension before registering the host.** Ask the operator to open
   `chrome://extensions`, enable Developer mode, **Load unpacked** on
   `<root>\extension`, and read back the 32-character ID. Never invent it: the
   ID is derived from the path on disk and the installer cannot pin an origin
   that does not exist yet. `[scripts/install.ps1; README.md]`
6. **Register the native host.**

   ```powershell
   powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\install.ps1 -ExtensionId <id>
   ```

   It checks every prerequisite before writing anything, builds the Go launcher,
   renders the host manifest, writes the `HKCU` key, then re-reads what it wrote.
   `-WhatIf` shows the plan and changes nothing.
7. **If it warns that Chrome's download directory differs** from the companion's
   default, set exactly the `GPTWEBCALL_DOWNLOADS_DIR` value it prints, then
   restart Chrome.
8. **Reload the extension and open the side panel.** A green dot means the
   companion answered the native `health` message. If it says unavailable,
   reload the extension before reinstalling — a stale service worker is the
   common cause.
9. **Run the improvised smoke test** in
   [SMOKE_TEST](../../references/SMOKE_TEST.md). Do not substitute anything from
   `tests/e2e/`: `README.md` records that it encodes an older request contract
   and is not a release gate.
10. **Report**: the verified root, the prerequisite versions found, each suite's
    outcome, the native-health result, and the smoke exchange with its
    validation report. Keep every exchange local; never publish or transmit
    `calls/` or `state/`.

## Refuse

- Refuse to report success on macOS or Linux, with a missing runtime, with a
  failing suite that could run, with an unverified extension ID, with a failed
  installer postflight, with native health still unavailable after a reload, or
  with a failed smoke test.
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
