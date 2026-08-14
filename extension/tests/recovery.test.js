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


/* One zip goes up with the prompt inside it, so the message ChatGPT receives
 * says nothing on its own and a bare archive gets a model asking what to do.
 * The companion writes the line; Go types it.
 *
 * The ordering is the part that breaks silently. insertPromptIntoComposer
 * attaches its own debugger session and detaches in `finally`, so running it
 * after armTab would throw on the second attach and strip the file-chooser
 * interception off a tab that was waiting for it.
 */
test("Go types the launch line, and types it before arming the tab", async () => {
  const worker = await readFile(new URL("../service_worker.js", import.meta.url), "utf8");

  const body = worker.slice(
    worker.indexOf("async function beginGo"),
    worker.indexOf("async function typeLaunchPrompt"),
  );
  const typed = body.indexOf("typeLaunchPrompt");
  const armed = body.indexOf("armTab(");
  assert.ok(typed > 0, "beginGo types the launch line");
  assert.ok(armed > typed, "the launch line is typed before the tab is armed");

  assert.match(worker, /result\.launch_prompt/);
  // Failing to type it hands the operator the text instead of losing the call.
  assert.match(worker, /inserted: false/);
});


test("a launch line that could not be typed is offered to copy, and one that was is not", async () => {
  const panel = await readFile(new URL("../sidepanel.js", import.meta.url), "utf8");

  assert.match(panel, /function showLaunchPrompt\(handoff\)/);
  assert.match(panel, /if \(!handoff \|\| handoff\.launchInserted\) \{\s*\n\s*return;/);
  assert.match(panel, /showPromptToCopy\(handoff\.launchPrompt\)/);
  assert.match(panel, /showPromptToCopy\(handoff\?\.repairPrompt\)/);
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
