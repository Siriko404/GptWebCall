import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";


test("an empty active list is reported as absence, not as a running call", async () => {
  const worker = await readFile(new URL("../service_worker.js", import.meta.url), "utf8");

  // [] is truthy in JavaScript, so any panel testing `if (state.active)` would
  // treat "no calls running" as "a call is running" and disable Go.
  assert.match(worker, /active\.length === 0 \? null : active/);
});


test("the panel tests the active list by length, never by truthiness", async () => {
  const panel = await readFile(new URL("../sidepanel.js", import.meta.url), "utf8");

  assert.doesNotMatch(panel, /if \(state\.active\)/);
  assert.match(panel, /state\.active\?\.length/);
});
