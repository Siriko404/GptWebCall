# Improvised end-to-end smoke test

Use only when `init` reaches its final step, or when `menu health smoke` is
explicitly asked for.

**Build it fresh, every time.** No repository fixture, no checked-in smoke
request, no prebuilt package. A canned probe passes on a machine where the live
path is broken, because the canned parts are the parts that were already known to
work. That is an owner requirement, not a preference.

## 1. Build a fresh probe

1. Generate a token: a GUID plus the current UTC timestamp. Work in a temporary
   directory outside `calls/` and `state/`.
2. Write `smoke_source.txt` containing the token and two randomly generated short
   key/value facts. Compute its exact byte size and SHA-256 locally, now.
3. Derive a request ID and a pass prefix from the token, e.g.
   `webcall-smoke-<short-token>-v1`. Deliverables are `<pass>_response.json` and
   `<pass>_outputs.zip`. Unique names are mandatory: filename is the only routing
   key.
4. Write a fresh `WEB_REVIEW_REQUEST.json` asking the responder to read the
   supplied source, report the token and both facts, reproduce the source's
   SHA-256, and create `smoke_receipt.txt` holding those values. Forbid outside
   research. Require honest `PARTIAL` or `BLOCKED` if it cannot comply.
5. Write a fresh `WEB_RESPONSE_SCHEMA.json` requiring `request_id`, `status`,
   the smoke results, `artifacts_manifest`, `limitations`, and `delivery`.
   Require manifest entries for the outputs ZIP and for `smoke_receipt.txt` —
   never for the main JSON itself.
6. Write a fresh preparation spec: `input_files` = the request JSON, the schema
   JSON, and `smoke_source.txt`; `expected_main_json` = the unique response name;
   `expected_artifacts` = the unique outputs ZIP.
7. `prompt_text` must name exactly those two downloads, put every other file
   inside the ZIP, require sizes and digests computed from the bytes actually
   written, and forbid conversational text outside the downloads.

## 2. Prepare and inspect

```powershell
& '<root>\gptwebcall.cmd' prepare --spec <fresh-spec>
& '<root>\gptwebcall.cmd' show --exchange <id>
```

Before any browser action confirm: state `PREPARED`, request ID matches, the
expected filenames are the fresh ones, and `attach_files` is exactly the
generated prompt plus the inputs ZIP. `show` is the pre-send check — not
`validate`.

## 3. Operator round trip

Ask the operator: side panel → **Go** → ChatGPT's **Attach files** → **Send** →
download both named files → **Done and validate**. The extension attaches; it
never sends.

## 4. Pass or fail

Pass only if all of these hold:

- delivery `status` is `COMPLETE`;
- `response_status` is `COMPLETE` — for a probe this small, anything else is a
  failure to investigate, even though `PARTIAL` is a valid outcome in real work;
- `manifest_verified` is `true`;
- the response and `smoke_receipt.txt` carry the fresh token, both fresh facts,
  and the SHA-256 you computed locally;
- the outputs ZIP exists under its expected name and its declared member sizes
  and digests verify.

If the files reached the Downloads folder but never reached the exchange, the
smoke test has failed even if a later manual `done` or `validate` rescues it.
Record that, and say so plainly.

## 5. What this test gives up

It exercises live ChatGPT Web, Chrome attachment, native messaging, filename
routing, download collection, archive-member accounting, and validation in a
single path. In exchange it is slow, needs operator clicks, spends a live model
interaction, and can fail because the network or the model is unavailable while
the local code is sound.

Run the unit suites first so this is an integration test rather than the first
diagnostic. `README.md` records that `tests/e2e/` still encodes an older request
contract and is not a release gate.
