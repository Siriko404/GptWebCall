# GPT Web Call

GPT Web Call is a small local bridge for bounded, human-authorized ChatGPT Web work. It prepares an immutable request package, attaches it only after you click ChatGPT's attachment control, watches downloads you start, and validates the returned JSON/artifacts when you click Done.

Give any new Codex or Claude Code session [WEB_CALL_PROTOCOL.md](WEB_CALL_PROTOCOL.md). It is the complete operating runbook: triage, exact request templates, command reference, extension workflow, deterministic and semantic validation, restart recovery, correction rules, and extension-free manual fallback.

The system intentionally has one active call, no automatic Send, no response scraping, and no automatic trust in model output.

Development verification:

```powershell
go test ./... -race -count=1
python -m unittest discover -s companion/tests -v
npm --prefix extension test
```
