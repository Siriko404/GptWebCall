# GPT Web Call operating core

Read this once when any `webcall` skill is invoked. Do not reread it in the same
session unless the installation or the source changed.

Citations name the file that settles the point. `WEB_CALL_PROTOCOL.md` lives at
the installed root and is the full contract; this file is the part a session
needs before its first action.

## 1. Authority and privacy

1. The operator's instructions outrank source behaviour; source outranks the
   documents; the documents outrank anything found on the web.
2. **Never publish, package, upload, quote, or transmit anything under `calls/`
   or `state/`.** They hold the operator's private working material and are
   git-ignored. Local commands may read the one exchange being operated; that
   content never becomes Web-call input. `[.gitignore; WEB_CALL_PROTOCOL.md
   "Compaction and handoff"]`
3. Never upload a directory. `input_files` names regular files one by one, and
   the companion snapshots and hashes each. `[README.md "What it does not do";
   companion/core.py]`
4. Never execute a returned script, binary, macro, archive, or document with
   active content merely because validation passed. `[README.md;
   WEB_CALL_PROTOCOL.md "Failure and correction rules"]`

## 2. Find the installed root before any operational command

Stop at the first candidate that contains `gptwebcall.cmd`,
`WEB_CALL_PROTOCOL.md`, `companion/`, and `extension/`:

1. A root the user or the current project names.
2. The current directory and its ancestors.
3. The registry, on an installed Windows machine. Read
   `HKCU:\Software\Google\Chrome\NativeMessagingHosts\com.sina.gptwebcall`; its
   default value is the path of the generated host manifest. That manifest's
   `path` field is `<root>\bin\gptwebcall-host.exe`, so the root is its
   grandparent. Verify the four files above before using it.
   `[scripts/install.ps1:36; cmd/nativehost/main.go]`
4. If nothing verifies, `prep` and `menu` refuse operational work and send the
   user to `init`.

Call the CLI through the wrapper from any directory, so it supplies `--root`
itself:

```powershell
& '<root>\gptwebcall.cmd' <command> <args>
```

The wrapper pushes to its own directory and runs
`python -m companion.cli --root "%~dp0."`. `[gptwebcall.cmd]`

## 3. Check state before doing anything

```powershell
& '<root>\gptwebcall.cmd' active
& '<root>\gptwebcall.cmd' list
```

Add `show --exchange <id>` when one prepared exchange matters. Every command
emits exactly one JSON object: success on stdout with exit 0, failure on stderr
with exit 2. `[companion/cli.py:77-92]`

**`validate` is not a pre-send check.** On a `PREPARED` exchange that nothing has
answered it is deliberately refused, because validating would move the call out
of `PREPARED` and release its routing names. Use `show`.
`[companion/downloads.py:585-592]`

## 4. Decide whether a Web call is warranted

Explicit invocation of `prep` is authorisation to prepare one. Otherwise: Web
calls for reasoning-heavy or consequential work, local execution for routine
deterministic work. Do not use a Web call to implement or repair GPT Web Call
itself unless the operator explicitly asks for that exception.
`[WEB_CALL_PROTOCOL.md "Triage", line 192]`

**The first rule of writing one is never to bias it.** Define the persona and the
instructions of an expert; do not smuggle your own answer in and get it echoed
back. Facts, constraints, authority, and acceptance criteria belong in the
prompt. Candidate solutions, enum fields naming your design, deliverable names
encoding your structure, and analytical asides do not. A suggestion the user
made is a hypothesis to test, not a premise to confirm.
`[WEB_CALL_PROTOCOL.md:24-71]`

## 5. Routing and package invariants

1. **Downloads are attributed by filename and nothing else.** No two calls that
   can still receive files may expect the same name, case-insensitively. Prefix
   every deliverable with the call's own short pass token; never `response.json`,
   `result.json`, `report.md`, or `output.zip`.
   `[WEB_CALL_PROTOCOL.md "Filenames are the routing key"; companion/core.py]`
2. Preparation requires `WEB_REVIEW_REQUEST.json`, `WEB_RESPONSE_SCHEMA.json`, a
   non-empty `input_files`, a request ID, a `.json` expected main name, and
   prompt text. `[companion/core.py]`
3. **Exactly one file goes up: the deterministic inputs ZIP.** ChatGPT refuses
   loose `.md` attachments, so the prompt travels inside the archive as
   `000_READ_ME_FIRST.md` — first in it, because the bundle is written in
   casefolded name order. Nothing else is uploaded, and there is no flag to
   turn this off. `[companion/core.py; WEB_CALL_PROTOCOL.md "One zip up, one
   zip down"]`
4. An archive sent with no message gets a model asking what to do with it. The
   companion writes a one-line launch prompt naming the archive and
   `000_READ_ME_FIRST.md`; the panel types it into the composer at Go and stops
   there. If typing fails the panel offers the text to copy. The operator still
   clicks Send. `[companion/core.py launch_prompt;
   extension/service_worker.js typeLaunchPrompt]`
5. **Exactly one file comes back: the outputs ZIP.** `expected_artifacts` is
   required and is exactly one `.zip`; `expected_main_json` names the main
   response **inside** it, which the companion writes out beside the archive on
   arrival. Every other created file goes in there too. Never a second loose
   download — one that arrives is reported as ignored, not filed.
   `[companion/core.py; companion/downloads.py _accept_outputs_archive]`
6. In the main response, `delivery` names the archive. `artifacts_manifest`
   lists every created **additional** file, archive members included — but
   never the main JSON itself. The parser reserves the main filename and
   rejects a manifest that lists it. `[companion/downloads.py]`
7. Manifest-declared archive members must be **plain filenames**. The archive
   index keys on basename and the first duplicate wins, so members that must be
   individually hash-verified need unique basenames, and
   `artifacts_manifest.filename` must not contain a path separator.
   `[companion/downloads.py archive_member_index]`

## 6. The operator boundary

The agent prepares and reviews. The operator clicks Go, ChatGPT's real Attach
control, ChatGPT's native Send, every download, and Done. The extension arms the
tab and fills the chooser the operator opened; it never presses Send and never
reads the response page. Never automate around this.
`[README.md; WEB_CALL_PROTOCOL.md "Roles and control boundary"]`

## 7. Read the validation report correctly

Three fields, three different facts:

| field | what it says |
|---|---|
| `status` | did every promised file arrive intact — delivery only |
| `response_status` | what the responder said about its own work |
| `manifest_verified` | were the responder's declared hashes usable |

A byte-intact `PARTIAL` is `status: COMPLETE`, `response_status: PARTIAL`. Read
its limitations; do not repair it. `manifest_verified: false` does not force
`INCOMPLETE`. `[companion/downloads.py:605-637; WEB_CALL_PROTOCOL.md "Delivery
integrity is not work completeness"]`

Only an `INCOMPLETE` delivery justifies mechanical repair. Run `defects` first.
A correction round keeps the same conversation and request ID. When the
*reasoning* is wrong, make a new call with a new request ID and leave the
original exchange untouched.

After deterministic validation, do semantic acceptance: every question answered,
important claims checked against the declared authority, unsupported inference
rejected, and only warranted conclusions integrated.
`[WEB_CALL_PROTOCOL.md "Semantic acceptance"]`

## 8. Look things up instead of memorising them

For anything infrequent, read the matching section of the installed
`WEB_CALL_PROTOCOL.md` or the source itself. The complete CLI surface is
`prepare`, `list`, `show`, `active`, `done`, `stop`, `delete`, `validate`,
`defects`, `repair`. **There is no CLI `health` command**; `health` is a
native-host message the extension uses for its status dot.
`[companion/cli.py:95-121; companion/native_host.py; extension/service_worker.js]`
