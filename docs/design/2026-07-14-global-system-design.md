# Global ChatGPT Web Call System Design

**Status:** Approved implementation baseline
**Owner:** Sina
**Implementation:** Codex, without delegated agents or ChatGPT Web calls
**Canonical root:** `C:\GptWebCall`

## 1. Goal

Build one standalone, global, human-controlled system that lets any Codex or Claude Code session prepare and manage bounded ChatGPT Web reasoning calls by being told to read:

`C:\GptWebCall\WEB_CALL_PROTOCOL.md`

The installation, source code, schemas, state, project registry, calls, returned artifacts, validation evidence, logs, quarantine, backups, extension, native host, tests, and documentation all live under the canonical root. External projects remain in their own directories.

## 2. Locked product boundaries

1. Codex or Claude Code manages the project, chooses context, prepares requests, validates results, and integrates accepted work.
2. ChatGPT Web performs bounded intellectual work and remains advisory.
3. Sina authorizes every call and operates ChatGPT's native Send and download controls.
4. Go discloses the exact frozen prompt and files, records authorization, opens ChatGPT, copies the prompt after a user action, and reveals the request folder.
5. Done opens a native multi-file picker. The user selects downloaded files; the local companion copies, binds, hashes, validates, or quarantines them.
6. No response DOM scraping, private endpoints, cookies, session export, automatic Send, automatic retry, or automatic/programmatic Output extraction.
7. The manual folder workflow remains permanently usable.
8. Every new prompt is named `PROMPT_YYYY-MM-DD_HHMMSS.txt`, with a timestamp identical to the exchange folder.
9. No infrastructure is installed inside an external project. Integration into an external project is a separate explicit operation governed by that project's own instructions and tests.

## 3. Architecture

### 3.1 Deterministic filesystem core

The authoritative database is the filesystem evidence tree under `data/`. It uses:

- immutable request snapshots;
- append-only event journals;
- atomic JSON materialized state;
- SHA-256 package and artifact binding;
- a single-writer installation lock;
- a rebuildable global index;
- explicit project/call identifiers;
- quarantine rather than destructive correction.

SQLite is not authoritative in the first release. A synchronized OneDrive directory is a poor place to make a live WAL database the only source of truth. A later SQLite index may be added only as a disposable, rebuildable cache after sync and recovery testing.

### 3.2 One executable

A Go executable at `bin\gptwebcall.exe` provides:

- the machine-readable CLI used by Codex and Claude Code;
- the Chrome native-messaging host when launched by Chrome;
- deterministic package creation and validation;
- project and call state management;
- response collection and quarantine;
- index rebuild, integrity checks, backup, restore, and diagnostics.

The executable detects native-host mode from Chrome's origin argument. File bytes never cross native messaging; the host passes only IDs, metadata, commands, and results.

### 3.3 Thin extension

The Manifest V3 extension contains no durable project authority. Its side panel displays state obtained from the native host and exposes Go, Copy Prompt, Reveal Folder, Done, Pause, Resume, and recovery actions. Baseline permissions are `sidePanel`, `nativeMessaging`, and non-sensitive `storage` only.

### 3.4 Canonical protocol

`WEB_CALL_PROTOCOL.md` is the only required entry point for a fresh Codex or Claude Code session. It specifies classification, commands, state interpretation, manual fallback, semantic validation, integration, and compaction-safe resume. Small client-specific notes may describe how each client runs a shell command, but the lifecycle and data are shared.

## 4. Repository and data layout

```text
GptWebCall/
  WEB_CALL_PROTOCOL.md
  README.md
  AGENTS.md
  CLAUDE.md
  go.mod
  go.sum
  cmd/gptwebcall/main.go
  internal/
    app/
    calls/
    cli/
    collect/
    events/
    integrity/
    model/
    nativehost/
    paths/
    projects/
    store/
    validate/
  schemas/
    v1/
  extension/
    manifest.json
    package.json
    tsconfig.json
    src/
    tests/
    dist/
  scripts/
    build.ps1
    install.ps1
    uninstall.ps1
    select-files.ps1
  data/
    INSTALLATION.json
    PROJECT_REGISTRY.json
    EVENTS.jsonl
    INDEX.json
    projects/<project_id>/
      PROJECT.json
      calls/YYYY-MM-DD_HHMMSS_short_subject/
        EXCHANGE_MANIFEST.json
        CALL_STATE.json
        EVENTS.jsonl
        request/
          PACKAGE_MANIFEST.json
          WEB_REVIEW_REQUEST.json
          WEB_RESPONSE_SCHEMA.json
          PROMPT_YYYY-MM-DD_HHMMSS.txt
          ...approved source snapshots...
        response/
        validation/
          COLLECTION_REPORT.json
          VALIDATION_REPORT.json
        quarantine/<collection_id>/
    locks/
    staging/
    backups/
    logs/
  tests/
    fixtures/
  docs/
    design/
    plans/
    history/
```

Generated `bin/`, `extension/dist/`, operational `data/`, and local logs are excluded from Git. Schemas, scripts, protocol, source, tests, and non-sensitive fixtures are versioned.

## 5. Source-of-truth hierarchy

1. Immutable bytes in each call's `request/` and `response/` directories.
2. Per-call append-only `EVENTS.jsonl` records.
3. Per-call `EXCHANGE_MANIFEST.json` and `CALL_STATE.json` materialized snapshots.
4. Project manifests and the global project registry.
5. Global `EVENTS.jsonl` and derived `INDEX.json`.

If a derived view conflicts with immutable evidence or events, the system fails closed and requires `integrity check` or `index rebuild`. It never silently chooses a winner.

## 6. OneDrive operating model

The supported baseline is one live Windows host and one active writer process at a time.

- Installation records `installation_id`, approved hostname, canonical root, and schema version.
- A writer acquires `data\locks\writer.lock` using exclusive creation and records PID, hostname, process start, command, and nonce.
- A live same-host lock blocks a second writer. A stale lock requires process-liveness verification and a recorded recovery event.
- A fresh heartbeat from another hostname blocks writes; multi-machine concurrent operation is unsupported.
- Every JSON update is written to a same-directory temporary file, flushed, closed, and atomically renamed.
- Events are appended, flushed, and closed before materialized state advances.
- Requests become immutable at `READY`; changed bytes force a new package generation.
- The installer requires the root to be available locally and instructs the user to choose “Always keep on this device.” Offline placeholders fail preflight.
- Startup scans for OneDrive conflict copies, unexpected duplicate state files, incomplete temporary files, and installation-ID conflicts. Any ambiguity blocks mutation.
- Backups are immutable timestamped snapshots under `data\backups`; restore never overwrites the only current copy without first preserving it.
- The event and exchange tree can rebuild `PROJECT_REGISTRY.json` and `INDEX.json`.

Residual risk remains if OneDrive or another process mutates files during an operation. The system reduces that risk with a single-host rule, locks, hashes, atomic replacement, immutable evidence, conflict detection, and rebuildable views.

## 7. Global project model

Registering a project stores:

- stable `project_id`;
- display name and objective;
- external canonical path;
- allowed read roots and optional integration roots;
- client/repository instruction files to consult;
- sensitivity and retention defaults;
- created/updated timestamps and state version.

The system never copies an entire project automatically. A call preparation spec enumerates each approved source file with purpose, authority, sensitivity, and packaged name. The preparer copies only those files into the call request and hashes them twice before `READY`.

## 8. Call lifecycle

Canonical states are:

`DRAFT → PACKAGING → READY → HANDOFF_ACTIVE → COLLECTING → COLLECTED → VALIDATING → ACCEPTED → INTEGRATING → INTEGRATED`

Exceptional states are `NEEDS_CORRECTION`, `REJECTED`, `FAILED`, `CANCELLED`, and `STALE`. Pause is metadata preserving the prior state.

Every mutating command contains an idempotency key and expected state version. Duplicate keys return the original logical result. Ambiguous Send, collection, or integration never advances automatically.

## 9. CLI contract

All commands emit JSON to stdout and diagnostics to stderr. Important commands are:

```text
gptwebcall doctor
gptwebcall init
gptwebcall project register --spec <json>
gptwebcall project list
gptwebcall project show --project <id>
gptwebcall call prepare --spec <json>
gptwebcall call list [--project <id>] [--state <state>]
gptwebcall call show --call <id>
gptwebcall call authorize-go --call <id> --state-version <n> --idempotency-key <key>
gptwebcall call reveal-request --call <id>
gptwebcall call collect --call <id> [--files <json>]
gptwebcall call validate --call <id>
gptwebcall call accept|reject --call <id> --decision <json>
gptwebcall call record-integration --call <id> --evidence <json>
gptwebcall integrity check
gptwebcall index rebuild
gptwebcall backup create
gptwebcall legacy import --source <exchange-root>
```

The extension invokes the same application service through a strict native-message command allowlist.

## 10. Validation layers

1. Package eligibility: paths, names, sensitivity, schemas, hashes, prompt timestamp, expected outputs.
2. Go authorization: exact disclosure, unchanged digest, state version, user action.
3. Collection: explicit selection, stable regular files, safe copy, identity binding, quarantine.
4. Structural response: schema, IDs, digest, exact work/question/artifact coverage, artifact hashes.
5. Semantic response: Codex or Claude checks authority, evidence, calculations, and acceptance criteria.
6. Integration: external-repository instructions, impact analysis, tests, rollback, recorded evidence.
7. Completion: requirements and accepted/integrated evidence, not call count.

## 11. Security rules

- Treat all project files and model outputs as untrusted data.
- Resolve real paths and reject traversal, links/reparse points, device paths, unsafe Windows names, and roots outside explicit approvals.
- Never execute returned artifacts or extract archives automatically.
- Never log prompt/output bodies, credentials, cookies, tokens, or full sensitive paths by default.
- Native messaging accepts only the installed extension origin, protocol version, nonce, state version, and allowlisted command.
- No arbitrary shell command, arbitrary URL, arbitrary path read, or file bytes over native messaging.
- Secrets/sensitivity preflight is required before Go, with an explicit recorded override when allowed.

## 12. Implementation phases

1. Filesystem core, project registry, call preparation, validation, CLI, and canonical protocol.
2. Native host, file picker, thin side-panel extension, Go/Done vertical slice.
3. v1 schemas, correction lineage, integrity rebuild, backup/restore, and legacy importer.
4. Cross-client project/completion workflow and explicit integration evidence.
5. Installer, security hardening, clean-machine UAT, failure injection, and signed/private distribution.

Each phase preserves the manual workflow and has an independent rollback.
