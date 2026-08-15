import assert from "node:assert/strict";
import test from "node:test";

import { chooseTargetTab } from "../lib/target.js";

const chatTab = { id: 7, url: "https://chatgpt.com/c/abc-123" };


/* This used to assert {create: true} unconditionally — every call opened a tab,
 * so twenty calls left twenty ChatGPT tabs behind. A conversation is a page, not
 * a window: a tab is created only when there is no ChatGPT tab to reuse. */
test("a fresh conversation opens a tab only when there is none to reuse", () => {
  assert.deepEqual(chooseTargetTab({ mode: "new" }), { create: true });
  // An absent or unrecognised mode must not silently bind a live tab, and must
  // not navigate one either.
  assert.deepEqual(chooseTargetTab({}), { create: true });
  assert.deepEqual(chooseTargetTab({ mode: "nonsense" }), { create: true });
});


test("a fresh conversation reuses an open ChatGPT tab", () => {
  assert.deepEqual(
    chooseTargetTab({ mode: "new", chatgptTabs: [chatTab] }),
    { create: false, tabId: 7, navigate: true },
  );
});


/* The window the operator is looking at is where they will expect the call to
 * appear, so the focused tab wins over one buried in another window. */
test("a fresh conversation prefers the focused ChatGPT tab", () => {
  assert.deepEqual(
    chooseTargetTab({
      mode: "new",
      activeTab: chatTab,
      chatgptTabs: [{ id: 3, url: "https://chatgpt.com/" }, chatTab],
    }),
    { create: false, tabId: 7, navigate: true },
  );
});


/* Same rule as conductor mode, different consequence: taking a tab that is
 * running a call would navigate its conversation away mid-delivery. */
test("a fresh conversation never takes a tab running a call", () => {
  const handoffs = { "ex-1": { tabId: 7, exchangeId: "ex-1" } };

  assert.deepEqual(
    chooseTargetTab({ mode: "new", activeTab: chatTab, chatgptTabs: [chatTab], handoffs }),
    { create: true },
  );
  assert.deepEqual(
    chooseTargetTab({
      mode: "new",
      activeTab: chatTab,
      chatgptTabs: [chatTab, { id: 8, url: "https://chatgpt.com/" }],
      handoffs,
    }),
    { create: false, tabId: 8, navigate: true },
  );
});


/* The focused tab is usually not ChatGPT at all — the operator is in their
 * editor. That is a reason to look further, not a reason to refuse. */
test("a fresh conversation ignores a focused tab that is not ChatGPT", () => {
  assert.deepEqual(
    chooseTargetTab({
      mode: "new",
      activeTab: { id: 4, url: "https://example.com/" },
      chatgptTabs: [chatTab],
    }),
    { create: false, tabId: 7, navigate: true },
  );
  // And a lookalike host is not ChatGPT, in this direction too.
  assert.deepEqual(
    chooseTargetTab({
      mode: "new",
      chatgptTabs: [{ id: 9, url: "https://chatgpt.com.evil.test/c/1" }],
    }),
    { create: true },
  );
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
