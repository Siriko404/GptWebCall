import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";


test("side panel exposes an explicit user-controlled Resume action", async () => {
  const html = await readFile(new URL("../sidepanel.html", import.meta.url), "utf8");
  const panel = await readFile(new URL("../sidepanel.js", import.meta.url), "utf8");
  const worker = await readFile(new URL("../service_worker.js", import.meta.url), "utf8");

  // One recovery card, one Resume per lost call, named by its exchange id.
  assert.match(html, /id="recovery-card"/);
  assert.match(panel, /type: "RESUME"/);
  assert.match(panel, /exchangeId: record\.exchange_id/);
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


/* A fresh conversation needs telling what the attachment is. A thread the
 * operator is already working in does not: it has the context that makes the
 * archive make sense, and typing into it would put words in a conversation the
 * operator is conducting. */
test("the launch line is typed only into a fresh conversation", async () => {
  const worker = await readFile(new URL("../service_worker.js", import.meta.url), "utf8");

  const body = worker.slice(
    worker.indexOf("async function typeLaunchPrompt"),
    worker.indexOf("async function resumeCall"),
  );
  assert.match(body, /if \(mode === "current"\) \{\s*\n\s*return \{ inserted: null/);
  assert.ok(
    body.indexOf('mode === "current"') < body.indexOf("insertPromptIntoComposer"),
    "the current-conversation case returns before anything is typed",
  );
});


test("a launch line that could not be typed is offered to copy; one never attempted is not", async () => {
  const panel = await readFile(new URL("../sidepanel.js", import.meta.url), "utf8");

  assert.match(panel, /function showLaunchPrompt\(handoff\)/);
  // Strictly false. `null` is "never attempted" and must not surface a card.
  assert.match(panel, /handoff\.launchInserted !== false/);
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

  assert.match(panel, /mode: recoveryMode\.value/);
  assert.match(worker, /case "RESUME":\s*\n\s*return resumeCall\(message\.exchangeId, message\.mode\);/);
  assert.match(worker, /async function resumeCall\(exchangeId, mode\) \{\s*\n\s*const tab = await resolveTargetTab\(mode\);/);
  assert.doesNotMatch(
    worker.slice(worker.indexOf("async function resumeCall")),
    /chrome\.tabs\.create/,
  );
});


/* What a browser restart destroys is the binding to a conversation, and that
 * cannot be guessed back. The old panel resumed with whatever the shared Go
 * dropdown happened to say, which is how a conductor call was once re-armed
 * against a blank conversation with no warning. Recovery now asks, and Resume
 * stays disabled until the operator answers.
 */
test("recovery refuses to guess the destination a restart destroyed", async () => {
  const html = await readFile(new URL("../sidepanel.html", import.meta.url), "utf8");
  const panel = await readFile(new URL("../sidepanel.js", import.meta.url), "utf8");

  // No preselected value: the first option is a disabled placeholder.
  assert.match(html, /id="recovery-mode"/);
  assert.match(html, /<option value="" disabled selected>/);
  // And the button cannot be pressed until one is chosen.
  assert.match(panel, /resume\.disabled = !recoveryMode\.value/);
  // The recovery card only appears when the companion holds calls the browser
  // has lost — not merely because a call is running.
  assert.match(panel, /handoffs\.length === 0 \? activeRecords : \[\]/);
});
