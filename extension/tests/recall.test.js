import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const read = (name) => readFile(new URL(`../${name}`, import.meta.url), "utf8");


/* The report has always carried three independent facts and the panel showed
 * one word. The operator read a PARTIAL-but-intact delivery as a failure once
 * already; a byte-perfect delivery of declared-partial work is COMPLETE
 * delivery, PARTIAL work, verified hashes, and no single word says that.
 */
test("the result card renders three separate facts", async () => {
  const html = await read("sidepanel.html");
  const panel = await read("sidepanel.js");

  assert.match(html, /id="result-facts"/);
  assert.match(panel, /resultFacts\(report\)/);
  // Not a single status pill standing in for all three.
  assert.doesNotMatch(panel, /resultStatus/);
});


/* Recall used to mean opening the exchange folder by hand. The archive rows
 * are buttons now, and what they open is metadata: state, report, defects,
 * paths. */
test("past calls are inspectable from the panel", async () => {
  const html = await read("sidepanel.html");
  const panel = await read("sidepanel.js");
  const worker = await read("service_worker.js");

  assert.match(html, /id="history-card"/);
  // A button, not a list item, so it is reachable by keyboard.
  assert.match(panel, /button\.className = "h-row"/);
  assert.match(panel, /type: "INSPECT", exchangeId/);
  assert.match(worker, /case "INSPECT":/);
  assert.match(worker, /nativeCommand\("call\.inspect"/);
});


/* The panel points at responses; it never renders them. Returned content stays
 * inert on disk, which is where "never execute what a call returns" can hold.
 */
test("recall shows metadata and paths, never response content", async () => {
  const panel = await read("sidepanel.js");

  assert.match(panel, /inspect\.paths\?\.main_response/);
  // Nothing reads a file body into the DOM.
  assert.doesNotMatch(panel, /inspect\.content/);
  assert.doesNotMatch(panel, /innerHTML/);
});


/* Every incomplete call sent the operator to a terminal to ask why. The same
 * diagnosis a correction round would send is now on screen before they decide
 * whether to open one. */
test("defects are shown before a correction round is offered", async () => {
  const html = await read("sidepanel.html");
  const panel = await read("sidepanel.js");

  assert.match(html, /id="defect-list"/);
  assert.match(panel, /inspect\.defects/);
  // Only an INCOMPLETE delivery has defects worth acting on; a PARTIAL but
  // intact one must not be dressed up as broken.
  assert.match(panel, /report\.status !== "INCOMPLETE"/);
});


test("a correction round is visible as a round number", async () => {
  const html = await read("sidepanel.html");
  const panel = await read("sidepanel.js");

  assert.match(html, /id="result-round"/);
  assert.match(panel, /round \$\{inspect\.repair_round\}/);
});


/* Attention order: whatever needs the next click is on top. A running call
 * outranks the launch queue, and the launch queue is collapsed rather than
 * removed so the operator can still reach it. */
test("the running call owns the top of the stack", async () => {
  const html = await read("sidepanel.html");
  const panel = await read("sidepanel.js");

  const flight = html.indexOf('id="flight-card"');
  const launch = html.indexOf('id="launch-card"');
  const history = html.indexOf('id="history-card"');
  assert.ok(flight > 0 && flight < launch, "in-flight comes before launch");
  assert.ok(launch < history, "launch comes before the archive");
  assert.match(panel, /collapseLaunch\(handoffs\.length > 0\)/);
  // Empty sections disappear rather than sitting there empty.
  assert.match(panel, /flightCard\.hidden = handoffs\.length === 0/);
  assert.match(panel, /historyCard\.hidden = recent\.length === 0/);
});


/* A filing failure recorded durably by the companion is attributed to the call
 * that expected the filename, so it survives the browser restart that erases
 * session storage — which is exactly when the operator needs it. */
test("a durable filing failure is shown on the call it belongs to", async () => {
  const panel = await read("sidepanel.js");
  const worker = await read("service_worker.js");

  assert.match(panel, /activeRecord\?\.download_failures/);
  assert.match(worker, /nativeCommand\("download\.failure\.record"/);
  // Session storage is written first: if the native channel is the broken
  // piece, the immediate record is all there is.
  const body = worker.slice(worker.indexOf("async function recordDownloadFailure"));
  assert.ok(
    body.indexOf("lastDownloadFailure") < body.indexOf("download.failure.record"),
    "the session record is written before the durable one",
  );
});


/* The boundary, restated as a test because a redesign is exactly when it would
 * be eroded by accident. */
test("no panel code sends, attaches, downloads, or finishes on its own", async () => {
  const panel = await read("sidepanel.js");
  const worker = await read("service_worker.js");

  for (const source of [panel, worker]) {
    assert.doesNotMatch(source, /Input\.dispatchKeyEvent/);
    assert.doesNotMatch(source, /\.click\(\)/);
    assert.doesNotMatch(source, /chrome\.downloads\.download/);
  }
  // Done and Stop are per-call buttons the operator presses, never timers.
  assert.doesNotMatch(panel, /setTimeout\([^)]*DONE/);
});
