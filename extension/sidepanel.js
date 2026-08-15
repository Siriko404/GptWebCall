/* The panel is an attention stack. Whatever needs the operator's next click
 * sits on top: a running call while one runs, the ready queue while nothing
 * does, a recovery card when the browser forgot calls the companion still
 * remembers. Everything else keeps quiet.
 *
 * Two rules carried over intact from the first design, because they were the
 * two correct things about it: Done is held back until every expected file has
 * landed (Done stops monitoring, so anything still downloading at that moment
 * is lost), and no software here ever clicks Send.
 */

import {
  describeStage,
  formatBytes,
  formatElapsed,
  downloadGuard,
  describeDownloadFailure,
  resultFacts,
} from "./lib/panel.js";

const el = (id) => document.querySelector(`#${id}`);

const select = el("call-select");
const goMode = el("go-mode");
const goModeHint = el("go-mode-hint");
const callDetail = el("call-detail");
const readyCount = el("ready-count");
const goButton = el("go-button");
const launchCard = el("launch-card");
const launchToggle = el("launch-toggle");
const flightCard = el("flight-card");
const flight = el("flight");
const flightCount = el("flight-count");
const recoveryCard = el("recovery-card");
const recoveryCount = el("recovery-count");
const recoveryMode = el("recovery-mode");
const recoveryList = el("recovery-list");
const resultCard = el("result-card");
const resultRound = el("result-round");
const resultFactsBox = el("result-facts");
const resultBody = el("result-body");
const defectList = el("defect-list");
const repairButton = el("repair-button");
const repairCard = el("repair-card");
const repairPrompt = el("repair-prompt");
const copyRepairButton = el("copy-repair-button");
const historyCard = el("history-card");
const history = el("history");
const historyCount = el("history-count");
const health = el("health");
const companionLine = el("companion-line");
const errorLine = el("error");
const downloadFailure = el("download-failure");
const reloadButton = el("reload-button");

let repairTarget = null;
let forced = new Set();
let ticking = null;
/* Which archive row is open, and the operator's own say over the launch card:
 * the stack collapses Launch while a call runs, but a deliberate toggle wins
 * until the running/idle state actually changes. */
let openHistoryId = null;
let launchPinned = null;
let lastHadActive = null;

// Reloads the whole extension, the manual fix for a stale build that has
// stopped auto-capturing downloads. It also reloads this panel, so no refresh.
reloadButton.addEventListener("click", () => chrome.runtime.reload());

/* The destination survives a browser restart, because getting it wrong is
 * expensive in one direction: a call meant for a long-running thread that opens
 * a blank conversation loses the context the thread existed to accumulate. */
const GO_MODE_HINTS = {
  new: "Nothing it has been told before affects the answer.",
  current: "Whichever conversation is focused when you click Go.",
};

goMode.addEventListener("change", () => {
  chrome.storage.local.set({ goMode: goMode.value });
  renderGoMode();
});

function renderGoMode() {
  goModeHint.textContent = GO_MODE_HINTS[goMode.value] ?? "";
}

chrome.storage.local.get("goMode").then((stored) => {
  if (stored.goMode === "current" || stored.goMode === "new") {
    goMode.value = stored.goMode;
  }
  renderGoMode();
});

goButton.addEventListener("click", () =>
  run(async () => {
    const handoff = await send({
      type: "GO",
      exchangeId: select.value,
      mode: goMode.value,
    });
    showLaunchPrompt(handoff);
  }),
);

launchToggle.addEventListener("click", () => {
  launchPinned = launchCard.classList.contains("collapsed");
  launchCard.classList.toggle("collapsed", !launchPinned);
  launchToggle.textContent = launchPinned ? "Hide" : "Show";
});

repairButton.addEventListener("click", () =>
  run(async () => {
    const handoff = await send({ type: "REPAIR", exchangeId: repairTarget });
    showPromptToCopy(handoff?.repairPrompt);
  }),
);

copyRepairButton.addEventListener("click", async () => {
  try {
    await navigator.clipboard.writeText(repairPrompt.textContent);
    copyRepairButton.textContent = "Copied";
  } catch (_error) {
    copyRepairButton.textContent = "Copy failed";
  }
});

select.addEventListener("change", () => renderDetail(select.selectedOptions[0]?.call));

chrome.runtime.onMessage.addListener((message) => {
  if (message?.type === "HANDOFF_STATUS") {
    refresh();
  }
});

async function run(action) {
  setBusy(true);
  clearError();
  try {
    await action();
  } catch (error) {
    showError(error.message);
  } finally {
    setBusy(false);
    await refresh();
  }
}

async function refresh() {
  let state;
  try {
    state = await send({ type: "GET_STATUS" });
  } catch (error) {
    health.className = "dot down";
    companionLine.textContent = "Companion unavailable";
    showError(error.message);
    goButton.disabled = true;
    return;
  }
  health.className = "dot up";
  companionLine.textContent = state.root ? shortRoot(state.root) : "Companion connected";
  clearError();

  const handoffs = state.handoffs ?? [];
  const activeRecords = state.active ?? [];

  renderReady(state.ready ?? []);
  renderFlight(handoffs, state.progress ?? [], activeRecords);
  renderRecovery(activeRecords, handoffs);
  renderHistory(state.recent ?? []);
  collapseLaunch(handoffs.length > 0);

  repairTarget = state.repairExchangeId;
  repairButton.hidden = !state.canRepair;
  renderDownloadFailure(state.lastDownloadFailure);
  renderResult(state.lastReport);
  scheduleTick(handoffs);
}

/* ---------- the stack's own shape ---------- */

function collapseLaunch(hasActive) {
  launchToggle.hidden = !hasActive;
  if (lastHadActive !== hasActive) {
    // The situation changed; the operator's old preference is about the old
    // situation.
    launchPinned = null;
    lastHadActive = hasActive;
  }
  const collapsed = launchPinned === null ? hasActive : !launchPinned;
  launchCard.classList.toggle("collapsed", collapsed && hasActive);
  launchToggle.textContent = launchCard.classList.contains("collapsed") ? "Show" : "Hide";
}

/* ---------- prepared calls ---------- */

function renderReady(ready) {
  const keep = select.value;
  select.replaceChildren();
  for (const call of ready) {
    const option = document.createElement("option");
    option.value = call.exchange_id;
    option.textContent = call.subject || call.exchange_id;
    option.call = call;
    select.append(option);
  }
  if (ready.some((call) => call.exchange_id === keep)) {
    select.value = keep;
  }
  readyCount.textContent = ready.length === 1 ? "1 ready" : `${ready.length} ready`;
  readyCount.className = ready.length ? "pill ok" : "pill";
  goButton.disabled = ready.length === 0;
  renderDetail(select.selectedOptions[0]?.call);
}

function renderDetail(call) {
  callDetail.replaceChildren();
  if (!call) {
    return;
  }
  /* Three lines, and only what the operator can act on before Go: which
   * request this is, the one archive going up, the one coming back. The main
   * JSON is not listed — it travels inside the archive and is never a download,
   * which is the same reason the in-flight checklist stopped naming it. */
  const rows = [["request", call.request_id]];
  for (const name of call.attach_files ?? []) {
    rows.push(["sends", name]);
  }
  for (const name of call.expected_artifacts ?? []) {
    rows.push(["expects", name]);
  }
  for (const [term, value] of rows) {
    const dt = document.createElement("dt");
    dt.textContent = term;
    const dd = document.createElement("dd");
    dd.textContent = value ?? "";
    callDetail.append(dt, dd);
  }
}

/* ---------- in flight ---------- */

function renderFlight(handoffs, progress, activeRecords) {
  flight.replaceChildren();
  flightCard.hidden = handoffs.length === 0;
  flightCount.textContent = handoffs.length ? `${handoffs.length} running` : "";
  flightCount.className = "pill wait";

  const progressById = new Map(progress.map((item) => [item.exchange_id, item]));
  const activeById = new Map(
    activeRecords.map((record) => [record.exchange_id, record]),
  );
  for (const handoff of handoffs) {
    flight.append(
      callCard(
        handoff,
        progressById.get(handoff.exchangeId),
        activeById.get(handoff.exchangeId),
      ),
    );
  }
}

function callCard(handoff, progress, activeRecord) {
  const card = document.createElement("div");
  card.className = "call";

  const title = document.createElement("p");
  title.className = "call-title";
  title.textContent = progress?.subject || handoff.subject || handoff.exchangeId;
  card.append(title);

  const id = document.createElement("div");
  id.className = "call-id";
  id.textContent = handoff.exchangeId;
  card.append(id);

  const head = document.createElement("div");
  head.className = "card-head";
  const stage = document.createElement("p");
  stage.className = "call-stage";
  stage.textContent = handoff.message ?? describeStage(handoff.status);
  head.append(stage);
  const elapsed = document.createElement("span");
  elapsed.className = "pill";
  elapsed.dataset.since = progress?.started_at ?? handoff.monitoringStartedAt ?? "";
  elapsed.textContent = formatElapsed(elapsed.dataset.since, Date.now());
  head.append(elapsed);
  card.append(head);

  if (progress?.files?.length) {
    card.append(fileChecklist(progress.files));
  }

  /* A durable filing failure attributed to this call. The file is safe in the
   * downloads folder; what matters is saying so before Done stops monitoring —
   * and saying so even if the browser restarted since it happened. */
  const failures = activeRecord?.download_failures ?? [];
  if (failures.length) {
    const newest = failures[failures.length - 1];
    const warn = document.createElement("p");
    warn.className = "warn";
    warn.textContent = describeDownloadFailure({
      downloadId: newest.download_id,
      message: newest.message,
    });
    card.append(warn);
  }

  const guard = downloadGuard(progress, forced.has(handoff.exchangeId));
  if (guard.warning) {
    const warn = document.createElement("p");
    warn.className = "warn";
    warn.textContent = guard.warning;
    card.append(warn);
  }

  const row = document.createElement("div");
  row.className = "row";
  const done = actionButton(guard.doneLabel, "primary", {
    type: "DONE",
    exchangeId: handoff.exchangeId,
  });
  done.disabled = guard.blockDone;
  row.append(done);
  row.append(actionButton("Stop", "secondary", { type: "STOP", exchangeId: handoff.exchangeId }));
  card.append(row);

  if (guard.blockDone) {
    const override = document.createElement("button");
    override.type = "button";
    override.className = "ghost";
    override.textContent = "Let me click Done anyway";
    override.addEventListener("click", () => {
      forced.add(handoff.exchangeId);
      refresh();
    });
    card.append(override);
  }
  return card;
}

function fileChecklist(files) {
  const list = document.createElement("ul");
  list.className = "files";
  for (const file of files) {
    const item = document.createElement("li");
    item.className = file.arrived ? "here" : "away";

    const tick = document.createElement("span");
    tick.className = "tick";
    tick.textContent = file.arrived ? "✓" : "○";
    item.append(tick);

    const name = document.createElement("span");
    name.className = "name";
    name.textContent = file.filename;
    item.append(name);

    const size = document.createElement("span");
    size.className = "size";
    size.textContent = file.arrived ? formatBytes(file.size) : "waiting";
    item.append(size);

    list.append(item);
  }
  return list;
}

function actionButton(label, className, message) {
  const button = document.createElement("button");
  button.type = "button";
  button.className = className;
  button.textContent = label;
  button.addEventListener("click", () =>
    run(async () => {
      const result = await send(message);
      if (message.type === "DONE") {
        forced.delete(message.exchangeId);
        renderResult(result);
      }
    }),
  );
  return button;
}

/* ---------- recovery after a browser restart ---------- */

/* The companion still holds active calls; the browser holds no handoffs. What
 * a restart destroyed is the binding to a conversation, and that cannot be
 * guessed back: resuming a conductor call into a fresh tab silently discards
 * the thread the mode existed to keep. So the destination is a deliberate
 * choice made here, not a default. */
function renderRecovery(activeRecords, handoffs) {
  const lost = handoffs.length === 0 ? activeRecords : [];
  recoveryCard.hidden = lost.length === 0;
  recoveryList.replaceChildren();
  if (!lost.length) {
    return;
  }
  recoveryCount.textContent = lost.length === 1 ? "1 call" : `${lost.length} calls`;
  for (const record of lost) {
    const item = document.createElement("div");
    item.className = "recover-item";

    const title = document.createElement("p");
    title.className = "call-title";
    title.textContent = record.request_id || record.exchange_id;
    item.append(title);

    const id = document.createElement("div");
    id.className = "call-id";
    id.textContent = record.exchange_id;
    item.append(id);

    const resume = document.createElement("button");
    resume.type = "button";
    resume.className = "secondary";
    resume.textContent = "Resume attachment";
    resume.disabled = !recoveryMode.value;
    resume.addEventListener("click", () =>
      run(async () => {
        const handoff = await send({
          type: "RESUME",
          exchangeId: record.exchange_id,
          mode: recoveryMode.value,
        });
        showLaunchPrompt(handoff);
      }),
    );
    item.append(resume);
    recoveryList.append(item);
  }
}

recoveryMode.addEventListener("change", () => {
  for (const button of recoveryList.querySelectorAll("button")) {
    button.disabled = !recoveryMode.value;
  }
});

function renderDownloadFailure(failure) {
  const message = describeDownloadFailure(failure);
  downloadFailure.textContent = message;
  downloadFailure.hidden = message === "";
}

/* ---------- results: three facts, never one word ---------- */

function renderResult(report) {
  if (!report) {
    resultCard.hidden = true;
    return;
  }
  resultCard.hidden = false;
  renderFactsInto(resultFactsBox, report);

  resultBody.replaceChildren();
  const rows = [];
  if (report.missing_files?.length) {
    rows.push(["missing", report.missing_files.join(", ")]);
  }
  if (report.invalid_files?.length) {
    rows.push(["invalid", report.invalid_files.join(", ")]);
  }
  if (report.checked_files?.length) {
    rows.push(["validated", report.checked_files.join(", ")]);
  }
  if (rows.length) {
    const list = document.createElement("ul");
    list.className = "result-list";
    for (const [label, value] of rows) {
      const item = document.createElement("li");
      const key = document.createElement("span");
      key.className = "label";
      key.textContent = label;
      const val = document.createElement("span");
      val.className = "value";
      val.textContent = value;
      item.append(key, val);
      list.append(item);
    }
    resultBody.append(list);
  }

  renderDefects(report);
}

function renderFactsInto(container, report) {
  container.replaceChildren();
  for (const fact of resultFacts(report)) {
    const box = document.createElement("div");
    box.className = `fact ${fact.tone}`;
    const label = document.createElement("span");
    label.className = "fact-label";
    label.textContent = fact.label;
    const value = document.createElement("span");
    value.className = "fact-value";
    value.textContent = fact.value;
    box.append(label, value);
    box.title = fact.detail;
    container.append(box);
  }
}

/* Only an INCOMPLETE delivery has defects worth listing, and they come from
 * the same diagnosis a correction round would send — so the operator sees why
 * before deciding whether to open one, without a terminal. */
async function renderDefects(report) {
  defectList.hidden = true;
  defectList.replaceChildren();
  resultRound.hidden = true;
  if (!report.exchange_id) {
    return;
  }
  try {
    const inspect = await send({ type: "INSPECT", exchangeId: report.exchange_id });
    if (inspect.repair_round > 0) {
      resultRound.textContent = `round ${inspect.repair_round}`;
      resultRound.hidden = false;
    }
    if (report.status !== "INCOMPLETE" || !inspect.defects?.length) {
      return;
    }
    for (const defect of inspect.defects) {
      const item = document.createElement("li");
      const kind = document.createElement("span");
      kind.className = "kind";
      kind.textContent = `${defect.kind} · ${defect.target}`;
      const why = document.createElement("span");
      why.className = "why";
      why.textContent = `expected ${defect.expected}; got ${defect.observed}`;
      item.append(kind, why);
      defectList.append(item);
    }
    defectList.hidden = false;
  } catch (_error) {
    // Recall is a convenience; the report on disk stays authoritative.
  }
}

/* Only when typing it was attempted and failed.
 *
 * `true` means the line is already in the composer, and showing it again would
 * invite the operator to paste a second copy underneath the first. `null` means
 * it was never attempted, because the call is going into a conversation the
 * operator is already working in and that thread does not need telling. */
function showLaunchPrompt(handoff) {
  if (!handoff || handoff.launchInserted !== false) {
    return;
  }
  showPromptToCopy(handoff.launchPrompt);
}

/* The card that hands the operator text to paste. It serves a correction round
 * and a launch line that could not be typed: same need either way, which is a
 * prompt the extension has but the page did not take. */
function showPromptToCopy(text) {
  if (typeof text !== "string" || !text) {
    return;
  }
  repairPrompt.textContent = text;
  repairCard.hidden = false;
  copyRepairButton.textContent = "Copy";
}

/* ---------- the archive ---------- */

function renderHistory(recent) {
  historyCard.hidden = recent.length === 0;
  historyCount.textContent = recent.length === 1 ? "1 call" : `${recent.length} calls`;
  history.replaceChildren();
  for (const item of recent) {
    const row = document.createElement("li");

    const button = document.createElement("button");
    button.type = "button";
    button.className = "h-row";
    button.setAttribute("aria-expanded", String(openHistoryId === item.exchange_id));
    const name = document.createElement("span");
    name.className = "h-name";
    name.textContent = item.subject || item.exchange_id;
    const state = document.createElement("span");
    state.className = `pill ${
      item.state === "COMPLETE" ? "ok" : item.state === "INCOMPLETE" ? "bad" : ""
    }`.trim();
    state.textContent = item.state ?? "";
    button.append(name, state);
    button.addEventListener("click", () => toggleHistoryDrawer(item.exchange_id));
    row.append(button);

    if (openHistoryId === item.exchange_id) {
      const drawer = document.createElement("div");
      drawer.className = "h-drawer";
      drawer.dataset.exchange = item.exchange_id;
      drawer.textContent = "Reading…";
      row.append(drawer);
      fillHistoryDrawer(drawer, item.exchange_id);
    }
    history.append(row);
  }
}

function toggleHistoryDrawer(exchangeId) {
  openHistoryId = openHistoryId === exchangeId ? null : exchangeId;
  refresh();
}

/* Recall without a terminal: what the call was, how it ended, what came back,
 * and where the files live. Paths are selectable text, deliberately — the
 * panel points at responses, it never renders them. */
async function fillHistoryDrawer(drawer, exchangeId) {
  let inspect;
  try {
    inspect = await send({ type: "INSPECT", exchangeId });
  } catch (error) {
    drawer.textContent = error.message;
    return;
  }
  if (drawer.dataset.exchange !== exchangeId) {
    return;
  }
  drawer.replaceChildren();

  if (inspect.validation) {
    const facts = document.createElement("div");
    facts.className = "facts";
    renderFactsInto(facts, inspect.validation);
    drawer.append(facts);
  }

  const kv = document.createElement("dl");
  kv.className = "kv";
  const rows = [
    ["request", inspect.request_id],
    ["state", inspect.state],
    ["created", inspect.created_at],
  ];
  if (inspect.repair_round > 0) {
    rows.push(["rounds", String(inspect.repair_round)]);
  }
  for (const file of inspect.response_files ?? []) {
    rows.push(["file", `${file.filename} · ${formatBytes(file.size)}`]);
  }
  if (inspect.defects?.length) {
    rows.push([
      "defects",
      inspect.defects.map((defect) => defect.kind).join(", "),
    ]);
  }
  if (inspect.paths?.main_response) {
    rows.push(["response", inspect.paths.main_response]);
  }
  rows.push(["folder", inspect.paths?.exchange ?? ""]);
  for (const [term, value] of rows) {
    const dt = document.createElement("dt");
    dt.textContent = term;
    const dd = document.createElement("dd");
    dd.textContent = value ?? "";
    kv.append(dt, dd);
  }
  drawer.append(kv);
}

/* ---------- plumbing ---------- */

function scheduleTick(handoffs) {
  clearInterval(ticking);
  if (handoffs.length === 0) {
    return;
  }
  // A live clock without a full refresh, so the elapsed pill stays honest
  // between status pushes.
  ticking = setInterval(() => {
    for (const pill of flight.querySelectorAll("[data-since]")) {
      pill.textContent = formatElapsed(pill.dataset.since, Date.now());
    }
  }, 1000);
}

function setBusy(busy) {
  goButton.disabled = busy || select.options.length === 0;
  repairButton.disabled = busy;
  for (const button of flight.querySelectorAll("button")) {
    button.disabled = busy;
  }
  for (const button of recoveryList.querySelectorAll("button")) {
    button.disabled = busy || !recoveryMode.value;
  }
}

function showError(message) {
  errorLine.textContent = message;
  errorLine.hidden = false;
}

function clearError() {
  errorLine.hidden = true;
  errorLine.textContent = "";
}

function shortRoot(root) {
  const parts = String(root).split(/[\\/]/).filter(Boolean);
  return parts.slice(-2).join("/") || root;
}

async function send(message) {
  const response = await chrome.runtime.sendMessage(message);
  if (!response?.ok) {
    throw new Error(response?.error ?? "Extension command failed");
  }
  return response.result;
}

refresh();
