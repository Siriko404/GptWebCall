# Manual fallback

Use this when the extension is unavailable. `WEB_CALL_PROTOCOL.md` remains authoritative.

1. From the canonical root, run `.\gptwebcall.cmd active` and `.\gptwebcall.cmd list`.
2. Select one exchange; inspect it with `.\gptwebcall.cmd show --exchange <exchange_id>`.
3. Upload the one file named in its `attach_files`, from `request\`: the inputs archive. The prompt is inside it as `000_READ_ME_FIRST.md`. Send it with one line of your own — open the archive, read `000_READ_ME_FIRST.md` first, follow it — because an archive sent bare gets a model asking what to do with it.
4. The operator clicks ChatGPT's native Send and manually downloads the expected main JSON plus all created artifacts.
5. Place only those returned files in that exchange's `response\` directory under their expected names. Never overwrite different existing bytes.
6. If the exchange was never active, run `.\gptwebcall.cmd validate --exchange <exchange_id>`.
7. If it is active, run `.\gptwebcall.cmd done`.
8. Read `validation\VALIDATION_REPORT.json`; then perform semantic review before using the output.

Use `.\gptwebcall.cmd stop` only to abandon an active call. Unrelated downloads remain outside the response folder. A substantive repair requiring ChatGPT reasoning becomes a new correction call; the original exchange stays unchanged.
