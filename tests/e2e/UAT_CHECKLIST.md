# Live non-sensitive UAT checklist

Automated tests do not substitute for this manual Chrome/ChatGPT check. Use only a harmless fixture request.

- [ ] Run `scripts\install.ps1` with the installed unpacked extension's ID, then load `extension\` unpacked in Chrome.
- [ ] Prepare a fixture call and verify the side panel shows its exact request files and expected main JSON.
- [ ] Click Go. Confirm ChatGPT opens and the panel waits for a real Attach files click.
- [ ] Click Attach files yourself. Confirm exactly the manifest files attach; the extension never clicks Send.
- [ ] Send manually. Download an unrelated file, then the main JSON and valid artifact.
- [ ] Confirm the unrelated file remains in Downloads and the matching files move to the exchange response directory.
- [ ] Click Done and validate. Confirm the panel shows `COMPLETE` and `validation\VALIDATION_REPORT.json` exists.
- [ ] Start another fixture; download a hash-mismatched artifact and confirm Done reports it invalid/incomplete without overwriting anything.
- [ ] Restart Chrome during an active call. Confirm the panel exposes Resume attachment/Stop and does not resend or reattach files automatically.
- [ ] With the extension disabled, follow `docs\MANUAL_FALLBACK.md` and confirm validation can still be completed safely.
