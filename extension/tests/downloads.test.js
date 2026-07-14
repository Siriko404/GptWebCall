import assert from "node:assert/strict";
import test from "node:test";

import {
  claimCompletedDownload,
  completedTrackedDownload,
  shouldObserveDownload,
} from "../lib/downloads.js";


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


test("submits a tracked download exactly when Chrome marks it complete", () => {
  const tracked = [4, 7];
  assert.equal(
    completedTrackedDownload(active, tracked, {
      id: 4,
      state: { current: "complete" },
    }),
    true,
  );
  assert.equal(
    completedTrackedDownload(active, tracked, {
      id: 4,
      state: { current: "interrupted" },
    }),
    false,
  );
  assert.equal(
    completedTrackedDownload(active, tracked, {
      id: 9,
      state: { current: "complete" },
    }),
    false,
  );
});


test("completion is disabled immediately after Done", () => {
  assert.equal(
    completedTrackedDownload(
      { ...active, monitoring: false },
      [4],
      { id: 4, state: { current: "complete" } },
    ),
    false,
  );
});


test("claims each completed download only once", () => {
  const tracker = { ids: [4], processing: [] };

  assert.equal(claimCompletedDownload(tracker, 4), true);
  assert.deepEqual(tracker, { ids: [4], processing: [4] });
  assert.equal(claimCompletedDownload(tracker, 4), false);
  assert.equal(claimCompletedDownload(tracker, 7), false);
});
