# Minimal ChatGPT Web Call Architecture

**Status:** Approved design
**Owner:** Sina
**Canonical root:** `C:\GptWebCall`
**Supersedes:** `2026-07-14-global-system-design.md` as the implementation target

## 1. Goal

Build the smallest reliable system that prepares one ChatGPT Web call, attaches its request files after Sina clicks ChatGPT's **Attach files** control, watches the downloads Sina starts manually, moves matching outputs into the correct response folder, and stops monitoring when Sina clicks **Done**.

The system never presses ChatGPT's Send button and never reads the response page.

## 2. Components

### Chrome extension

A Manifest V3 side-panel extension provides:

- the active call summary;
- **Go**;
- attachment status;
- captured-download status;
- **Done**;
- missing-output and recovery messages.

Its required permissions are limited to:

- `sidePanel`;
- `nativeMessaging`;
- `debugger`, used only to intercept the user-opened file chooser and assign approved request paths;
- `downloads`, used only while one call is active to observe downloads the user starts;
- `storage`, for non-authoritative UI recovery data.

It does not request cookies, `webRequest`, all-sites access, or response-page scraping access.

### Python companion

A small Python standard-library program serves both as:

- the Chrome native-messaging host; and
- a command-line utility usable by Codex or Claude Code.

It owns filesystem access, package discovery, response movement, hashes, JSON validation, and the single active-call record. It exposes a small command allowlist rather than arbitrary shell or path operations.

### Filesystem

The filesystem is the database. There is no SQLite database, event-sourcing layer, global project graph, or background service in the first version.

Only one call may be active globally.

## 3. Call layout

```text
GptWebCall/
  WEB_CALL_PROTOCOL.md
  extension/
  companion/
  scripts/
  calls/
    YYYY-MM-DD_HHMMSS_short_subject/
      EXCHANGE_MANIFEST.json
      request/
        PROMPT_YYYY-MM-DD_HHMMSS.txt
        WEB_REVIEW_REQUEST.json
        WEB_RESPONSE_SCHEMA.json
        ...approved context files...
      response/
        ...validated downloaded files...
      validation/
        VALIDATION_REPORT.json
  state/
    ACTIVE_CALL.json
```

The timestamp in the exchange folder and prompt filename must be identical. Every uploadable file is explicitly listed in `EXCHANGE_MANIFEST.json`; the extension never uploads an entire directory implicitly.

## 4. Go flow

1. Codex or Claude Code creates the exchange folder and manifest.
2. The extension displays the exact request files and expected main-output filename.
3. Sina clicks **Go**.
4. The companion verifies the listed files exist and returns their absolute paths.
5. The extension records the call as active, starts download monitoring, opens or focuses ChatGPT, and attaches Chrome's debugger interface to that tab.
6. The extension enables file-chooser interception and waits. It does not click ChatGPT's attachment control.
7. Sina clicks ChatGPT's **Attach files** control.
8. Chrome emits the intercepted file-chooser event. The extension assigns every approved request path to that exact file input through `DOM.setFileInputFiles`.
9. The extension confirms the attached filenames and detaches the debugger immediately.
10. Sina reviews the attachments and clicks ChatGPT's native **Send** button.

The prompt is an uploaded file named `PROMPT_YYYY-MM-DD_HHMMSS.txt`. ChatGPT receives it alongside the request JSON, response schema, and approved context files. The first version does not manipulate the ChatGPT composer text.

If the chooser event is not received, the extension fails visibly and leaves manual attachment available. It never guesses at another page control.

## 5. Download monitoring and movement

Monitoring begins at Go and ends at Done.

The extension records downloads created after monitoring begins and reacts only after Chrome reports them complete. It sends the completed local path and download metadata to the companion.

The companion moves a file only when it can associate it with the active call:

1. The main JSON matches the expected main-output filename, allowing a browser duplicate suffix such as `(1)`, and contains the active request identity.
2. The companion parses the main JSON's artifact manifest.
3. Each additional file is moved only when its filename is listed in that manifest.
4. Where provided, size and SHA-256 must match the manifest.

Artifacts downloaded before the main JSON are remembered as pending candidates. They are moved only after the main JSON identifies them. Unmatched downloads remain untouched in Downloads.

Each safe move is implemented as copy-to-temporary, hash/size verification, atomic rename into `response/`, and deletion of the original only after verification. Existing different bytes are never overwritten.

## 6. Main JSON contract

Every call requires one downloadable main JSON response. It must contain:

- the request identity;
- status: `COMPLETE`, `PARTIAL`, or `BLOCKED`;
- the requested reasoning/work results;
- an artifact manifest containing every additional returned file;
- for each artifact: exact filename, status, media type, byte size, and SHA-256 when created;
- limitations and missing work;
- a delivery list accounting for the main JSON and all artifacts.

The main JSON remains advisory. Codex or Claude Code performs intellectual validation after deterministic file validation succeeds.

## 7. Done flow

When Sina clicks **Done**:

1. The extension immediately stops accepting new download events for the call.
2. The companion finishes any already-completed candidate currently being moved.
3. It validates the main JSON, artifact list, returned filenames, sizes, and hashes.
4. It writes `validation/VALIDATION_REPORT.json`.
5. The extension reports either **Complete** or an exact list of missing/invalid files.
6. `ACTIVE_CALL.json` is cleared only after the result is recorded.

Done does not pretend an incomplete response succeeded. The collected files remain preserved for inspection or a later correction call.

## 8. Minimal state and recovery

`ACTIVE_CALL.json` contains only the active exchange path, call/request identity, start time, bound ChatGPT tab, monitoring status, observed download IDs, and collected filenames.

On extension or Chrome restart, the extension asks the companion whether an active call exists and offers **Resume** or **Stop**. It never resends a ChatGPT message or silently resumes file-chooser control.

## 9. Testing and acceptance

The first version is accepted only after:

- unit tests cover manifest parsing, path restrictions, browser suffix handling, safe moves, hashing, and main/artifact validation;
- extension tests use a local mock page to prove that attachment occurs only after a real user file-chooser click;
- download tests prove that unmatched downloads remain untouched and monitoring stops at Done;
- restart tests recover the one active call;
- one non-sensitive live ChatGPT test completes Go -> Attach -> Send -> manual downloads -> Done;
- the manual folder workflow still works with the extension disabled.

## 10. Explicitly deferred

- automatic Send;
- response DOM reading or scraping;
- multiple simultaneous active calls;
- SQLite, event journals, project graphs, and completion engines;
- automatic retries;
- broad repository integration;
- cross-platform support beyond the initial Windows/Chrome installation.

## 11. Technical basis

- Chrome's debugger API can send Chrome DevTools Protocol commands to an attached tab: <https://developer.chrome.com/docs/extensions/reference/api/debugger>
- `Page.setInterceptFileChooserDialog` suppresses the native chooser and emits `Page.fileChooserOpened` after the user requests it: <https://chromedevtools.github.io/devtools-protocol/tot/Page/#method-setInterceptFileChooserDialog>
- `DOM.setFileInputFiles` assigns local file paths to that specific file input: <https://chromedevtools.github.io/devtools-protocol/tot/DOM/#method-setFileInputFiles>
- Chrome's downloads API reports creation and completion and supplies the local filename: <https://developer.chrome.com/docs/extensions/reference/api/downloads>
- Native messaging connects the extension to the local Python companion: <https://developer.chrome.com/docs/extensions/develop/concepts/native-messaging>
