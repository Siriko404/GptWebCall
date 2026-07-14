import {
  attachmentBasenames,
  buildFileAssignment,
} from "./lib/attachment.js";


const NATIVE_HOST = "com.sina.gptwebcall";
const CHATGPT_URL = "https://chatgpt.com/";


chrome.runtime.onInstalled.addListener(() => {
  chrome.sidePanel.setPanelBehavior({ openPanelOnActionClick: true });
});


chrome.runtime.onStartup.addListener(() => {
  chrome.sidePanel.setPanelBehavior({ openPanelOnActionClick: true });
});


chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  handlePanelMessage(message)
    .then((result) => sendResponse({ ok: true, result }))
    .catch((error) => sendResponse({ ok: false, error: error.message }));
  return true;
});


chrome.debugger.onEvent.addListener((source, method, params) => {
  if (method !== "Page.fileChooserOpened") {
    return;
  }
  completeAttachment(source, params).catch(async (error) => {
    await setHandoffStatus("ERROR", error.message);
    await safeDetach(source.tabId);
  });
});


async function handlePanelMessage(message) {
  switch (message?.type) {
    case "GET_STATUS":
      return getStatus();
    case "GO":
      return beginGo(message.exchangeId);
    case "STOP":
      return stopActiveCall();
    default:
      throw new Error(`Unknown extension command: ${message?.type}`);
  }
}


async function getStatus() {
  const [ready, active, stored] = await Promise.all([
    nativeCommand("calls.list_ready"),
    nativeCommand("call.active"),
    chrome.storage.session.get("handoff"),
  ]);
  return {
    ready,
    active,
    handoff: stored.handoff ?? null,
  };
}


async function beginGo(exchangeId) {
  if (typeof exchangeId !== "string" || !exchangeId) {
    throw new Error("Select a prepared call first");
  }
  const tab = await chrome.tabs.create({ url: CHATGPT_URL, active: true });
  if (!Number.isInteger(tab.id)) {
    throw new Error("Chrome did not create a usable ChatGPT tab");
  }
  const existingDownloads = await chrome.downloads.search({});
  let started = false;
  try {
    const result = await nativeCommand("call.go", {
      exchange_id: exchangeId,
      tab_id: tab.id,
      download_baseline: existingDownloads.map((item) => item.id),
    });
    started = true;
    const handoff = {
      armed: true,
      tabId: tab.id,
      exchangeId,
      requestPaths: result.request_paths,
      attachmentNames: attachmentBasenames(result.request_paths),
      status: "WAITING_FOR_ATTACH_CLICK",
      message: "Click Attach files in ChatGPT.",
    };
    await chrome.storage.session.set({ handoff });
    await chrome.debugger.attach({ tabId: tab.id }, "1.3");
    await chrome.debugger.sendCommand(
      { tabId: tab.id },
      "Page.enable",
      { enableFileChooserOpenedEvent: true },
    );
    await chrome.debugger.sendCommand(
      { tabId: tab.id },
      "Page.setInterceptFileChooserDialog",
      { enabled: true },
    );
    return handoff;
  } catch (error) {
    await chrome.storage.session.remove("handoff");
    await safeDetach(tab.id);
    if (started) {
      await nativeCommand("call.stop").catch(() => undefined);
    }
    throw error;
  }
}


async function completeAttachment(source, params) {
  const stored = await chrome.storage.session.get("handoff");
  const handoff = stored.handoff;
  const assignment = buildFileAssignment(handoff, source, params);
  await chrome.debugger.sendCommand(source, assignment.method, assignment.params);
  await chrome.debugger.sendCommand(
    { tabId: source.tabId },
    "Page.setInterceptFileChooserDialog",
    { enabled: false },
  );
  await safeDetach(source.tabId);
  const updated = {
    ...handoff,
    armed: false,
    status: "ATTACHED",
    message: `${handoff.attachmentNames.length} files attached. Review them, then click Send.`,
  };
  await chrome.storage.session.set({ handoff: updated });
  await broadcastStatus(updated);
}


async function stopActiveCall() {
  const stored = await chrome.storage.session.get("handoff");
  if (Number.isInteger(stored.handoff?.tabId)) {
    await safeDetach(stored.handoff.tabId);
  }
  const result = await nativeCommand("call.stop");
  await chrome.storage.session.remove("handoff");
  return result;
}


async function setHandoffStatus(status, message) {
  const stored = await chrome.storage.session.get("handoff");
  if (!stored.handoff) {
    return;
  }
  const updated = { ...stored.handoff, status, message, armed: false };
  await chrome.storage.session.set({ handoff: updated });
  await broadcastStatus(updated);
}


async function safeDetach(tabId) {
  if (!Number.isInteger(tabId)) {
    return;
  }
  try {
    await chrome.debugger.detach({ tabId });
  } catch (_error) {
    // Detaching an already-detached target is harmless.
  }
}


async function nativeCommand(command, payload = {}) {
  const response = await chrome.runtime.sendNativeMessage(NATIVE_HOST, {
    protocol_version: 1,
    command,
    payload,
  });
  if (!response?.ok) {
    throw new Error(response?.error?.message ?? "Native companion failed");
  }
  return response.result;
}


async function broadcastStatus(handoff) {
  try {
    await chrome.runtime.sendMessage({ type: "HANDOFF_STATUS", handoff });
  } catch (_error) {
    // The side panel may be closed; session storage remains authoritative.
  }
}
