# GPT Web Call

Hand one bounded task from a coding-agent session to ChatGPT Web, and get back files you can verify.

A coding agent — Claude Code, Codex — is good at knowing your project and bad at being a second opinion on it. This is the bridge: the agent packages a task, you send it in your own browser, and the companion checks what comes back against what the response claimed it sent.

**You stay in the loop by construction.** The extension has no way to send a message. It fills a file chooser *you* opened, then detaches. It never reads the response page.

```
agent prepares  →  you: Go → Attach → Send  →  you download  →  companion validates
   (2 files)         (your browser, your click)                  (hashes, sizes, names)
```

## What it does not do

Listed first because it is the point.

- Never presses Send. There is no code path that submits a ChatGPT message.
- Never reads or scrapes the response page. Output arrives only as files you download.
- Never touches cookies, credentials, session tokens, or ChatGPT's private endpoints.
- Never uploads a directory. Only the files a preparation spec names, snapshotted and hashed first.
- Never executes what comes back, however cleanly it validated.
- Never moves a download it cannot bind to a specific call. Unrelated downloads stay where Chrome put them.

## Requirements

| | |
|---|---|
| Windows | the installer registers a Chrome native host under `HKCU` and the extension asserts Windows attachment paths |
| Google Chrome 125+ | `minimum_chrome_version` in the extension manifest |
| Python 3.10+ on PATH | the companion. Standard library only — nothing to `pip install` |
| Go 1.24+ | builds a 53-line launcher that starts the companion. Not a runtime dependency |
| PowerShell | install and uninstall scripts |

Node is needed only to run the extension's tests. The extension has no dependencies and no build step.

macOS and Linux are not supported. Some Python is portable, but the installer, the registry key, and the attachment path checks are not.

## Install

**Order matters.** Chrome derives an unpacked extension's ID from where it sits on disk, and the host manifest must pin that exact ID. So the extension is loaded first, and its ID is passed to the installer.

**1. Clone somewhere you intend to keep it.** The generated host manifest contains an absolute path; moving the repository means installing again.

```powershell
git clone https://github.com/Siriko404/GptWebCall.git
cd GptWebCall
```

**2. Run the tests.** If these fail, stop — installing will not help.

```powershell
go test ./... -race -count=1
python -m unittest discover -s companion/tests
npm --prefix extension test
```

**3. Load the extension.** In `chrome://extensions`: enable **Developer mode** → **Load unpacked** → select this repository's `extension` directory. Copy the 32-character ID Chrome shows.

**4. Register the native host.**

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\install.ps1 -ExtensionId <the-32-character-id>
```

It checks every prerequisite before writing anything, then verifies what it wrote. Add `-WhatIf` to see the plan without changing your machine.

**5. Reload the extension** in `chrome://extensions` and open its side panel. A green dot means the companion answered.

If the panel says the companion is unavailable, reload the extension before reinstalling — a stale service worker is the common cause.

## Use it

Point your agent session at [`WEB_CALL_PROTOCOL.md`](WEB_CALL_PROTOCOL.md). That file is the complete operating contract: how to decide a task is worth a call, how to construct the request, what the response must contain, how validation reads, and how to recover. It is written to be handed to a fresh session with no other context.

The agent prepares a call:

```powershell
.\gptwebcall.cmd list                          # what is ready
.\gptwebcall.cmd prepare --spec C:\path\spec.json
.\gptwebcall.cmd active                        # what is running
```

Then you drive it: **Go** → click ChatGPT's own **Attach files** → review what attached → **Send** → download each returned file → **Done and validate**.

Several calls can run at once, each bound to its own tab, as long as no two expect the same filename — attribution is by filename, because Chrome does not tell an extension which tab produced a download.

Full command reference is in the protocol. `delete`, `stop`, `validate`, `defects`, and `repair` cover the recovery paths.

### Everything lands on disk

```
calls/2026-08-08_141310_shipinfra/
  EXCHANGE_MANIFEST.json     identity, state, expected filenames, hashes
  request/                   the frozen snapshot that was uploaded
  response/                  what came back
  validation/VALIDATION_REPORT.json
```

The filesystem is the database. No server, no SQLite, nothing to migrate. An exchange survives your agent losing its context, and the next session reads the manifest rather than the conversation.

## How the attachment works

The extension attaches Chrome's debugger to the tab it opened and enables file-chooser interception ([`Page.setInterceptFileChooserDialog`](https://chromedevtools.github.io/devtools-protocol/tot/Page/#method-setInterceptFileChooserDialog)). When *you* click ChatGPT's attach control, Chrome emits the event instead of showing a picker; the extension assigns exactly the approved paths ([`DOM.setFileInputFiles`](https://chromedevtools.github.io/devtools-protocol/tot/DOM/#method-setFileInputFiles)) and detaches immediately.

That is why the tab shows Chrome's "being debugged" banner until your files are attached, and why nothing happens until you click.

The companion runs as a [native-messaging host](https://developer.chrome.com/docs/extensions/develop/concepts/native-messaging): a small Go launcher registered with Chrome that starts `python -m companion.native_host`. File bytes never cross that channel — only commands, names, and results.

## Reading a validation report

`status: COMPLETE` means the **delivery** was intact: every promised file arrived and hashes to what the response said. It says nothing about whether the reasoning is right — that judgement is yours and your agent's.

Three fields, three different facts:

| field | answers |
|---|---|
| `status` | did every promised file arrive intact |
| `response_status` | did the responder say it finished — `COMPLETE`, `PARTIAL`, `BLOCKED` |
| `manifest_verified` | were the responder's declared hashes usable at all |

A `PARTIAL` response delivered intact is `status: COMPLETE`, `response_status: PARTIAL`. Read it — the files are perfect and the responder has told you where its gaps are.

When `manifest_verified` is `false`, the responder's own manifest was malformed, so the files were checked structurally rather than against declared hashes. The bytes are present and sound; the binding is weaker. Weigh it accordingly.

## Without the extension

The manual path is permanent, not a fallback that rots. Upload the two files a call names in `attach_files`, drop the returned files into its `response/` directory, and run `validate --exchange <id>`. See [`docs/MANUAL_FALLBACK.md`](docs/MANUAL_FALLBACK.md).

## Known limits

- Windows and Chrome only.
- The companion looks for downloads in `%USERPROFILE%\Downloads`. If Chrome saves elsewhere, set `GPTWEBCALL_DOWNLOADS_DIR`, or pass `--downloads-dir` when validating.
- Unclaimed downloads accumulate in `state/PENDING_DOWNLOADS.json` and are not pruned automatically.
- `tests/e2e/` still encodes an older request contract and is not yet a release gate. The unit suites are current.

## Uninstall

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\uninstall.ps1
```

Removes the registry entry and the generated host manifest, and nothing else. Your calls, responses, and validation evidence stay. Remove the extension separately in `chrome://extensions`.

## License

MIT. See [LICENSE](LICENSE).
