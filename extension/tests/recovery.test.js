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


/* Resume is the path a conductor call takes after a browser restart, and a
 * restart is exactly when the handoff naming its tab is gone. Resolving the
 * destination the same way Go does is what keeps the thread; creating a tab
 * outright would lose it with no error and no warning.
 */
test("resume sends the destination, and resolves it the way Go does", async () => {
  const panel = await readFile(new URL("../sidepanel.js", import.meta.url), "utf8");
  const worker = await readFile(new URL("../service_worker.js", import.meta.url), "utf8");

  assert.match(panel, /type: "RESUME", mode: goMode\.value/);
  assert.match(worker, /case "RESUME":\s*\n\s*return resumeCall\(message\.exchangeId, message\.mode\);/);
  assert.match(worker, /async function resumeCall\(exchangeId, mode\) \{\s*\n\s*const tab = await resolveTargetTab\(mode\);/);
  assert.doesNotMatch(
    worker.slice(worker.indexOf("async function resumeCall")),
    /chrome\.tabs\.create/,
  );
});
