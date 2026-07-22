/* The panel exists to answer one question quickly: is it safe to click Done?
 *
 * Done stops monitoring. Anything still downloading at that moment is never
 * collected, and getting it back means copying files into the exchange by hand.
 * So every in-flight call shows its expected files as a checklist, and Done is
 * held back until they have all landed. The operator can still force it, but
 * only deliberately.
 */

import { describeStage, formatBytes, formatElapsed, downloadGuard } from "./lib/panel.js";

const el = (id) => document.querySelector(`#${id}`);

const select = el("call-select");
const callDetail = el("call-detail");
const readyCount = el("ready-count");
const goButton = el("go-button");
const flight = el("flight");
const flightEmpty = el("flight-empty");
const flightCount = el("flight-count");
const resumeButton = el("resume-button");
const resultCard = el("result-card");
const resultStatus = el("result-status");
const resultBody = el("result-body");
const repairButton = el("repair-button");
const repairCard = el("repair-card");
const repairPrompt = el("repair-prompt");
const copyRepairButton = el("copy-repair-button");
const historyCard = el("history-card");
const history = el("history");
const historyToggle = el("history-toggle");
const health = el("health");
const companionLine = el("companion-line");
const errorLine = el("error");

let repairTarget = null;
let forced = new Set();
let ticking = null;

goButton.addEventListener("click", () => run(() => send({ type: "GO", exchangeId: select.value })));
resumeButton.addEventListener("click", () => run(() => send({ type: "RESUME" })));

repairButton.addEventListener("click", () =>
  run(async () => {
    const handoff = await send({ type: "REPAIR", exchangeId: repairTarget });
    showRepairPrompt(handoff);
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

historyToggle.addEventListener("click", () => {
  history.hidden = !history.hidden;
  historyToggle.textContent = history.hidden ? "Show" : "Hide";
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

  renderReady(state.ready ?? []);
  renderFlight(state.handoffs ?? [], state.progress ?? []);
  renderHistory(state.recent ?? []);

  resumeButton.hidden = !(state.active?.length && (state.handoffs ?? []).length === 0);
  repairTarget = state.repairExchangeId;
  repairButton.hidden = !state.canRepair;
  renderResult(state.lastReport);
  scheduleTick(state.handoffs ?? []);
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
  const rows = [
    ["request", call.request_id],
    ["returns", call.expected_main_json],
  ];
  for (const name of call.expected_artifacts ?? []) {
    rows.push(["archive", name]);
  }
  const uploads = call.attach_files ?? [];
  if (uploads.length) {
    rows.push(["uploads", `${uploads.length} files: ${uploads.join(", ")}`]);
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

function renderFlight(handoffs, progress) {
  flight.replaceChildren();
  flightEmpty.hidden = handoffs.length > 0;
  flightCount.textContent = handoffs.length ? `${handoffs.length} running` : "idle";
  flightCount.className = handoffs.length ? "pill wait" : "pill";

  const byId = new Map(progress.map((item) => [item.exchange_id, item]));
  for (const handoff of handoffs) {
    flight.append(callCard(handoff, byId.get(handoff.exchangeId)));
  }
}

function callCard(handoff, progress) {
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

/* ---------- results ---------- */

function renderResult(report) {
  if (!report) {
    resultCard.hidden = true;
    return;
  }
  resultCard.hidden = false;
  resultStatus.textContent = report.status ?? "";
  resultStatus.className =
    report.status === "COMPLETE" ? "pill ok" : report.status === "INCOMPLETE" ? "pill bad" : "pill";

  resultBody.replaceChildren();
  const list = document.createElement("ul");
  list.className = "result-list";
  const rows = [];
  if (report.checked_files?.length) {
    rows.push(["validated", report.checked_files.join(", ")]);
  }
  if (report.missing_files?.length) {
    rows.push(["missing", report.missing_files.join(", ")]);
  }
  if (report.invalid_files?.length) {
    rows.push(["invalid", report.invalid_files.join(", ")]);
  }
  if (rows.length === 0) {
    rows.push(["result", "See the validation report on disk."]);
  }
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

function showRepairPrompt(handoff) {
  if (!handoff?.repairPrompt) {
    return;
  }
  repairPrompt.textContent = handoff.repairPrompt;
  repairCard.hidden = false;
  copyRepairButton.textContent = "Copy";
}

/* ---------- history ---------- */

function renderHistory(recent) {
  historyCard.hidden = recent.length === 0;
  history.replaceChildren();
  for (const item of recent) {
    const row = document.createElement("li");
    const name = document.createElement("span");
    name.className = "h-name";
    name.textContent = item.subject || item.exchange_id;
    const state = document.createElement("span");
    state.className = `pill ${
      item.state === "COMPLETE" ? "ok" : item.state === "INCOMPLETE" ? "bad" : ""
    }`.trim();
    state.textContent = item.state ?? "";
    row.append(name, state);
    history.append(row);
  }
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
  resumeButton.disabled = busy;
  repairButton.disabled = busy;
  for (const button of flight.querySelectorAll("button")) {
    button.disabled = busy;
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
