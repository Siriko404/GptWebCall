import assert from "node:assert/strict";
import test from "node:test";

import {
  describeDownloadFailure,
  describeStage,
  downloadGuard,
  formatBytes,
  formatElapsed,
  resultFacts,
} from "../lib/panel.js";

const files = (...arrived) =>
  arrived.map((flag, index) => ({
    filename: index === 0 ? "pass_response.json" : `pass_outputs_${index}.zip`,
    arrived: flag,
    size: flag ? 1024 : 0,
  }));

const progress = (...arrived) => ({
  files: files(...arrived),
  received: arrived.filter(Boolean).length,
  expected: arrived.length,
});

test("Done is blocked while an expected file is still missing", () => {
  const guard = downloadGuard(progress(true, false));

  assert.equal(guard.blockDone, true);
  assert.match(guard.warning, /pass_outputs_1\.zip/);
  assert.match(guard.warning, /stops monitoring/);
  assert.equal(guard.doneLabel, "Done and validate (1/2)");
});

test("Done opens once every expected file has landed", () => {
  const guard = downloadGuard(progress(true, true));

  assert.equal(guard.blockDone, false);
  assert.equal(guard.warning, "");
  assert.equal(guard.doneLabel, "Done and validate (2/2)");
});

test("the operator can force Done, and the warning stays visible when they do", () => {
  const guard = downloadGuard(progress(true, false), true);

  assert.equal(guard.blockDone, false);
  assert.notEqual(guard.warning, "");
});

test("every missing file is named, not just counted", () => {
  const guard = downloadGuard(progress(false, false, false));

  assert.match(guard.warning, /3 files have not arrived/);
  assert.match(guard.warning, /pass_response\.json/);
  assert.match(guard.warning, /pass_outputs_2\.zip/);
});

test("without progress data the panel must not block the operator", () => {
  for (const value of [null, undefined, {}, { files: [] }, { files: "nope" }]) {
    assert.equal(downloadGuard(value).blockDone, false, `blocked on ${JSON.stringify(value)}`);
  }
});

test("byte sizes stay short enough for a narrow panel", () => {
  assert.equal(formatBytes(0), "0 B");
  assert.equal(formatBytes(999), "999 B");
  assert.equal(formatBytes(1536), "1.5 KB");
  assert.equal(formatBytes(1024 * 1024 * 3.25), "3.3 MB");
  assert.equal(formatBytes(1024 * 1024 * 40), "40 MB");
  assert.equal(formatBytes("not a number"), "");
});

test("elapsed time reads as a duration and never as a negative", () => {
  const now = Date.parse("2026-07-21T20:10:00Z");

  assert.equal(formatElapsed("2026-07-21T20:09:15Z", now), "45s");
  assert.equal(formatElapsed("2026-07-21T20:08:25Z", now), "1m 35s");
  assert.equal(formatElapsed("2026-07-21T18:40:00Z", now), "1h 30m");
  assert.equal(formatElapsed("2026-07-21T20:11:00Z", now), "0s");
  assert.equal(formatElapsed(undefined, now), "");
});

test("an unknown stage falls back to its own name rather than going blank", () => {
  assert.equal(describeStage("ATTACHED"), "Files attached. Review them, then click Send.");
  assert.equal(describeStage("SOMETHING_NEW"), "SOMETHING_NEW");
  assert.equal(describeStage(undefined), "Running.");
});

test("a download that could not be filed tells the operator how to recover", () => {
  const message = describeDownloadFailure({
    downloadId: 42,
    message: "Native companion failed",
    at: "2026-08-08T18:00:00Z",
  });

  assert.match(message, /Download 42/);
  assert.match(message, /Native companion failed/);
  // The recovery matters more than the cause: the bytes are safe, and the
  // operator has to move them before Done stops monitoring.
  assert.match(message, /still in your downloads folder/);
});

test("no failure renders nothing at all", () => {
  assert.equal(describeDownloadFailure(null), "");
  assert.equal(describeDownloadFailure({ downloadId: 1, message: "" }), "");
});

test("the three result facts are kept apart, not collapsed into one word", () => {
  const facts = resultFacts({
    status: "COMPLETE",
    response_status: "PARTIAL",
    manifest_verified: true,
  });

  assert.equal(facts.length, 3);
  const [delivery, work, manifest] = facts;
  // An intact delivery of declared-partial work: the trap the operator has
  // already fallen into once. Delivery must not look bad, work must not look
  // done.
  assert.equal(delivery.tone, "ok");
  assert.equal(work.value, "PARTIAL");
  assert.equal(work.tone, "wait");
  assert.match(work.detail, /do not repair/);
  assert.equal(manifest.value, "verified");
});

test("an unusable manifest warns without condemning the delivery", () => {
  const [delivery, , manifest] = resultFacts({
    status: "COMPLETE",
    response_status: "COMPLETE",
    manifest_verified: false,
  });

  assert.equal(delivery.tone, "ok");
  assert.equal(manifest.value, "unusable");
  assert.equal(manifest.tone, "wait");
  assert.match(manifest.detail, /before trusting/);
});

test("an incomplete delivery is the fact that goes red", () => {
  const [delivery, work] = resultFacts({
    status: "INCOMPLETE",
    response_status: "COMPLETE",
    manifest_verified: true,
  });

  assert.equal(delivery.tone, "bad");
  assert.equal(work.tone, "ok");
});

test("a report from before the response_status field renders honestly", () => {
  const [delivery, work] = resultFacts({ status: "COMPLETE" });

  assert.equal(delivery.value, "COMPLETE");
  assert.equal(work.value, "unreported");
  assert.equal(work.tone, "neutral");
});

test("no report means no facts", () => {
  assert.deepEqual(resultFacts(null), []);
  assert.deepEqual(resultFacts(undefined), []);
});
