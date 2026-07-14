import assert from "node:assert/strict";
import test from "node:test";

import {
  attachmentBasenames,
  buildFileAssignment,
} from "../lib/attachment.js";


const handoff = {
  armed: true,
  tabId: 42,
  requestPaths: [
    "C:\\calls\\request\\PROMPT_2026-07-14_151500.txt",
    "C:\\calls\\request\\WEB_REVIEW_REQUEST.json",
  ],
};


test("builds a file assignment only for the bound tab and chooser node", () => {
  const result = buildFileAssignment(
    handoff,
    { tabId: 42 },
    { backendNodeId: 87 },
  );

  assert.deepEqual(result, {
    method: "DOM.setFileInputFiles",
    params: {
      files: handoff.requestPaths,
      backendNodeId: 87,
    },
  });
});


test("rejects chooser events from another tab", () => {
  assert.throws(
    () => buildFileAssignment(handoff, { tabId: 99 }, { backendNodeId: 87 }),
    /bound tab/,
  );
});


test("rejects unarmed handoffs", () => {
  assert.throws(
    () => buildFileAssignment({ ...handoff, armed: false }, { tabId: 42 }, { backendNodeId: 87 }),
    /not armed/,
  );
});


test("rejects a chooser without a backend node", () => {
  assert.throws(
    () => buildFileAssignment(handoff, { tabId: 42 }, {}),
    /backendNodeId/,
  );
});


test("rejects empty or non-absolute Windows request paths", () => {
  assert.throws(
    () => buildFileAssignment({ ...handoff, requestPaths: [] }, { tabId: 42 }, { backendNodeId: 1 }),
    /request paths/,
  );
  assert.throws(
    () => buildFileAssignment({ ...handoff, requestPaths: ["relative.txt"] }, { tabId: 42 }, { backendNodeId: 1 }),
    /absolute Windows/,
  );
});


test("returns only attachment basenames for UI disclosure", () => {
  assert.deepEqual(attachmentBasenames(handoff.requestPaths), [
    "PROMPT_2026-07-14_151500.txt",
    "WEB_REVIEW_REQUEST.json",
  ]);
});
