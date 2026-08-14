import assert from "node:assert/strict";
import test from "node:test";

import { readFile } from "node:fs/promises";

import { shouldObserveDownload } from "../lib/downloads.js";


const active = {
  monitoring: true,
  monitoringStartedAt: "2026-07-14T19:30:00.000Z",
  downloadBaseline: [1, 2],
  observedDownloadIds: [3],
};


test("observes only downloads created inside the active monitoring window", () => {
  assert.equal(
    shouldObserveDownload(active, {
      id: 4,
      startTime: "2026-07-14T19:30:01.000Z",
    }),
    true,
  );
  assert.equal(
    shouldObserveDownload(active, {
      id: 5,
      startTime: "2026-07-14T19:29:59.000Z",
    }),
    false,
  );
});


test("does not observe baseline, repeated, malformed, or post-Done downloads", () => {
  assert.equal(
    shouldObserveDownload(active, { id: 1, startTime: "2026-07-14T19:30:01.000Z" }),
    false,
  );
  assert.equal(
    shouldObserveDownload(active, { id: 3, startTime: "2026-07-14T19:30:01.000Z" }),
    false,
  );
  assert.equal(shouldObserveDownload(active, { id: "4", startTime: "bad" }), false);
  assert.equal(
    shouldObserveDownload(
      { ...active, monitoring: false },
      { id: 4, startTime: "2026-07-14T19:30:01.000Z" },
    ),
    false,
  );
});


/* The regression this file exists for.
 *
 * Deciding a download took two events: onCreated wrote its id into a tracker in
 * session storage, and onChanged submitted only ids found there. Both halves
 * were an unlocked read-modify-write, so two downloads created together both
 * read the empty tracker and the second write erased the first. The erased one
 * completed, failed the lookup, and vanished without an error anywhere. It cost
 * three real calls, each rescued only by running `validate` by hand.
 *
 * One event now, and the decision is made from the download itself. A tracker
 * reappearing here is that bug coming back.
 */
test("a completed download is decided from one event, with no state kept between two", async () => {
  const worker = await readFile(new URL("../service_worker.js", import.meta.url), "utf8");

  assert.doesNotMatch(worker, /downloadTracker/);
  assert.doesNotMatch(worker, /downloads\.onCreated\.addListener/);
  assert.match(worker, /downloads\.onChanged\.addListener/);
  // The item is fetched and judged inside the one handler.
  assert.match(worker, /chrome\.downloads\.search\(\{ id: delta\.id \}\)/);
  assert.match(worker, /anyShouldObserveDownload\(handoffs, item\)/);
});


test("only a completed download is submitted", async () => {
  const worker = await readFile(new URL("../service_worker.js", import.meta.url), "utf8");

  assert.match(worker, /delta\?\.state\?\.current !== "complete"/);
  // monitoring: false is still the gate that Done closes.
  assert.equal(
    shouldObserveDownload(
      { ...active, monitoring: false },
      { id: 4, startTime: "2026-07-14T19:30:01.000Z" },
    ),
    false,
  );
});
