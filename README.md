# GPT Web Call

GPT Web Call is a small local bridge for bounded, human-authorized ChatGPT Web work. It prepares an immutable request package, attaches it only after you click ChatGPT's attachment control, watches downloads you start, and validates the returned JSON/artifacts when you click Done.

Read [WEB_CALL_PROTOCOL.md](WEB_CALL_PROTOCOL.md) before using it. The system intentionally has one active call, no automatic Send, no response scraping, and a permanent manual fallback.

Development verification:

```powershell
go test ./... -race -count=1
python -m unittest discover -s companion/tests -v
npm --prefix extension test
```
