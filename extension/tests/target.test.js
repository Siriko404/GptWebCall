import assert from "node:assert/strict";
import test from "node:test";

import { chooseTargetTab } from "../lib/target.js";

const chatTab = { id: 7, url: "https://chatgpt.com/c/abc-123" };


test("the default opens a fresh conversation", () => {
  assert.deepEqual(chooseTargetTab({ mode: "new", activeTab: chatTab }), { create: true });
  // An absent or unrecognised mode must not silently bind a live tab.
  assert.deepEqual(chooseTargetTab({}), { create: true });
  assert.deepEqual(chooseTargetTab({ mode: "nonsense", activeTab: chatTab }), { create: true });
});


test("conductor mode binds the focused ChatGPT conversation", () => {
  assert.deepEqual(
    chooseTargetTab({ mode: "current", activeTab: chatTab }),
    { create: false, tabId: 7 },
  );
});


/* The whole point of the guard: arming the debugger on a tab we cannot prove is
 * ChatGPT would attach it to an unrelated site and then hand that site files. */
test("a tab that cannot be proven to be ChatGPT is refused, never fallen back on", () => {
  for (const activeTab of [
    { id: 7, url: "https://example.com/" },
    { id: 7 }, // no host permission for this site, so Chrome withholds the URL
    { id: 7, url: "https://chatgpt.com.evil.test/c/1" },
    { id: 7, url: "http://chatgpt.com/" }, // downgraded scheme
    null,
    { url: "https://chatgpt.com/" }, // no usable tab id
  ]) {
    assert.throws(
      () => chooseTargetTab({ mode: "current", activeTab }),
      /not a ChatGPT conversation|No active tab/,
    );
  }
});


test("a conversation already running a call is not reused", () => {
  assert.throws(
    () => chooseTargetTab({
      mode: "current",
      activeTab: chatTab,
      handoffs: { "ex-1": { tabId: 7, exchangeId: "ex-1" } },
    }),
    /already running call ex-1/,
  );
});


test("a call running in a different tab does not block this one", () => {
  assert.deepEqual(
    chooseTargetTab({
      mode: "current",
      activeTab: chatTab,
      handoffs: { "ex-1": { tabId: 99, exchangeId: "ex-1" } },
    }),
    { create: false, tabId: 7 },
  );
});
