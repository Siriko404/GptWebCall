# GPT Web Call Protocol

Canonical root: `C:\GptWebCall`

This is the one operating instruction for Codex and Claude Code. The filesystem in this root is authoritative. There is one active call globally.

## Triage

Before substantive work, decide whether the task is reasoning-heavy: planning, consequential technical or academic judgment, investigation, deep research, multi-file synthesis, ambiguous trade-offs, or a substantial review/artifact. For reasoning-heavy work, prepare one bounded Web call. Routine deterministic work may proceed locally.

Do not use a Web call for implementation of this system itself unless Sina explicitly asks.

## Prepare

Create a preparation spec containing the task's `subject`, `request_id`, `expected_main_json`, `prompt_text`, and explicit `input_files`. The inputs must include `WEB_REVIEW_REQUEST.json` and `WEB_RESPONSE_SCHEMA.json`. Run:

```powershell
.\gptwebcall.cmd prepare --spec C:\path\to\spec.json
```

The companion creates `calls\YYYY-MM-DD_HHMMSS_short_subject\request\` and generates `PROMPT_YYYY-MM-DD_HHMMSS.txt` with the same timestamp. It snapshots only the listed files and records their hashes in `EXCHANGE_MANIFEST.json`.

The request file must name the authority hierarchy, exact task, research permissions, expected outputs, acceptance criteria, and whether artifacts are required. The prompt directs ChatGPT Web to return no conversational text: only the downloadable main JSON and listed artifacts.

## Extension lifecycle

1. Load `extension\` unpacked in Chrome after installation.
2. Select the prepared call and click **Go**.
3. The extension opens ChatGPT and waits for you to click its real **Attach files** control.
4. Only after that click, it assigns exactly the manifest-approved request paths. Review them and use ChatGPT's native **Send** control yourself.
5. Manually download the main JSON and every artifact ChatGPT returns. The extension observes downloads during this call; the companion moves only files bound to the active call.
6. Click **Done and validate**. Monitoring stops immediately and validation reports either `COMPLETE` or specific missing/invalid files.

The extension never presses Send and never reads ChatGPT's response page. It does not capture unrelated downloads: unmatched files stay in Downloads.

## Response contract

The expected main JSON filename is fixed by the call manifest. It must bind to the active `request_id`, contain `status` (`COMPLETE`, `PARTIAL`, or `BLOCKED`), `artifacts_manifest`, and `delivery`.

Every created artifact in `artifacts_manifest` must state exact `filename`, `status`, `media_type`, byte `size`, and SHA-256 `sha256`; each must also appear in `delivery`. The main JSON is advisory. After deterministic validation, Codex or Claude Code must still check the intellectual work against the supplied authority.

## Recovery and manual fallback

Use `python -m companion.cli --root <root> list` to list prepared calls. If Chrome restarts, the side panel can show the active call; either stop it or continue the manual workflow. Do not run a second call while `state\ACTIVE_CALL.json` exists.

The manual fallback is permanent: upload every file listed by the exchange's `EXCHANGE_MANIFEST.json` from `request\`, download the JSON/artifacts yourself, then place them in `response\` using their expected names. Run `python -m companion.native_host --root <root>` only through the extension/native host; use `call.done` through the extension to create the validation report. See `docs\MANUAL_FALLBACK.md` for the safe recovery procedure.

## Installation

Build and install with:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\install.ps1 -ExtensionId <Chrome-extension-ID>
```

The installer origin-pins the native host to that extension ID under the current user only. `uninstall.ps1` removes only that registration and its generated manifest; it never deletes calls or responses.
