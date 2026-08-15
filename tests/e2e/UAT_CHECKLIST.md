# Live non-sensitive UAT checklist

Automated tests do not substitute for this manual Chrome/ChatGPT check. Use only a harmless fixture request.

- [ ] Run `scripts\install.ps1` with the installed unpacked extension's ID, then load `extension\` unpacked in Chrome.
- [ ] Prepare a fixture call. Click its row in the panel's top list and verify the opened drawer shows its exact request id, the one inputs ZIP going up, and the one archive expected back.
- [ ] Click Go. Confirm ChatGPT opens and the panel waits for a real Attach files click.
- [ ] Click Attach files yourself. Confirm exactly the manifest files attach; the extension never clicks Send.
- [ ] Send manually. Download an unrelated file, then the main JSON and valid artifact.
- [ ] Confirm the unrelated file remains in Downloads and the matching files move to the exchange response directory.
- [ ] Click Done and validate. Confirm the panel shows `COMPLETE` and `validation\VALIDATION_REPORT.json` exists.
- [ ] Start another fixture; download a hash-mismatched artifact and confirm Done reports it invalid/incomplete without overwriting anything.
- [ ] Restart Chrome during an active call. Confirm that call's row offers Resume attachment and Stop, that Resume stays disabled until a destination is chosen, and that nothing resends or reattaches automatically.
- [ ] Confirm the finished call moved to the Previous list, and that its row shows the delivery state alone — no work or hash verdict anywhere in the panel.
- [ ] Open a finished call and click Prepare a copy. Confirm a new PREPARED call appears in the top list, the original keeps its state and its response files, and nothing was sent.
- [ ] Stop a call before sending it, then Prepare a copy from its row. This is the only route out of STOPPED — go, done and repair all refuse it.
- [ ] With the extension disabled, follow `docs\MANUAL_FALLBACK.md` and confirm validation can still be completed safely.
