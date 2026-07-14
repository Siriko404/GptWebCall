# Global Core and Protocol Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Delegation is prohibited for this project. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the first usable standalone vertical slice: initialize global state, register an external project, prepare an immutable timestamped Web-call package, collect returned files, validate them, and operate/resume the workflow from either Codex or Claude Code through one canonical Markdown protocol.

**Architecture:** A single Go executable owns a filesystem-first deterministic database under the canonical root. Immutable exchange bytes and append-only per-call events are authoritative; atomic JSON files are materialized views; the global index is rebuildable. The browser extension is intentionally deferred to the next plan, while every operation in this plan remains usable manually and exposes the exact application interfaces the native host will later call.

**Tech Stack:** Go 1.24.5, Go standard library, `github.com/santhosh-tekuri/jsonschema/v6`, PowerShell 5.1/7 for Windows scripts, JSON Schema Draft 2020-12, Git.

## Global Constraints

- Canonical root: `C:\GptWebCall`.
- All code, state, calls, evidence, logs, tests, and documentation live under the canonical root.
- No delegated agents or ChatGPT Web calls for implementation.
- New prompt filename: `PROMPT_YYYY-MM-DD_HHMMSS.txt`, matching its exchange timestamp exactly.
- One live Windows host and one writer process are supported; multi-host concurrent writes fail closed.
- No SQLite authority in Phase 1; the global index is derived and rebuildable.
- All CLI success output is JSON on stdout; diagnostics use stderr; non-success uses a nonzero exit code.
- No automatic ChatGPT Send, response scraping, cookie/session access, private endpoints, or automatic Output extraction.
- Every production behavior follows red-green-refactor; no production function is written before its failing test.
- Generated `bin/`, `extension/dist/`, and operational `data/` are not committed.

---

### Task 1: Repository foundation and canonical path contract

**Files:**
- Create: `.gitignore`
- Create: `go.mod`
- Create: `internal/paths/layout.go`
- Test: `internal/paths/layout_test.go`

**Interfaces:**
- Produces: `paths.New(root string) (Layout, error)`
- Produces: `Layout.ProjectDir(projectID string) string`
- Produces: `Layout.CallDir(projectID, exchangeName string) string`
- Produces: `paths.ExchangeName(time.Time, subject string) (string, error)`
- Produces: `paths.PromptFilename(time.Time) string`
- Produces: `paths.SafeSlug(string) (string, error)`

- [ ] **Step 1: Create the module metadata and ignore generated state**

```text
module github.com/Siriko404/GptWebCall

go 1.24.0
```

`.gitignore` must ignore `/bin/`, `/data/`, `/extension/dist/`, coverage output, temporary files, and local editor state while keeping schemas, tests, docs, and fixtures tracked.

- [ ] **Step 2: Write failing path-contract tests**

```go
func TestExchangeAndPromptShareExactTimestamp(t *testing.T) {
    now := time.Date(2026, 7, 14, 13, 57, 14, 0, time.FixedZone("EDT", -4*3600))
    exchange, err := ExchangeName(now, "Global standalone architecture")
    if err != nil { t.Fatal(err) }
    if exchange != "2026-07-14_135714_global_standalone_architecture" { t.Fatalf("%q", exchange) }
    if PromptFilename(now) != "PROMPT_2026-07-14_135714.txt" { t.Fatal(PromptFilename(now)) }
}

func TestSafeSlugRejectsTraversalAndReservedNames(t *testing.T) {
    for _, value := range []string{"../escape", "CON", "a/b", ""} {
        if _, err := SafeSlug(value); err == nil { t.Fatalf("accepted %q", value) }
    }
}
```

- [ ] **Step 3: Run the path tests and verify RED**

Run: `go test ./internal/paths -run 'TestExchange|TestSafeSlug' -v`
Expected: compile failure because `ExchangeName`, `PromptFilename`, and `SafeSlug` do not exist.

- [ ] **Step 4: Implement the minimum path contract**

Implement timestamp formatting with `2006-01-02_150405`, lowercase ASCII snake-case slugs, Windows reserved-name rejection, traversal/separator rejection, and layout paths rooted under `data/projects/<project_id>/calls`.

- [ ] **Step 5: Verify GREEN and commit**

Run: `go test ./internal/paths -v`
Expected: PASS.

Commit:

```powershell
git add .gitignore go.mod internal/paths
git commit -m "feat(core): define canonical global layout"
```

### Task 2: Atomic store, append-only events, and single-writer lock

**Files:**
- Create: `internal/store/atomic.go`
- Create: `internal/store/events.go`
- Create: `internal/store/lock.go`
- Test: `internal/store/atomic_test.go`
- Test: `internal/store/events_test.go`
- Test: `internal/store/lock_test.go`

**Interfaces:**
- Produces: `store.WriteJSONAtomic(path string, value any) error`
- Produces: `store.ReadJSON(path string, target any) error`
- Produces: `store.AppendEvent(path string, event any) error`
- Produces: `store.AcquireWriterLock(ctx context.Context, lockPath string, metadata LockMetadata) (*WriterLock, error)`
- Produces: `(*WriterLock).Release() error`

- [ ] **Step 1: Write failing atomicity and event tests**

```go
func TestWriteJSONAtomicLeavesNoTempFile(t *testing.T) {
    path := filepath.Join(t.TempDir(), "state.json")
    if err := WriteJSONAtomic(path, map[string]any{"version": 1}); err != nil { t.Fatal(err) }
    var got map[string]any
    if err := ReadJSON(path, &got); err != nil { t.Fatal(err) }
    if got["version"] != float64(1) { t.Fatalf("%v", got) }
    matches, _ := filepath.Glob(path + ".tmp-*")
    if len(matches) != 0 { t.Fatalf("temporary files remain: %v", matches) }
}

func TestAppendEventWritesOneJSONObjectPerLine(t *testing.T) {
    path := filepath.Join(t.TempDir(), "EVENTS.jsonl")
    if err := AppendEvent(path, map[string]any{"event_id": "e1"}); err != nil { t.Fatal(err) }
    data, _ := os.ReadFile(path)
    if string(data) != "{\"event_id\":\"e1\"}\n" { t.Fatalf("%q", data) }
}
```

- [ ] **Step 2: Run tests and verify RED**

Run: `go test ./internal/store -v`
Expected: compile failure because the store functions do not exist.

- [ ] **Step 3: Implement durable writes and exclusive lock creation**

`WriteJSONAtomic` must create a same-directory temporary file, encode deterministic indented JSON with a final newline, call `Sync`, close, and rename. `AppendEvent` must open with append/create, write one compact JSON line, call `Sync`, and close. The lock must use `O_CREATE|O_EXCL`, record installation/host/PID/nonce/command/start time, and never break an existing lock automatically.

- [ ] **Step 4: Add duplicate-writer and stale-metadata tests**

```go
func TestSecondWriterCannotAcquireLiveLock(t *testing.T) {
    path := filepath.Join(t.TempDir(), "writer.lock")
    first, err := AcquireWriterLock(context.Background(), path, LockMetadata{PID: os.Getpid(), Hostname: "host-a"})
    if err != nil { t.Fatal(err) }
    defer first.Release()
    if _, err := AcquireWriterLock(context.Background(), path, LockMetadata{PID: os.Getpid(), Hostname: "host-a"}); !errors.Is(err, ErrWriterLocked) {
        t.Fatalf("expected ErrWriterLocked, got %v", err)
    }
}
```

- [ ] **Step 5: Verify GREEN and commit**

Run: `go test ./internal/store -race -v`
Expected: PASS with no race reports.

Commit:

```powershell
git add internal/store
git commit -m "feat(core): add atomic state and writer lock"
```

### Task 3: Installation and global project registry

**Files:**
- Create: `internal/model/model.go`
- Create: `internal/projects/registry.go`
- Test: `internal/projects/registry_test.go`

**Interfaces:**
- Produces: `model.Installation`, `model.Project`, `model.ProjectRegistry`, `model.Event`
- Produces: `projects.Initialize(layout paths.Layout, now time.Time, hostname string) (model.Installation, error)`
- Produces: `projects.Register(layout paths.Layout, spec RegisterSpec, now time.Time) (model.Project, error)`
- Produces: `projects.List(layout paths.Layout) ([]model.Project, error)`

- [ ] **Step 1: Write failing registration tests**

```go
func TestRegisterProjectKeepsSourceExternalAndStateGlobal(t *testing.T) {
    layout, _ := paths.New(t.TempDir())
    source := t.TempDir()
    project, err := Register(layout, RegisterSpec{Name: "Thesis", ExternalRoot: source}, fixedTime)
    if err != nil { t.Fatal(err) }
    if !filepath.IsAbs(project.ExternalRoot) || project.ExternalRoot != source { t.Fatalf("%+v", project) }
    if _, err := os.Stat(layout.ProjectDir(project.ProjectID)); err != nil { t.Fatal(err) }
    if strings.HasPrefix(layout.ProjectDir(project.ProjectID), source) { t.Fatal("state leaked into external project") }
}
```

- [ ] **Step 2: Verify RED**

Run: `go test ./internal/projects -v`
Expected: compile failure because registry types/functions do not exist.

- [ ] **Step 3: Implement initialization and registration**

Generate stable opaque IDs with `crypto/rand`; resolve the external root to an absolute path; reject missing roots, symlinks/reparse points, duplicate canonical roots, and roots inside `GptWebCall/data`. Write `INSTALLATION.json`, `PROJECT_REGISTRY.json`, project `PROJECT.json`, and matching events atomically under the writer lock.

- [ ] **Step 4: Add duplicate and cross-host tests**

Test duplicate external roots, a registry with another installation ID, malformed JSON, and a second hostname heartbeat. Each mutation must fail without changing existing bytes.

- [ ] **Step 5: Verify GREEN and commit**

Run: `go test ./internal/projects ./internal/store ./internal/paths -race -v`
Expected: PASS.

Commit:

```powershell
git add internal/model internal/projects
git commit -m "feat(core): add global project registry"
```

### Task 4: Immutable request package preparation

**Files:**
- Create: `internal/calls/prepare.go`
- Create: `internal/integrity/hash.go`
- Test: `internal/calls/prepare_test.go`
- Add fixture: `tests/fixtures/requests/minimal_request.json`
- Add fixture: `tests/fixtures/requests/minimal_response_schema.json`

**Interfaces:**
- Consumes: paths, store, projects, model
- Produces: `calls.Prepare(layout paths.Layout, spec PrepareSpec, now time.Time) (model.Call, error)`
- Produces: `integrity.FileSHA256(path string) (string, int64, error)`
- Produces: `integrity.PackageDigest(manifest model.PackageManifest) (string, error)`

- [ ] **Step 1: Write the failing package test**

```go
func TestPrepareCreatesFrozenSelfContainedExchange(t *testing.T) {
    // Register an external project and create one source file there.
    // Prepare one call with the request JSON, response schema, source, and prompt text.
    // Assert the exchange name and prompt share the exact timestamp.
    // Assert every packaged file has size and SHA-256 in PACKAGE_MANIFEST.json.
    // Assert CALL_STATE.json is READY and request_digest is non-empty.
    // Assert no infrastructure file was written into the external project.
}
```

- [ ] **Step 2: Verify RED**

Run: `go test ./internal/calls -run TestPrepare -v`
Expected: compile failure because `Prepare` and package types do not exist.

- [ ] **Step 3: Implement minimal preparation**

Validate each source is a regular file under an approved read root; reject links, traversal, duplicate packaged names, unsafe Windows names, and the prompt name supplied by the caller. Create the exchange in `data/staging`, copy and hash each file, generate the prompt name internally, write `PACKAGE_MANIFEST.json`, compute a canonical digest over its hash-covered fields, re-hash all copies, write manifest/state/events, then atomically rename the complete exchange into the project calls directory.

- [ ] **Step 4: Add negative preparation tests**

Cover changed source during copy, duplicate basename, source outside approved root, prompt timestamp mismatch attempt, destination already present, and injected write failure. No failed case may leave a `READY` call.

- [ ] **Step 5: Verify GREEN and commit**

Run: `go test ./internal/calls ./internal/integrity -race -v`
Expected: PASS.

Commit:

```powershell
git add internal/calls internal/integrity tests/fixtures/requests
git commit -m "feat(core): prepare immutable global exchanges"
```

### Task 5: Response collection, quarantine, and deterministic validation

**Files:**
- Create: `internal/collect/collect.go`
- Create: `internal/validate/response.go`
- Test: `internal/collect/collect_test.go`
- Test: `internal/validate/response_test.go`
- Add fixtures: `tests/fixtures/responses/valid/`
- Add fixtures: `tests/fixtures/responses/missing-artifact/`
- Add fixtures: `tests/fixtures/responses/wrong-request/`

**Interfaces:**
- Produces: `collect.Files(layout paths.Layout, callID string, selected []string, now time.Time) (model.CollectionReport, error)`
- Produces: `validate.Response(layout paths.Layout, callID string, now time.Time) (model.ValidationReport, error)`

- [ ] **Step 1: Write failing collection and validation tests**

```go
func TestCollectValidResponseBindsFilesAndAdvancesToCollected(t *testing.T) {
    // Prepare a call, supply the valid main JSON and artifact fixture,
    // collect explicit paths, and assert atomic copies plus independent hashes.
}

func TestWrongRequestIDIsQuarantinedAndNeverAccepted(t *testing.T) {
    // Collect a parseable response with a different request_id.
    // Assert quarantine contains the raw bytes and state is NEEDS_CORRECTION.
}
```

- [ ] **Step 2: Verify RED**

Run: `go test ./internal/collect ./internal/validate -v`
Expected: compile failure because collection/validation functions do not exist.

- [ ] **Step 3: Implement explicit-path collection and v2 deterministic checks**

Only accept caller-selected regular files. Copy into exchange-local staging, hash, close, reopen, verify, and rename. Parse the expected main JSON with byte/depth limits; check request ID, main filename, status, expected work/question/artifact IDs, attached-file list, and every artifact SHA-256. Record original and stored names. Wrong, extra, partial, executable, archive, or ambiguous files go to a collection-specific quarantine and cannot advance to `ACCEPTED`.

- [ ] **Step 4: Add idempotency and browser-suffix tests**

The same selected bytes and idempotency key must return the prior collection result. A browser `(1)` suffix may normalize only when request identity, schema role, and hash make the binding unambiguous; both names remain recorded.

- [ ] **Step 5: Verify GREEN and commit**

Run: `go test ./internal/collect ./internal/validate -race -v`
Expected: PASS.

Commit:

```powershell
git add internal/collect internal/validate tests/fixtures/responses
git commit -m "feat(core): collect and validate returned files"
```

### Task 6: Machine-readable CLI and resume surface

**Files:**
- Create: `internal/app/app.go`
- Create: `internal/cli/cli.go`
- Create: `internal/cli/cli_test.go`
- Create: `cmd/gptwebcall/main.go`
- Create: `scripts/build.ps1`
- Create: `gptwebcall.cmd`

**Interfaces:**
- Produces: `app.Service` methods wrapping project/call/store operations
- Produces: `cli.Run(ctx context.Context, args []string, stdout, stderr io.Writer) int`

- [ ] **Step 1: Write failing CLI contract tests**

```go
func TestProjectRegisterOutputsJSONOnly(t *testing.T) {
    var out, errOut bytes.Buffer
    code := Run(context.Background(), []string{"project", "register", "--spec", specPath}, &out, &errOut)
    if code != 0 { t.Fatalf("code=%d stderr=%s", code, errOut.String()) }
    var envelope map[string]any
    if err := json.Unmarshal(out.Bytes(), &envelope); err != nil { t.Fatalf("stdout not JSON: %v", err) }
    if envelope["ok"] != true { t.Fatalf("%v", envelope) }
}
```

- [ ] **Step 2: Verify RED**

Run: `go test ./internal/cli -v`
Expected: compile failure because `Run` does not exist.

- [ ] **Step 3: Implement the Phase 1 command set**

Implement `doctor`, `init`, `project register/list/show`, `call prepare/list/show`, `call authorize-go`, `call collect --files`, `call validate`, `call accept/reject`, `integrity check`, and `index rebuild`. Mutations require state version and idempotency key where applicable. Every response envelope contains `ok`, `command`, `result` or `error`, `state_version` when relevant, and `next_actions`.

- [ ] **Step 4: Build and run CLI smoke tests**

Run:

```powershell
.\scripts\build.ps1
.\bin\gptwebcall.exe doctor
```

Expected: build succeeds; doctor emits one valid JSON object and reports the canonical root, installation state, host, writer-lock status, OneDrive/local-availability checks, and manual-fallback availability.

- [ ] **Step 5: Verify GREEN and commit**

Run: `go test ./... -race`
Expected: PASS.

Commit:

```powershell
git add internal/app internal/cli cmd scripts/build.ps1 gptwebcall.cmd
git commit -m "feat(cli): expose global call workflow"
```

### Task 7: Canonical Codex/Claude protocol and manual fallback

**Files:**
- Create: `WEB_CALL_PROTOCOL.md`
- Create: `README.md`
- Create: `AGENTS.md`
- Create: `CLAUDE.md`
- Create: `docs/MANUAL_FALLBACK.md`
- Test: `internal/integrity/protocol_test.go`

**Interfaces:**
- Consumes: the exact Phase 1 CLI command surface
- Produces: one stable protocol entry point for Codex and Claude Code

- [ ] **Step 1: Write a failing protocol-consistency test**

```go
func TestProtocolUsesCurrentPromptNameAndImplementedCommands(t *testing.T) {
    data, err := os.ReadFile(filepath.Join(repoRoot(t), "WEB_CALL_PROTOCOL.md"))
    if err != nil { t.Fatal(err) }
    text := string(data)
    if strings.Contains(text, "PASTE_THIS_PROMPT") { t.Fatal("legacy prompt name present") }
    if !strings.Contains(text, "PROMPT_YYYY-MM-DD_HHMMSS.txt") { t.Fatal("current prompt rule missing") }
    for _, command := range []string{"project register", "call prepare", "call collect", "call validate", "index rebuild"} {
        if !strings.Contains(text, command) { t.Fatalf("missing command %q", command) }
    }
}
```

- [ ] **Step 2: Verify RED**

Run: `go test ./internal/integrity -run TestProtocol -v`
Expected: FAIL because `WEB_CALL_PROTOCOL.md` does not exist.

- [ ] **Step 3: Write the canonical protocol**

The protocol must be sufficient for a fresh Codex or Claude Code session and contain: root discovery, no-delegation exception precedence, triage, project registration, context selection, preparation spec, exact Go/Done boundary, manual transfer, response collection, deterministic and semantic validation, correction lineage, integration rules, completion rules, compaction-safe resume, failure recovery, and manual fallback. Client-specific sections may describe shell invocation only; they must not fork state or lifecycle semantics.

- [ ] **Step 4: Add repository-development instructions and user README**

`AGENTS.md` and `CLAUDE.md` govern development of GptWebCall itself. They must require TDD, scoped commits, no secret fixtures, no live authenticated-browser automation, preservation of manual fallback, and protocol/schema consistency tests.

- [ ] **Step 5: Verify GREEN and commit**

Run: `go test ./... -race`
Expected: PASS.

Commit:

```powershell
git add WEB_CALL_PROTOCOL.md README.md AGENTS.md CLAUDE.md docs/MANUAL_FALLBACK.md internal/integrity/protocol_test.go
git commit -m "docs: add global Codex and Claude protocol"
```

### Task 8: Integrity rebuild, backup, and Phase 1 end-to-end proof

**Files:**
- Create: `internal/integrity/check.go`
- Create: `internal/integrity/rebuild.go`
- Create: `internal/integrity/backup.go`
- Test: `internal/integrity/check_test.go`
- Test: `internal/integrity/rebuild_test.go`
- Test: `internal/integrity/backup_test.go`
- Create: `tests/e2e/manual_vertical_slice.ps1`

**Interfaces:**
- Produces: `integrity.Check(layout paths.Layout) Report`
- Produces: `integrity.RebuildIndex(layout paths.Layout) (model.Index, error)`
- Produces: `integrity.CreateBackup(layout paths.Layout, now time.Time) (string, error)`

- [ ] **Step 1: Write failing rebuild and backup tests**

```go
func TestRebuildIndexIgnoresDerivedIndexAndUsesProjectCallEvidence(t *testing.T) {
    // Create registry/project/call fixtures, corrupt INDEX.json,
    // rebuild, and assert the call/project states match evidence.
}

func TestBackupNeverOverwritesExistingSnapshot(t *testing.T) {
    // Run backup twice at the same timestamp and require a deterministic conflict,
    // not replacement of the first backup.
}
```

- [ ] **Step 2: Verify RED**

Run: `go test ./internal/integrity -run 'TestRebuild|TestBackup' -v`
Expected: compile failure because rebuild/backup functions do not exist.

- [ ] **Step 3: Implement integrity and rebuild operations**

Scan only expected manifests/events under registered project directories; verify path containment, JSON parse, monotonic state versions, package hashes, prompt timestamp, and response hashes. Derived index rebuild must never modify exchange bytes. Backup must create a timestamped immutable snapshot with `BACKUP_MANIFEST.json` and hashes.

- [ ] **Step 4: Execute the manual vertical slice**

The PowerShell test must initialize a temporary root, register two external projects, prepare one call in each, prove no cross-project mixing, authorize one Go idempotently, collect a valid fixture response, validate it, corrupt/rebuild the index, create/verify a backup, and confirm the manual request folder remains sufficient without extension state.

- [ ] **Step 5: Run the complete Phase 1 verification**

Run:

```powershell
go test ./... -race -count=1
.\scripts\build.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\e2e\manual_vertical_slice.ps1
git status --short
```

Expected: all tests pass, the E2E script reports every checkpoint PASS, and Git status contains only intended source/document changes.

- [ ] **Step 6: Commit the verified vertical slice**

```powershell
git add internal/integrity tests/e2e
git commit -m "feat(core): prove recoverable global vertical slice"
```

## Plan self-review

- Every Phase 1 product behavior has a failing-test step before production code.
- The plan does not depend on the future extension.
- The CLI/application interfaces are suitable for reuse by the native host.
- External projects remain outside the canonical root and are never silently modified.
- Prompt naming is consistent and legacy naming is absent from new production artifacts.
- OneDrive risk is addressed through single-host writes, atomic files, immutable evidence, conflict detection, backups, and rebuildable views rather than a live authoritative WAL database.
- Phase 2 will receive a separate plan for native messaging, the file picker, and the Chrome side panel after this vertical slice passes.
