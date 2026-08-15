import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

import { callCentre } from "../lib/panel.js";


test("an empty active list is reported as absence, not as a running call", async () => {
  const worker = await readFile(new URL("../service_worker.js", import.meta.url), "utf8");

  // [] is truthy in JavaScript, so any panel testing `if (state.active)` would
  // treat "no calls running" as "a call is running".
  assert.match(worker, /active\.length === 0 \? null : active/);
});


/* The companion reports absence as null and presence as an array, so every
 * consumer has to count rather than test. callCentre is the one place that
 * normalises it now, which is why this is a behaviour test and not a grep. */
test("the panel counts the active list, and never tests it for truthiness", async () => {
  const panel = await readFile(new URL("../sidepanel.js", import.meta.url), "utf8");
  assert.doesNotMatch(panel, /if \(state\.active\)/);

  assert.deepEqual(callCentre({ active: null }).now, []);
  assert.deepEqual(callCentre({}).now, []);
  assert.equal(callCentre({ active: [{ exchange_id: "ex-1" }] }).now.length, 1);
});


/* A call appears once. `recent` is every exchange the companion knows about,
 * prepared and running ones included, so the archive is what is left after the
 * top list has taken what it needs. Otherwise a running call sits in the panel
 * twice: once as work, once as history. */
test("a call in flight is not also in the archive", () => {
  const { now, past } = callCentre({
    active: [{ exchange_id: "ex-run" }],
    ready: [{ exchange_id: "ex-ready", subject: "ready one" }],
    recent: [
      { exchange_id: "ex-run", subject: "running one", state: "ACTIVE" },
      { exchange_id: "ex-ready", subject: "ready one", state: "PREPARED" },
      { exchange_id: "ex-old", subject: "finished one", state: "COMPLETE" },
    ],
  });

  assert.deepEqual(now.map((call) => call.id), ["ex-run", "ex-ready"]);
  assert.deepEqual(past.map((row) => row.id), ["ex-old"]);
});


/* Running calls come first in the top list: a call waiting on the operator
 * outranks one that has not been sent. */
test("running calls sit above prepared ones", () => {
  const { now } = callCentre({
    ready: [{ exchange_id: "ex-ready" }],
    active: [{ exchange_id: "ex-run" }],
  });

  assert.deepEqual(now.map((call) => [call.id, call.state]), [
    ["ex-run", "ACTIVE"],
    ["ex-ready", "PREPARED"],
  ]);
});
