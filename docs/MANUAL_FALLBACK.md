# Manual fallback

The manual fallback preserves the same evidence layout if the extension is unavailable.

1. Use `.\gptwebcall.cmd list` and select one `PREPARED` exchange.
2. Open its `EXCHANGE_MANIFEST.json`; upload exactly the files listed in `request_files` from its `request\` directory, including `PROMPT_YYYY-MM-DD_HHMMSS.txt`.
3. In ChatGPT Web, manually send the prepared files. Download the required main JSON and every listed artifact.
4. Copy only those returned files into that exchange's `response\` directory. Do not replace a different existing file.
5. Reopen the extension and click **Done and validate**. It writes `validation\VALIDATION_REPORT.json` and reports missing or invalid files.

If another call is active, stop it first; never create competing active-call state. Unrelated downloads are not evidence and should remain outside the response folder.
