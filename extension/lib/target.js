/* Which tab a call is delivered into.
 *
 * Kept pure and out of the service worker so the refusals can be tested. The
 * refusals are the reason this exists: "send into the conversation I am in"
 * means arming the debugger and intercepting a file chooser on a tab the
 * operator was already using, and doing that to the wrong tab would attach a
 * debugger to an unrelated site and hand it files.
 */

export const CHATGPT_URL = "https://chatgpt.com/";

/* Returns {create: false, tabId} to bind a conversation already open,
 * {create: false, tabId, navigate: true} to turn an open ChatGPT tab into a
 * fresh conversation, or {create: true} when there is no ChatGPT tab to use.
 * Throws with an operator-facing message when the focused tab cannot safely be
 * used.
 */
export function chooseTargetTab({
  mode,
  activeTab,
  handoffs = {},
  chatgptTabs = [],
} = {}) {
  if (mode !== "current") {
    return freshConversation(activeTab, chatgptTabs, handoffs);
  }
  if (!activeTab || !Number.isInteger(activeTab.id)) {
    throw new Error("No active tab to send into. Focus your ChatGPT conversation.");
  }
  /* The extension holds a host permission for chatgpt.com alone, so `url` is
   * populated for ChatGPT tabs and undefined everywhere else. An unreadable URL
   * is therefore a refusal and never a fallback — a missing URL is exactly the
   * case where we cannot prove the tab is safe to arm. */
  if (typeof activeTab.url !== "string" || !activeTab.url.startsWith(CHATGPT_URL)) {
    /* A withheld URL and a genuinely wrong site are indistinguishable from
     * here, and the operator staring straight at a ChatGPT tab needs the second
     * cause named or the message reads as a lie. */
    throw new Error(
      "The focused tab is not a ChatGPT conversation. Open the conversation you "
      + "want this call delivered into, focus it, then click Go. If it already "
      + "is one, Chrome is withholding the tab's address because the extension's "
      + "chatgpt.com permission was declined — reload the extension and accept "
      + "the prompt.",
    );
  }
  const bound = boundCall(handoffs, activeTab.id);
  if (bound) {
    throw new Error(`That conversation is already running call ${bound.exchangeId}.`);
  }
  return { create: false, tabId: activeTab.id };
}


/* A fresh conversation in a tab that already exists, rather than a new tab.
 *
 * Every call used to open one. Twenty calls meant twenty ChatGPT tabs, and
 * closing them was the operator's problem. A conversation is a page, not a
 * window: navigating an open ChatGPT tab to the root gives a new conversation
 * and leaves the old thread where it always was, in the sidebar.
 *
 * The focused tab is preferred when it is ChatGPT, because that is the window
 * the operator is looking at and where they will expect the call to appear. A
 * tab running a call is never taken - its download attribution and its armed
 * debugger both belong to that call. When nothing is usable, a tab is created,
 * which is also what happens when no ChatGPT tab is open at all.
 */
function freshConversation(activeTab, chatgptTabs, handoffs) {
  const usable = (tab) =>
    tab
    && Number.isInteger(tab.id)
    && typeof tab.url === "string"
    && tab.url.startsWith(CHATGPT_URL)
    && !boundCall(handoffs, tab.id);

  const chosen = usable(activeTab)
    ? activeTab
    : chatgptTabs.find(usable);
  return chosen
    ? { create: false, tabId: chosen.id, navigate: true }
    : { create: true };
}


function boundCall(handoffs, tabId) {
  return Object.values(handoffs).find((item) => item?.tabId === tabId);
}
