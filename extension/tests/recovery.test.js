import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";


test("side panel exposes an explicit user-controlled Resume action", async () => {
  const html = await readFile(new URL("../sidepanel.html", import.meta.url), "utf8");
  const panel = await readFile(new URL("../sidepanel.js", import.meta.url), "utf8");
  const worker = await readFile(new URL("../service_worker.js", import.meta.url), "utf8");

  assert.match(html, /id="resume-button"/);
  assert.match(panel, /type: "RESUME"/);
  assert.match(worker, /case "RESUME"/);
  assert.match(worker, /nativeCommand\("call\.resume"/);
});
