import {
  attachmentBasenames,
  buildFallbackAssignment,
  buildFileAssignment,
} from "./lib/attachment.js";
import {
  anyCompletedTrackedDownload,
  anyShouldObserveDownload,
  claimCompletedDownload,
  handoffForTab,
} from "./lib/downloads.js";
import { CHATGPT_URL, chooseTargetTab } from "./lib/target.js";


const NATIVE_HOST = "com.sina.gptwebcall";


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
    await setHandoffStatus(source.tabId, "ERROR", error.message);
    await safeDetach(source.tabId);
  });
});


chrome.downloads.onCreated.addListener((downloadItem) => {
  observeCreatedDownload(downloadItem).catch((error) => recordDownloadFailure(downloadItem?.id, error));
});


chrome.downloads.onChanged.addListener((delta) => {
  submitCompletedDownload(delta).catch((error) => recordDownloadFailure(delta?.id, error));
});


async function handlePanelMessage(message) {
  switch (message?.type) {
    case "GET_STATUS":
      return getStatus();
    case "GO":
      return beginGo(message.exchangeId, message.mode);
    case "RESUME":
      return resumeCall(message.exchangeId, message.mode);
    case "STOP":
      return stopCall(message.exchangeId);
    case "DONE":
      return finishCall(message.exchangeId);
    case "REPAIR":
      return openRepairRound(message.exchangeId);
    default:
      throw new Error(`Unknown extension command: ${message?.type}`);
  }
}


async function readHandoffs() {
  const stored = await chrome.storage.session.get("handoffs");
  return stored.handoffs ?? {};
}


async function writeHandoff(handoff) {
  const handoffs = await readHandoffs();
  handoffs[handoff.exchangeId] = handoff;
  await chrome.storage.session.set({ handoffs });
  return handoff;
}


async function dropHandoff(exchangeId) {
  const handoffs = await readHandoffs();
  const removed = handoffs[exchangeId] ?? null;
  delete handoffs[exchangeId];
  await chrome.storage.session.set({ handoffs });
  return removed;
}


async function getStatus() {
  const [health, ready, active, progress, recent, stored] = await Promise.all([
    nativeCommand("health"),
    nativeCommand("calls.list_ready"),
    nativeCommand("calls.active"),
    nativeCommand("calls.progress"),
    nativeCommand("calls.recent"),
    chrome.storage.session.get(["handoffs", "lastReport", "lastHandoff", "lastDownloadFailure"]),
  ]);
  const handoffs = stored.handoffs ?? {};
  return {
    root: health?.root ?? null,
    // Which expected files have actually landed, per running call. The panel
    // holds Done back until they all have, because Done stops monitoring.
    progress,
    recent,
    ready,
    // An empty array is truthy, so returning [] here disables Go in any caller
    // that tests `if (state.active)`. Absence must be falsy.
    active: Array.isArray(active) && active.length === 0 ? null : active,
    handoffs: Object.values(handoffs),
    lastReport: stored.lastReport ?? null,
    lastDownloadFailure: stored.lastDownloadFailure ?? null,
    canRepair: Boolean(
      stored.lastReport?.status === "INCOMPLETE"
      && Number.isInteger(stored.lastHandoff?.tabId),
    ),
    repairExchangeId: stored.lastHandoff?.exchangeId ?? null,
  };
}


/* Which conversation the call lands in.
 *
 * "new" starts a fresh ChatGPT conversation — the bounded, self-contained call
 * the protocol is built around. "current" binds the conversation already open in
 * the focused tab, so a call can be delivered into a long-running thread that
 * has accumulated context on purpose. The two are different products: a call
 * sent into an existing thread is answered by a model that has already been
 * argued with, which is the point in conductor mode and a contaminant otherwise.
 *
 * The companion does not care. It takes tab_id as an opaque integer and
 * call.repair already hands it a tab that has been in use, so this is entirely a
 * question of which tab id we resolve here.
 */
async function resolveTargetTab(mode) {
  const [activeTab] = mode === "current"
    ? await chrome.tabs.query({ active: true, lastFocusedWindow: true })
    : [null];
  const choice = chooseTargetTab({
    mode,
    activeTab,
    handoffs: mode === "current" ? await readHandoffs() : {},
  });
  if (!choice.create) {
    return { id: choice.tabId };
  }
  const created = await chrome.tabs.create({ url: CHATGPT_URL, active: true });
  if (!Number.isInteger(created.id)) {
    throw new Error("Chrome did not create a usable ChatGPT tab");
  }
  return created;
}


async function beginGo(exchangeId, mode) {
  if (typeof exchangeId !== "string" || !exchangeId) {
    throw new Error("Select a prepared call first");
  }
  await chrome.storage.session.set({ lastDownloadFailure: null });
  const tab = await resolveTargetTab(mode);
  const existingDownloads = await chrome.downloads.search({});
  let started = false;
  try {
    const result = await nativeCommand("call.go", {
      exchange_id: exchangeId,
      tab_id: tab.id,
      download_baseline: existingDownloads.map((item) => item.id),
    });
    started = true;
    const handoff = handoffFrom(
      result,
      tab.id,
      exchangeId,
      mode === "current"
        ? "Delivering into the open conversation. Click Attach files there."
        : "Click Attach files in ChatGPT.",
    );
    await writeHandoff(handoff);
    await armTab(tab.id);
    return handoff;
  } catch (error) {
    await dropHandoff(exchangeId);
    await safeDetach(tab.id);
    if (started) {
      await nativeCommand("call.stop", { exchange_id: exchangeId }).catch(() => undefined);
    }
    throw error;
  }
}


/* Resume re-arms a call whose handoff was lost — the panel offers it when the
 * companion still reports an active call and session storage holds no handoff,
 * which is what a browser restart leaves behind. That restart also destroys the
 * only record of which conversation the call was delivered into, so the
 * destination has to be resolved again rather than assumed: resuming a
 * conductor call into a fresh tab would silently discard the thread the mode
 * exists to keep.
 */
async function resumeCall(exchangeId, mode) {
  const tab = await resolveTargetTab(mode);
  const existingDownloads = await chrome.downloads.search({});
  const payload = {
    tab_id: tab.id,
    download_baseline: existingDownloads.map((item) => item.id),
  };
  if (typeof exchangeId === "string" && exchangeId) {
    payload.exchange_id = exchangeId;
  }
  try {
    const result = await nativeCommand("call.resume", payload);
    const handoff = handoffFrom(
      result,
      tab.id,
      result.active.exchange_id,
      mode === "current"
        ? "Resumed into the open conversation. Click Attach files there."
        : "Resumed. Click Attach files in ChatGPT.",
    );
    await writeHandoff(handoff);
    await armTab(tab.id);
    return handoff;
  } catch (error) {
    await safeDetach(tab.id);
    throw error;
  }
}


function handoffFrom(result, tabId, exchangeId, message) {
  return {
    armed: true,
    tabId,
    exchangeId,
    subject: result.active.request_id,
    requestPaths: result.request_paths,
    attachmentNames: attachmentBasenames(result.request_paths),
    status: "WAITING_FOR_ATTACH_CLICK",
    message,
    monitoring: true,
    monitoringStartedAt: result.active.started_at,
    downloadBaseline: result.active.download_baseline,
    observedDownloadIds: result.active.observed_download_ids,
  };
}


async function armTab(tabId) {
  await chrome.debugger.attach({ tabId }, "1.3");
  await chrome.debugger.sendCommand(
    { tabId },
    "Page.enable",
    { enableFileChooserOpenedEvent: true },
  );
  await chrome.debugger.sendCommand(
    { tabId },
    "Page.setInterceptFileChooserDialog",
    { enabled: true },
  );
}


async function completeAttachment(source, params) {
  const handoffs = await readHandoffs();
  const handoff = handoffForTab(handoffs, source.tabId);
  let assignment;
  try {
    assignment = buildFileAssignment(handoff, source, params);
  } catch (error) {
    if (!error.message.includes("backendNodeId")) {
      throw error;
    }
    // ChatGPT's chooser no longer names its input node; find it ourselves.
    const nodeId = await findFileInputNode(source);
    assignment = buildFallbackAssignment(handoff, source, nodeId);
  }
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
  await writeHandoff(updated);
  await broadcastStatus(updated);
}


/* Fallback for a chooser event with no backendNodeId: the composer's hidden
 * <input type=file> is still on the page, so locate it by query. When several
 * exist, the last is the one ChatGPT's current composer wired most recently.
 */
async function findFileInputNode(source) {
  await chrome.debugger.sendCommand(source, "DOM.enable", {});
  const { root } = await chrome.debugger.sendCommand(source, "DOM.getDocument", {});
  const { nodeIds } = await chrome.debugger.sendCommand(
    source,
    "DOM.querySelectorAll",
    { nodeId: root.nodeId, selector: "input[type=file]" },
  );
  if (!Array.isArray(nodeIds) || nodeIds.length === 0) {
    throw new Error("no <input type=file> found on the ChatGPT page");
  }
  return nodeIds.at(-1);
}


async function openRepairRound(exchangeId) {
  const stored = await chrome.storage.session.get(["handoffs", "lastHandoff"]);
  const handoffs = stored.handoffs ?? {};
  const handoff = (exchangeId ? handoffs[exchangeId] : null)
    ?? stored.lastHandoff
    ?? null;
  const tabId = handoff?.tabId;
  const target = exchangeId ?? handoff?.exchangeId;
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
    tabId,
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
  await writeHandoff(updated);
  await chrome.storage.session.set({ lastReport: null });
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


async function stopCall(exchangeId) {
  const handoffs = await readHandoffs();
  const handoff = exchangeId ? handoffs[exchangeId] : Object.values(handoffs)[0];
  if (Number.isInteger(handoff?.tabId)) {
    await safeDetach(handoff.tabId);
  }
  const payload = exchangeId ? { exchange_id: exchangeId } : {};
  const result = await nativeCommand("call.stop", payload);
  await dropHandoff(exchangeId ?? handoff?.exchangeId);
  return result;
}


async function finishCall(exchangeId) {
  const handoffs = await readHandoffs();
  const handoff = exchangeId ? handoffs[exchangeId] : Object.values(handoffs)[0];
  const target = exchangeId ?? handoff?.exchangeId;
  if (handoff) {
    await writeHandoff({ ...handoff, monitoring: false });
  }
  const payload = target ? { exchange_id: target } : {};
  const report = await nativeCommand("call.done", payload);
  // Keep the tab binding so a correction round can reuse the same conversation.
  const lastHandoff = handoff
    ? { tabId: handoff.tabId, exchangeId: handoff.exchangeId }
    : null;
  await chrome.storage.session.set({ lastReport: report, lastHandoff });
  await dropHandoff(target);
  await resetTrackerWhenIdle();
  return report;
}


async function resetTrackerWhenIdle() {
  const handoffs = await readHandoffs();
  if (Object.keys(handoffs).length === 0) {
    await chrome.storage.session.set({ downloadTracker: { ids: [], processing: [] } });
  }
}


async function observeCreatedDownload(downloadItem) {
  const stored = await chrome.storage.session.get(["handoffs", "downloadTracker"]);
  const tracker = stored.downloadTracker ?? { ids: [], processing: [] };
  if (
    !anyShouldObserveDownload(stored.handoffs ?? {}, downloadItem)
    || tracker.ids.includes(downloadItem.id)
  ) {
    return;
  }
  tracker.ids.push(downloadItem.id);
  await chrome.storage.session.set({ downloadTracker: tracker });
}


async function submitCompletedDownload(delta) {
  const stored = await chrome.storage.session.get(["handoffs", "downloadTracker"]);
  const handoffs = stored.handoffs ?? {};
  const tracker = stored.downloadTracker ?? { ids: [], processing: [] };
  if (!anyCompletedTrackedDownload(handoffs, tracker.ids, delta)) {
    return;
  }
  if (!claimCompletedDownload(tracker, delta.id)) {
    return;
  }
  await chrome.storage.session.set({ downloadTracker: tracker });

  const matches = await chrome.downloads.search({ id: delta.id });
  const item = matches[0];
  if (!item || item.state !== "complete" || !item.filename) {
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
  const owner = result.exchange_id ? handoffs[result.exchange_id] : null;
  if (!owner) {
    return;
  }
  const updated = {
    ...owner,
    observedDownloadIds: [...new Set([...(owner.observedDownloadIds ?? []), item.id])],
    status: `DOWNLOAD_${result.status}`,
    message: downloadMessage(result),
  };
  await writeHandoff(updated);
  await broadcastStatus(updated);
}


/* A download that fails to file itself is the one failure nobody can see. The
 * file sits in the downloads folder, the panel shows nothing, and validation
 * later reports it missing with no hint that anything went wrong. These
 * listeners used to discard the error entirely.
 *
 * It is recorded, not retried. A retry could file an ambiguous filename into the
 * wrong exchange, and filename is the only thing attribution has to go on.
 */
async function recordDownloadFailure(downloadId, error) {
  try {
    await chrome.storage.session.set({
      lastDownloadFailure: {
        downloadId: Number.isInteger(downloadId) ? downloadId : null,
        message: error?.message ?? String(error),
        at: new Date().toISOString(),
      },
    });
    await broadcastStatus(null);
  } catch (_ignored) {
    // Session storage is the last place left to report to.
  }
}


async function setHandoffStatus(tabId, status, message) {
  const handoffs = await readHandoffs();
  const handoff = handoffForTab(handoffs, tabId);
  if (!handoff) {
    return;
  }
  const updated = { ...handoff, status, message, armed: false };
  await writeHandoff(updated);
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
    case "AMBIGUOUS":
    case "INVALID":
    case "CONFLICT":
      return result.error ?? "Download was not collected.";
    default:
      return `Download status: ${result.status}.`;
  }
}
