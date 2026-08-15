import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

import { archiveVerdict } from "../lib/panel.js";

const read = (name) => readFile(new URL(`../${name}`, import.meta.url), "utf8");


/* The report has always carried three independent facts and the panel showed
 * one word. The operator read a PARTIAL-but-intact delivery as a failure once
 * already; a byte-perfect delivery of declared-partial work is COMPLETE
 * delivery, PARTIAL work, verified hashes, and no single word says that.
 */
test("an opened call renders three separate facts", async () => {
  const panel = await read("sidepanel.js");

  assert.match(panel, /resultFacts\(report\)/);
  assert.match(panel, /renderFactsInto\(facts, inspect\.validation\)/);
  // Not a single status pill standing in for all three.
  assert.doesNotMatch(panel, /resultStatus/);
});


/* A row has room for one word, and the archive still must not lie with it.
 * Delivery leads because it is the half this end can prove; a responder that
 * called its own work PARTIAL or BLOCKED demotes the row from good to
 * needs-a-look, which is the misreading that started all of this. */
test("an archive row never calls declared-partial work a success", () => {
  assert.deepEqual(
    archiveVerdict({ state: "COMPLETE", responseStatus: "COMPLETE" }),
    { label: "COMPLETE", tone: "ok" },
  );
  assert.deepEqual(
    archiveVerdict({ state: "COMPLETE", responseStatus: "PARTIAL" }),
    { label: "PARTIAL", tone: "wait" },
  );
  assert.deepEqual(
    archiveVerdict({ state: "COMPLETE", responseStatus: "BLOCKED" }),
    { label: "BLOCKED", tone: "wait" },
  );
  // A delivery that did not arrive intact says so regardless of the report.
  assert.deepEqual(
    archiveVerdict({ state: "INCOMPLETE", responseStatus: "COMPLETE" }),
    { label: "INCOMPLETE", tone: "bad" },
  );
  // No report read at all is not a verdict of fine.
  assert.deepEqual(
    archiveVerdict({ state: "COMPLETE", responseStatus: null }),
    { label: "COMPLETE", tone: "ok" },
  );
  assert.deepEqual(archiveVerdict({ state: "STOPPED" }), { label: "STOPPED", tone: "" });
});


/* Recall used to mean opening the exchange folder by hand. Every row is a
 * button now, and what it opens is metadata: state, report, defects, paths. */
test("past calls are inspectable from the panel", async () => {
  const html = await read("sidepanel.html");
  const panel = await read("sidepanel.js");
  const worker = await read("service_worker.js");

  assert.match(html, /id="past"/);
  // A button, not a list item, so it is reachable by keyboard.
  assert.match(panel, /head\.className = "row-head"/);
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
 * diagnosis a correction round would send is on screen before they decide
 * whether to open one. */
test("defects are shown before a correction round is offered", async () => {
  const panel = await read("sidepanel.js");

  assert.match(panel, /inspect\.defects/);
  assert.ok(
    panel.indexOf("defectList(inspect.defects")
      < panel.indexOf('accent("Open correction round"'),
    "the diagnosis is built before the button that acts on it",
  );
  // The companion caps what it sends to keep inside the 1 MB frame; a capped
  // list that says it is complete is worse than no list.
  assert.match(panel, /inspect\.defects_omitted/);
});


test("a correction round is visible as a round number", async () => {
  const panel = await read("sidepanel.js");

  assert.match(panel, /inspect\.repair_round > 0/);
  assert.match(panel, /\["rounds", String\(inspect\.repair_round\)\]/);
});


/* A resend and the call it came from are two rows with the same subject,
 * separated by a timestamp. The link is the only thing that says which. */
test("a resend says what it is a copy of", async () => {
  const panel = await read("sidepanel.js");

  assert.match(panel, /item\.clonedFrom/);
  assert.match(panel, /"resend of"/);
});


/* Attention order: whatever needs the next click is on top. Calls that need
 * something, then calls that are over — and an empty archive is not a heading
 * with nothing under it. */
test("calls that need something own the top of the panel", async () => {
  const html = await read("sidepanel.html");
  const panel = await read("sidepanel.js");

  const now = html.indexOf('id="now-card"');
  const past = html.indexOf('id="past-card"');
  assert.ok(now > 0 && now < past, "in-flight comes before the archive");
  assert.match(panel, /pastCard\.hidden = rows\.length === 0/);
  // The top section stays, and says so, because its absence is information.
  assert.match(panel, /nowEmpty\.hidden = calls\.length > 0/);
});


/* A filing failure recorded durably by the companion is attributed to the call
 * that expected the filename, so it survives the browser restart that erases
 * session storage — which is exactly when the operator needs it. */
test("a durable filing failure is shown on the call it belongs to", async () => {
  const panel = await read("sidepanel.js");
  const worker = await read("service_worker.js");

  assert.match(panel, /call\.record\?\.download_failures/);
  assert.match(worker, /nativeCommand\("download\.failure\.record"/);
  // Session storage is written first: if the native channel is the broken
  // piece, the immediate record is all there is.
  const body = worker.slice(worker.indexOf("async function recordDownloadFailure"));
  assert.ok(
    body.indexOf("lastDownloadFailure") < body.indexOf("download.failure.record"),
    "the session record is written before the durable one",
  );
});


/* Cloning prepares; it never sends. The finished call keeps its response,
 * because that response is the only copy of work the model already did. */
test("preparing a copy does not send it, and does not touch the original", async () => {
  const panel = await read("sidepanel.js");
  const worker = await read("service_worker.js");

  assert.match(panel, /type: "CLONE", exchangeId: item\.id/);
  assert.match(worker, /nativeCommand\("call\.clone"/);
  // The clone lands in the top list as a prepared call, and Go is a separate
  // press. Nothing chains one into the other.
  const body = panel.slice(panel.indexOf('accent("Prepare a copy"'));
  assert.doesNotMatch(body.slice(0, 400), /type: "GO"/);
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
