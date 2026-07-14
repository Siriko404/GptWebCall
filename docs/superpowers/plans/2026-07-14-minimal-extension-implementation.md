# Minimal ChatGPT Web Call Extension Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Delegation is prohibited for this project. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Windows/Chrome extension and small local companion that attach one prepared call after Sina clicks ChatGPT's attachment control, collect matching manually downloaded outputs until Done, and validate the main JSON and its artifacts.

**Architecture:** A Manifest V3 side panel owns user interaction and temporary Chrome coordination. A Python standard-library companion owns the filesystem and validation, with a tiny Go launcher providing a reliable Windows native-messaging executable. The filesystem is authoritative, and only one call can be active.

**Tech Stack:** Chrome 150 Manifest V3, JavaScript ES modules, Chrome Debugger/Downloads/Native Messaging APIs, Python 3.13 standard library, Go 1.24 standard library, PowerShell, Python `unittest`, Node 24 built-in test runner.

## Global Constraints

- Canonical root: `C:\GptWebCall`.
- No delegated agents or ChatGPT Web calls during implementation.
- Preserve the existing Go prototype and its history; do not silently delete it.
- One active call globally.
- Prompt name: `PROMPT_YYYY-MM-DD_HHMMSS.txt`, sharing the exchange-folder timestamp.
- Go waits for Sina's real ChatGPT attachment click, assigns only manifest-approved files, and never presses Send.
- Download monitoring starts at Go and stops at Done.
- Unmatched downloads remain untouched.
- The main JSON must bind to the request and enumerate every additional artifact.
- No response DOM reading, cookie access, private endpoint, automatic Send, automatic retry, database, or event-sourcing layer.
- All production behavior follows red-green-refactor.
- Commit each completed task separately.

---

### Task 0: Preserve the superseded Go prototype

**Files:**
- Existing: `internal/model/model.go`
- Existing: `internal/calls/prepare.go`
- Existing: `internal/calls/prepare_test.go`
- Existing: `internal/integrity/hash.go`
- Existing: `internal/integrity/hash_test.go`
- Existing: `tests/fixtures/requests/*`

**Interfaces:**
- Produces: a clean checkpoint commit containing the already-written package-preparation prototype.

- [ ] **Step 1: Verify the existing prototype without editing it**

Run: `gofmt -l .; go test ./... -race -count=1`

Expected: no unformatted filenames and every Go package passes.

- [ ] **Step 2: Inspect the exact preservation set**

Run: `git status --short; git diff -- internal/model/model.go`

Expected: only the known model change and untracked `internal/calls`, `internal/integrity`, and request fixtures.

- [ ] **Step 3: Commit only the preserved prototype**

```powershell
git add internal/model/model.go internal/calls internal/integrity tests/fixtures/requests
git commit -m "archive: preserve superseded Go package prototype"
```

Expected: the commit succeeds and no unrelated file is staged.

### Task 1: Minimal exchange and active-call filesystem core

**Files:**
- Create: `companion/__init__.py`
- Create: `companion/core.py`
- Create: `companion/tests/__init__.py`
- Create: `companion/tests/test_core.py`

**Interfaces:**
- Produces: `prepare_call(root: Path, spec: dict, now: datetime) -> dict`
- Produces: `list_ready_calls(root: Path) -> list[dict]`
- Produces: `start_call(root: Path, exchange_id: str, tab_id: int, download_baseline: list[int]) -> dict`
- Produces: `load_active_call(root: Path) -> dict | None`
- Produces: `stop_call(root: Path) -> dict`

- [ ] **Step 1: Write failing exchange-contract tests**

Create tests that build three request files and assert:

```python
def test_prepare_call_uses_one_timestamp_for_folder_and_prompt(self):
    manifest = prepare_call(self.root, self.spec(), self.now)
    self.assertEqual(manifest["exchange_id"], "2026-07-14_151500_fixture_call")
    names = [item["filename"] for item in manifest["request_files"]]
    self.assertIn("PROMPT_2026-07-14_151500.txt", names)

def test_only_one_call_can_be_active(self):
    first = prepare_call(self.root, self.spec("first"), self.now)
    second = prepare_call(self.root, self.spec("second"), self.now.replace(second=1))
    start_call(self.root, first["exchange_id"], 11, [])
    with self.assertRaisesRegex(RuntimeError, "already active"):
        start_call(self.root, second["exchange_id"], 12, [])
```

Also cover unsafe subjects, absent request files, duplicate filenames, non-JSON request/schema files, and prompt timestamp mismatch.

- [ ] **Step 2: Verify RED**

Run: `python -m unittest companion.tests.test_core -v`

Expected: import failure because `companion.core` does not exist.

- [ ] **Step 3: Implement the minimum filesystem core**

Use these exact manifest fields:

```python
manifest = {
    "schema_version": 1,
    "exchange_id": exchange_id,
    "request_id": spec["request_id"],
    "subject": subject,
    "created_at": now.astimezone(timezone.utc).isoformat(),
    "state": "PREPARED",
    "expected_main_json": spec["expected_main_json"],
    "request_files": request_files,
    "response_dir": "response",
}
```

`request_files` must contain `filename`, `size`, and `sha256`. Implement `_safe_name`, `_sha256`, `_write_json_atomic`, and path-containment checks in `core.py`. `ACTIVE_CALL.json` must contain only `exchange_id`, `exchange_path`, `request_id`, `tab_id`, `started_at`, `monitoring`, `download_baseline`, `observed_download_ids`, and `collected_files`.

`prepare_call` receives `prompt_text` and `input_files` in the spec. It creates the timestamped prompt itself, copies only the explicitly listed input files into `request/`, rejects duplicate destination basenames, hashes the completed copies, and atomically publishes the exchange only after the manifest is valid.

- [ ] **Step 4: Verify GREEN**

Run: `python -m unittest companion.tests.test_core -v`

Expected: all core tests pass.

- [ ] **Step 5: Commit**

```powershell
git add companion/core.py companion/__init__.py companion/tests
git commit -m "feat(companion): add minimal exchange state"
```

### Task 2: Safe download association, movement, and response validation

**Files:**
- Create: `companion/downloads.py`
- Create: `companion/tests/test_downloads.py`
- Create: `companion/tests/fixtures/main_complete.json`

**Interfaces:**
- Consumes: `load_active_call`, `_write_json_atomic`, and manifest paths from `companion.core`
- Produces: `handle_completed_download(root: Path, download: dict) -> dict`
- Produces: `finish_call(root: Path) -> dict`
- Produces: `validate_response(exchange_dir: Path) -> dict`

- [ ] **Step 1: Write failing association tests**

Cover these exact cases:

```python
def test_unmatched_download_stays_in_downloads(self):
    source = self.download("unrelated.pdf", b"unrelated")
    result = handle_completed_download(self.root, {"id": 1, "filename": str(source)})
    self.assertEqual(result["status"], "IGNORED")
    self.assertTrue(source.exists())

def test_artifact_waits_until_main_json_names_it(self):
    artifact = self.download("report.md", b"report")
    pending = handle_completed_download(self.root, {"id": 2, "filename": str(artifact)})
    self.assertEqual(pending["status"], "PENDING")
    self.assertTrue(artifact.exists())

def test_browser_suffix_binds_to_expected_main_json(self):
    main = self.download("result (1).json", self.main_json_bytes())
    moved = handle_completed_download(self.root, {"id": 3, "filename": str(main)})
    self.assertEqual(moved["stored_name"], "result.json")
    self.assertFalse(main.exists())
```

Also test wrong request ID, missing artifact, hash mismatch, existing different response bytes, interrupted/nonexistent paths, and artifacts downloaded before and after the main JSON.

- [ ] **Step 2: Verify RED**

Run: `python -m unittest companion.tests.test_downloads -v`

Expected: import failure because `companion.downloads` does not exist.

- [ ] **Step 3: Implement deterministic association**

The main response contract must use:

```json
{
  "request_id": "request_fixture",
  "status": "COMPLETE",
  "artifacts_manifest": [
    {
      "filename": "report.md",
      "status": "CREATED",
      "media_type": "text/markdown",
      "size": 6,
      "sha256": "845e91831319e89c4d656bdb80c278ac09a7230d61e5dfd2e1b1fbb436ac8917"
    }
  ],
  "delivery": ["result.json", "report.md"]
}
```

Implement `_normalized_browser_name` so only `name (digits).ext` may map to an expected name. Implement `_safe_move` as copy to `response/.incoming-*`, flush/close, verify size/hash, `os.replace`, then unlink the source. Never overwrite different existing bytes. Pending candidates remain recorded in `ACTIVE_CALL.json` but are not moved until identified by the main JSON.

- [ ] **Step 4: Implement Done validation**

`finish_call` must set `monitoring` false first, validate the main JSON and every `CREATED` artifact, write `validation/VALIDATION_REPORT.json`, update `EXCHANGE_MANIFEST.json` to `COMPLETE` or `INCOMPLETE`, and remove `ACTIVE_CALL.json` only after those writes succeed.

- [ ] **Step 5: Verify GREEN**

Run: `python -m unittest companion.tests.test_downloads -v`

Expected: all association, safe-move, and validation tests pass.

- [ ] **Step 6: Commit**

```powershell
git add companion/downloads.py companion/tests/test_downloads.py companion/tests/fixtures
git commit -m "feat(companion): collect and validate downloads"
```

### Task 3: Native messaging protocol and Windows launcher

**Files:**
- Create: `companion/native_host.py`
- Create: `companion/tests/test_native_host.py`
- Create: `companion/cli.py`
- Create: `companion/tests/test_cli.py`
- Create: `cmd/nativehost/main.go`
- Create: `scripts/build.ps1`
- Create: `gptwebcall.cmd`

**Interfaces:**
- Consumes: core/download functions from Tasks 1-2
- Produces: `read_message(stream) -> dict | None`
- Produces: `write_message(stream, value: dict) -> None`
- Produces: `dispatch(root: Path, message: dict) -> dict`
- Produces: `python -m companion.cli prepare|list|show`
- Produces: `bin/gptwebcall-host.exe`

- [ ] **Step 1: Write failing framing and command tests**

Test a four-byte little-endian length prefix, UTF-8 JSON body, truncated frames, messages over 1 MiB, unknown commands, and the exact allowlist:

```python
ALLOWED_COMMANDS = {
    "health",
    "calls.list_ready",
    "call.active",
    "call.go",
    "download.completed",
    "call.done",
    "call.stop",
}
```

Each request must contain `protocol_version: 1`, `command`, and `payload`. Responses must contain `ok`, `command`, and either `result` or `error`.

- [ ] **Step 2: Verify RED**

Run: `python -m unittest companion.tests.test_native_host -v`

Expected: import failure because `companion.native_host` does not exist.

- [ ] **Step 3: Implement the native host**

Use `sys.stdin.buffer` and `sys.stdout.buffer`; on Windows call `msvcrt.setmode(sys.stdin.fileno(), os.O_BINARY)` and `msvcrt.setmode(sys.stdout.fileno(), os.O_BINARY)`. Validate all payload fields and ensure every filesystem path is derived from the canonical root or a Chrome-supplied completed-download filename. No command may accept an arbitrary destination or shell command.

- [ ] **Step 4: Implement the Codex/Claude CLI**

`companion/cli.py` must expose `prepare --spec <json>`, `list`, and `show --exchange <id>`. Every successful command prints one JSON object to stdout. `gptwebcall.cmd` must invoke `python -m companion.cli --root "%~dp0" %*`. CLI tests must prepare a fixture from a spec file, list it as `PREPARED`, and reject an exchange path containing traversal.

- [ ] **Step 5: Implement the Go launcher**

`cmd/nativehost/main.go` must locate the repository root relative to its own executable, find `python.exe` with `exec.LookPath`, and run:

```go
command := exec.Command(python, "-m", "companion.native_host", "--root", root)
command.Dir = root
command.Stdin = os.Stdin
command.Stdout = os.Stdout
command.Stderr = os.Stderr
```

It must forward Chrome's origin/parent-window arguments after the fixed arguments and exit with the Python process's exit code.

- [ ] **Step 6: Build and verify GREEN**

Run: `python -m unittest companion.tests.test_native_host companion.tests.test_cli -v; .\scripts\build.ps1; .\gptwebcall.cmd list; Test-Path .\bin\gptwebcall-host.exe`

Expected: tests pass, Go build succeeds, and the executable exists.

- [ ] **Step 7: Commit**

```powershell
git add companion/native_host.py companion/cli.py companion/tests/test_native_host.py companion/tests/test_cli.py cmd/nativehost scripts/build.ps1 gptwebcall.cmd
git commit -m "feat(native): add restricted local bridge"
```

### Task 4: Extension shell and user-triggered attachment handoff

**Files:**
- Create: `extension/manifest.json`
- Create: `extension/service_worker.js`
- Create: `extension/sidepanel.html`
- Create: `extension/sidepanel.css`
- Create: `extension/sidepanel.js`
- Create: `extension/lib/attachment.js`
- Create: `extension/tests/attachment.test.js`
- Create: `extension/package.json`

**Interfaces:**
- Consumes: native commands `calls.list_ready`, `call.go`, and `call.active`
- Produces: `armAttachment(tabId, paths)` and `handleFileChooserOpened(source, params)`
- Produces: side-panel messages `GET_STATUS`, `GO`, and `STOP`

- [ ] **Step 1: Write failing pure-logic tests**

Using Node's built-in test runner, verify that chooser events are accepted only for the active tab, require `backendNodeId`, reject empty paths, and return this exact CDP command:

```javascript
{
  method: "DOM.setFileInputFiles",
  params: { files: approvedPaths, backendNodeId }
}
```

- [ ] **Step 2: Verify RED**

Run: `npm --prefix extension test`

Expected: module-not-found failure for `extension/lib/attachment.js`.

- [ ] **Step 3: Implement the MV3 shell**

`manifest.json` must declare only `sidePanel`, `nativeMessaging`, `debugger`, `downloads`, and `storage`; use `service_worker.js` as an ES module. Configure the side panel as `sidepanel.html`. Do not add content scripts or host permissions.

- [ ] **Step 4: Implement Go and attachment interception**

On Go:

1. resolve the selected exchange through `calls.list_ready`;
2. open/focus `https://chatgpt.com/` and retain its tab ID;
3. query current download IDs as the baseline;
4. call native `call.go` with the exchange ID, tab ID, and baseline, and receive exact approved paths;
5. attach `chrome.debugger` to that tab with protocol version `1.3`;
6. send `Page.enable` with `enableFileChooserOpenedEvent: true`;
7. send `Page.setInterceptFileChooserDialog` with `enabled: true`;
8. display `Waiting for you to click Attach files`.

On `Page.fileChooserOpened`, verify the bound tab, call `DOM.setFileInputFiles`, disable interception, detach the debugger, and display the attached basenames. Never call a Send control.

- [ ] **Step 5: Verify GREEN**

Run: `npm --prefix extension test`

Expected: all attachment logic tests pass.

- [ ] **Step 6: Commit**

```powershell
git add extension
git commit -m "feat(extension): attach prepared call on user chooser"
```

### Task 5: Extension download watcher and Done control

**Files:**
- Create: `extension/lib/downloads.js`
- Create: `extension/tests/downloads.test.js`
- Modify: `extension/service_worker.js`
- Modify: `extension/sidepanel.js`
- Modify: `extension/sidepanel.html`

**Interfaces:**
- Consumes: native commands `download.completed`, `call.done`, and `call.stop`
- Produces: `shouldObserveDownload(active, downloadItem) -> boolean`
- Produces: service-worker messages `DONE` and status broadcasts

- [ ] **Step 1: Write failing watcher tests**

Test that only downloads created after `monitoring_started_at` and not in the baseline ID set are observed; completion is reported exactly once; interrupted downloads are not submitted; and no event is accepted after Done sets monitoring false.

- [ ] **Step 2: Verify RED**

Run: `npm --prefix extension test`

Expected: module-not-found failure for `extension/lib/downloads.js`.

- [ ] **Step 3: Implement monitoring**

Immediately before native `call.go`, call `chrome.downloads.search({})`, pass every existing download ID as the baseline, and persist the returned active-call record. Listen to `chrome.downloads.onCreated` and `onChanged`. When a tracked ID becomes `complete`, call `chrome.downloads.search({id})`, then send its `id`, `filename`, `url`, `finalUrl`, `mime`, `startTime`, and `endTime` to `download.completed`.

The extension observes candidates; the companion alone decides whether to move them.

- [ ] **Step 4: Implement Done**

The side-panel Done button must first mark local monitoring false, then call native `call.done`, render `COMPLETE` or the exact missing/invalid list, and clear transient extension state. Repeated Done returns the recorded result rather than moving files twice.

- [ ] **Step 5: Verify GREEN**

Run: `npm --prefix extension test; python -m unittest discover -s companion/tests -v`

Expected: all extension and companion tests pass.

- [ ] **Step 6: Commit**

```powershell
git add extension
git commit -m "feat(extension): monitor downloads until Done"
```

### Task 6: Installer, canonical protocol, and manual fallback

**Files:**
- Create: `scripts/install.ps1`
- Create: `scripts/uninstall.ps1`
- Create: `native-host/com.sina.gptwebcall.template.json`
- Create: `WEB_CALL_PROTOCOL.md`
- Create: `README.md`
- Create: `docs/MANUAL_FALLBACK.md`
- Create: `companion/tests/test_protocol.py`

**Interfaces:**
- Produces: `install.ps1 -ExtensionId <32 lowercase letters>`
- Produces: HKCU registration at `Software\Google\Chrome\NativeMessagingHosts\com.sina.gptwebcall`
- Produces: one canonical instruction entry point for Codex and Claude Code

- [ ] **Step 1: Write failing protocol/installer tests**

Assert that the protocol contains the canonical root, reasoning-heavy triage, `PROMPT_YYYY-MM-DD_HHMMSS.txt`, one-call limit, Go/Done boundary, response JSON contract, manual fallback, and no automatic Send/scraping claim. Assert the host template has `name`, `description`, `path`, `type: stdio`, and exactly one `allowed_origins` entry after installation rendering.

- [ ] **Step 2: Verify RED**

Run: `python -m unittest companion.tests.test_protocol -v`

Expected: failure because the protocol and scripts do not exist.

- [ ] **Step 3: Implement installation scripts**

`install.ps1` must validate the extension ID against `^[a-p]{32}$`, build the Go launcher, render an absolute host manifest with `chrome-extension://<id>/`, register it under HKCU, and print the unpacked extension directory. `uninstall.ps1` removes only that registry key and generated host manifest; it must not delete calls or responses.

- [ ] **Step 4: Write the canonical protocol and fallback**

Document the exact lifecycle: triage -> create request files -> prepare exchange -> user Go -> user Attach -> extension assigns files -> user Send -> user downloads -> Done -> deterministic validation -> Codex semantic validation. Include CLI/native-host recovery and manual copying instructions.

- [ ] **Step 5: Verify GREEN**

Run: `python -m unittest companion.tests.test_protocol -v; powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\install.ps1 -ExtensionId aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa -WhatIf`

Expected: protocol tests pass and WhatIf reports the exact files/registry key without changing the registry.

- [ ] **Step 6: Commit**

```powershell
git add scripts native-host WEB_CALL_PROTOCOL.md README.md docs/MANUAL_FALLBACK.md companion/tests/test_protocol.py
git commit -m "docs: install and operate global web calls"
```

### Task 7: Local mock integration and real UAT

**Files:**
- Create: `tests/mock_chatgpt/index.html`
- Create: `tests/e2e/fixture_call.ps1`
- Create: `tests/e2e/UAT_CHECKLIST.md`
- Create: `tests/e2e/run_all.ps1`

**Interfaces:**
- Consumes: completed extension, companion, installer, and protocol
- Produces: repeatable automated verification plus one recorded live acceptance checklist

- [ ] **Step 1: Create the mock attachment/download surface**

The local page must expose an accessible `Attach files` button backed by `<input type="file" multiple>`, list selected filenames, and provide manual download links for a fixture main JSON, valid artifact, unrelated file, and hash-mismatch artifact. It must not imitate authentication or ChatGPT private endpoints.

- [ ] **Step 2: Create the fixture-call script**

The script must create a fresh temporary call containing a timestamped prompt, request JSON, response schema, and one context file, then assert the manifest contains exactly those four files and no file outside the fixture root.

- [ ] **Step 3: Create the complete verification script**

`run_all.ps1` must run:

```powershell
gofmt -l .
go test ./... -race -count=1
python -m unittest discover -s companion/tests -v
npm --prefix extension test
.\scripts\build.ps1
.\tests\e2e\fixture_call.ps1
git diff --check
```

It exits nonzero on any failure.

- [ ] **Step 4: Run automated verification**

Run: `powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\e2e\run_all.ps1`

Expected: every suite and fixture checkpoint passes.

- [ ] **Step 5: Perform live non-sensitive UAT**

Record pass/fail for: install unpacked extension; Go; user clicks Attach; exact files appear; user clicks Send; user manually downloads an unrelated file plus the response files; unrelated file stays in Downloads; matched files move; Done stops monitoring; main/artifact validation passes; a later download remains untouched; Chrome restart offers Resume/Stop.

- [ ] **Step 6: Commit verified E2E evidence**

```powershell
git add tests/mock_chatgpt tests/e2e
git commit -m "test: prove minimal web call vertical slice"
```

## Plan self-review

- Every approved design section maps to at least one task.
- Attachment automation occurs only after Sina's actual file-chooser click.
- The extension does not press Send or read ChatGPT's response DOM.
- Download monitoring has an explicit start and stop boundary.
- Unmatched downloads are tested to remain untouched.
- Main JSON identity and artifact accounting are tested before completion.
- The design remains filesystem-only with one active call.
- Installation, restart recovery, manual fallback, and live UAT are included.
- Existing Go work is preserved before the new implementation begins.
