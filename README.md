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

**Hand this file to Claude Code and say "install this".** The three steps below are all it needs. Two of them require your hands and are marked; Claude cannot click in Chrome.

**1. Clone somewhere permanent, and register the skills.** The generated host manifest stores an absolute path, so moving the repository afterwards means installing again — not a temporary directory.

```powershell
git clone https://github.com/Siriko404/GptWebCall.git
cd GptWebCall
python scripts/install_skill.py
```

That writes two keys into `~/.claude/settings.json` — the same two `/plugin marketplace add` and `/plugin install` write — and backs the file up first. `--dry-run` shows the change without making it.

**2. Restart Claude Code.** Commands register at startup, so `/webcall:*` appears in the next session, not the one that installed it.

If the commands are missing after the restart, type these two lines instead and restart again:

```text
/plugin marketplace add <path-to-this-repo>\skill\webcall
/plugin install webcall@webcall-local
```

**3. Run `/webcall:init`.** It takes over from here: checks your prerequisites, runs the three test suites, walks you through the two steps that need hands — loading the unpacked extension in `chrome://extensions` and reading back its 32-character ID — registers the native host with that ID, and finishes by running a live smoke test it invents on the spot rather than replaying a fixture.

It refuses to report success on a failed suite, an unverified extension ID, a failed installer postflight, or a failed smoke test.

## Use it

Everything runs through three commands.

| | |
|---|---|
| `/webcall:init` | install, or recheck an install, and smoke-test it |
| `/webcall:prep` | prepare one call: unbiased request, explicit file list, unique routing names, pre-send check |
| `/webcall:menu` | everything else — status, health, finish, recover, repair, stop, delete, manual fallback, watch, local responder |

Then you drive the browser half: **Go** → click ChatGPT's own **Attach files** → review what attached → **Send** → download each returned file → **Done and validate**. No skill does any of that for you, by design.

Several calls can run at once, each bound to its own tab, as long as no two expect the same filename — attribution is by filename, because Chrome does not tell an extension which tab produced a download.

[`WEB_CALL_PROTOCOL.md`](WEB_CALL_PROTOCOL.md) is the complete reference behind those commands — every rule, every command, every recovery path. It is not the operating surface: the skills are, and they cite it where it is needed. Read it to check a skill, or when operating by hand with the extension disabled.

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

The manual path is permanent, not a fallback that rots. Upload the one archive a call names in `attach_files`, drop the returned files into its `response/` directory, and run `validate --exchange <id>`. See [`docs/MANUAL_FALLBACK.md`](docs/MANUAL_FALLBACK.md).

## Known limits

- Windows and Chrome only.
- The companion looks for downloads in `%USERPROFILE%\Downloads`. The installer checks this against Chrome's own setting and tells you if they differ; set `GPTWEBCALL_DOWNLOADS_DIR` to fix it, or pass `--downloads-dir` when validating.
- `tests/e2e/` still encodes an older request contract and is not yet a release gate. The unit suites are current.

## Uninstall

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\uninstall.ps1
```

Removes the registry entry and the generated host manifest, and nothing else. Your calls, responses, and validation evidence stay. Remove the extension separately in `chrome://extensions`.

## License

MIT. See [LICENSE](LICENSE).
