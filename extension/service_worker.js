import {
  attachmentBasenames,
  buildFileAssignment,
} from "./lib/attachment.js";
import {
  claimCompletedDownload,
  completedTrackedDownload,
  shouldObserveDownload,
} from "./lib/downloads.js";


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


chrome.downloads.onCreated.addListener((downloadItem) => {
  observeCreatedDownload(downloadItem).catch((error) => {
    setHandoffStatus("ERROR", error.message).catch(() => undefined);
  });
});


chrome.downloads.onChanged.addListener((delta) => {
  submitCompletedDownload(delta).catch((error) => {
    setHandoffStatus("ERROR", error.message).catch(() => undefined);
  });
});


async function handlePanelMessage(message) {
  switch (message?.type) {
    case "GET_STATUS":
      return getStatus();
    case "GO":
      return beginGo(message.exchangeId);
    case "RESUME":
      return resumeActiveCall();
    case "STOP":
      return stopActiveCall();
    case "DONE":
      return finishActiveCall();
    case "REPAIR":
      return openRepairRound(message.exchangeId);
    default:
      throw new Error(`Unknown extension command: ${message?.type}`);
  }
}


async function getStatus() {
  const [ready, active, stored] = await Promise.all([
    nativeCommand("calls.list_ready"),
    nativeCommand("call.active"),
    chrome.storage.session.get(["handoff", "lastReport", "lastHandoff"]),
  ]);
  return {
    ready,
    active,
    handoff: stored.handoff ?? null,
    lastReport: stored.lastReport ?? null,
    canRepair: Boolean(
      stored.lastReport?.status === "INCOMPLETE"
      && Number.isInteger((stored.handoff ?? stored.lastHandoff)?.tabId),
    ),
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
      monitoring: true,
      monitoringStartedAt: result.active.started_at,
      downloadBaseline: result.active.download_baseline,
      observedDownloadIds: result.active.observed_download_ids,
    };
    await chrome.storage.session.set({
      handoff,
      downloadTracker: { ids: [], processing: [] },
      lastReport: null,
    });
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


async function resumeActiveCall() {
  const tab = await chrome.tabs.create({ url: CHATGPT_URL, active: true });
  if (!Number.isInteger(tab.id)) {
    throw new Error("Chrome did not create a usable ChatGPT tab");
  }
  const existingDownloads = await chrome.downloads.search({});
  try {
    const result = await nativeCommand("call.resume", {
      tab_id: tab.id,
      download_baseline: existingDownloads.map((item) => item.id),
    });
    const handoff = {
      armed: true,
      tabId: tab.id,
      exchangeId: result.active.exchange_id,
      requestPaths: result.request_paths,
      attachmentNames: attachmentBasenames(result.request_paths),
      status: "WAITING_FOR_ATTACH_CLICK",
      message: "Resumed. Click Attach files in ChatGPT.",
      monitoring: true,
      monitoringStartedAt: result.active.started_at,
      downloadBaseline: result.active.download_baseline,
      observedDownloadIds: result.active.observed_download_ids,
    };
    await chrome.storage.session.set({
      handoff,
      downloadTracker: { ids: [], processing: [] },
    });
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
    await chrome.storage.session.remove(["handoff", "downloadTracker"]);
    await safeDetach(tab.id);
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


async function openRepairRound(exchangeId) {
  const stored = await chrome.storage.session.get(["handoff", "lastHandoff"]);
  const handoff = stored.handoff ?? stored.lastHandoff ?? {};
  const tabId = handoff.tabId;
  const target = exchangeId ?? handoff.exchangeId;
  if (!Number.isInteger(tabId)) {
    throw new Error("No bound ChatGPT tab. Use Resume attachment first.");
  }
  if (typeof target !== "string" || !target) {
    throw new Error("No exchange to repair");
  }
  const existingDownloads = await chrome.downloads.search({});
  const result = await nativeCommand("call.repair", {
    exchange_id: target,
    tab_id: tabId,
    download_baseline: existingDownloads.map((item) => item.id),
  });

  let inserted = false;
  let insertError = "";
  try {
    inserted = await insertPromptIntoComposer(tabId, result.prompt);
  } catch (error) {
    insertError = error.message;
  }

  const updated = {
    ...handoff,
    exchangeId: result.exchange_id,
    armed: false,
    monitoring: true,
    monitoringStartedAt: result.active.started_at,
    downloadBaseline: result.active.download_baseline,
    observedDownloadIds: [],
    repairRound: result.round,
    repairPrompt: result.prompt,
    repairPromptPath: result.prompt_path,
    status: inserted ? "REPAIR_PROMPT_INSERTED" : "REPAIR_PROMPT_READY",
    message: inserted
      ? `Correction round ${result.round} typed into ChatGPT. Review it, then click Send.`
      : `Correction round ${result.round} ready. Copy the prompt below into ChatGPT, then click Send.`
        + (insertError ? ` (${insertError})` : ""),
  };
  await chrome.storage.session.set({
    handoff: updated,
    downloadTracker: { ids: [], processing: [] },
    lastReport: null,
  });
  await broadcastStatus(updated);
  return updated;
}


async function insertPromptIntoComposer(tabId, text) {
  await chrome.debugger.attach({ tabId }, "1.3");
  try {
    await chrome.debugger.sendCommand({ tabId }, "Runtime.enable", {});
    const focused = await chrome.debugger.sendCommand(
      { tabId },
      "Runtime.evaluate",
      {
        expression: `(() => {
          const composer = document.querySelector("#prompt-textarea")
            ?? document.querySelector("div[contenteditable='true']")
            ?? document.querySelector("textarea");
          if (!composer) { return false; }
          composer.focus();
          return true;
        })()`,
        returnByValue: true,
      },
    );
    if (focused?.result?.value !== true) {
      throw new Error("the ChatGPT composer was not found on the bound tab");
    }
    await chrome.debugger.sendCommand({ tabId }, "Input.insertText", { text });
    return true;
  } finally {
    await safeDetach(tabId);
  }
}


async function stopActiveCall() {
  const stored = await chrome.storage.session.get("handoff");
  if (Number.isInteger(stored.handoff?.tabId)) {
    await safeDetach(stored.handoff.tabId);
  }
  const result = await nativeCommand("call.stop");
  await chrome.storage.session.remove(["handoff", "downloadTracker"]);
  return result;
}


async function observeCreatedDownload(downloadItem) {
  const stored = await chrome.storage.session.get(["handoff", "downloadTracker"]);
  const handoff = stored.handoff;
  const tracker = stored.downloadTracker ?? { ids: [], processing: [] };
  if (!shouldObserveDownload(handoff, downloadItem) || tracker.ids.includes(downloadItem.id)) {
    return;
  }
  tracker.ids.push(downloadItem.id);
  await chrome.storage.session.set({ downloadTracker: tracker });
}


async function submitCompletedDownload(delta) {
  const stored = await chrome.storage.session.get(["handoff", "downloadTracker"]);
  const handoff = stored.handoff;
  const tracker = stored.downloadTracker ?? { ids: [], processing: [] };
  if (!completedTrackedDownload(handoff, tracker.ids, delta)) {
    return;
  }
  if (!claimCompletedDownload(tracker, delta.id)) {
    return;
  }
  await chrome.storage.session.set({ downloadTracker: tracker });

  const matches = await chrome.downloads.search({ id: delta.id });
  const item = matches[0];
  if (!item || item.state !== "complete" || !item.filename) {
    await setHandoffStatus("ERROR", `Completed download ${delta.id} has no local file.`);
    return;
  }
  const result = await nativeCommand("download.completed", {
    id: item.id,
    filename: item.filename,
    state: "complete",
    url: item.url,
    finalUrl: item.finalUrl,
    mime: item.mime,
    startTime: item.startTime,
    endTime: item.endTime,
  });
  const updated = {
    ...handoff,
    observedDownloadIds: [...new Set([...(handoff.observedDownloadIds ?? []), item.id])],
    status: `DOWNLOAD_${result.status}`,
    message: downloadMessage(result),
  };
  await chrome.storage.session.set({ handoff: updated, downloadTracker: tracker });
  await broadcastStatus(updated);
}


async function finishActiveCall() {
  const stored = await chrome.storage.session.get(["handoff", "downloadTracker"]);
  if (stored.handoff) {
    const stopped = { ...stored.handoff, monitoring: false };
    await chrome.storage.session.set({
      handoff: stopped,
      downloadTracker: { ...(stored.downloadTracker ?? { ids: [], processing: [] }), ids: [] },
    });
  }
  const report = await nativeCommand("call.done");
  // Keep the tab binding so a correction round can reuse the same conversation.
  const lastHandoff = stored.handoff
    ? { tabId: stored.handoff.tabId, exchangeId: stored.handoff.exchangeId }
    : null;
  await chrome.storage.session.set({ lastReport: report, lastHandoff });
  await chrome.storage.session.remove(["handoff", "downloadTracker"]);
  return report;
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


function downloadMessage(result) {
  switch (result.status) {
    case "MOVED":
      return `${result.stored_name} moved to this call's response folder.`;
    case "PENDING":
      return "Download saved as a candidate; waiting for the main JSON to name it.";
    case "IGNORED":
      return "Download left untouched because it is not part of this call.";
    case "INVALID":
    case "CONFLICT":
      return result.error ?? "Download was not collected.";
    default:
      return `Download status: ${result.status}.`;
  }
}
