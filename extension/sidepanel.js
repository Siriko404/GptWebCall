const select = document.querySelector("#call-select");
const summary = document.querySelector("#call-summary");
const status = document.querySelector("#status");
const running = document.querySelector("#running");
const attachments = document.querySelector("#attachments");
const goButton = document.querySelector("#go-button");
const resumeButton = document.querySelector("#resume-button");
const repairButton = document.querySelector("#repair-button");
const repairCard = document.querySelector("#repair-card");
const repairPrompt = document.querySelector("#repair-prompt");
const copyRepairButton = document.querySelector("#copy-repair-button");
const validationReport = document.querySelector("#validation-report");

let repairTarget = null;


goButton.addEventListener("click", async () => {
  setBusy(true);
  try {
    await send({ type: "GO", exchangeId: select.value });
    await refresh();
  } catch (error) {
    status.textContent = error.message;
  } finally {
    setBusy(false);
  }
});


resumeButton.addEventListener("click", async () => {
  setBusy(true);
  try {
    await send({ type: "RESUME" });
    await refresh();
  } catch (error) {
    status.textContent = error.message;
  } finally {
    setBusy(false);
  }
});


repairButton.addEventListener("click", async () => {
  setBusy(true);
  try {
    const handoff = await send({ type: "REPAIR", exchangeId: repairTarget });
    showRepairPrompt(handoff);
    await refresh();
  } catch (error) {
    status.textContent = error.message;
  } finally {
    setBusy(false);
  }
});


copyRepairButton.addEventListener("click", async () => {
  try {
    await navigator.clipboard.writeText(repairPrompt.textContent);
    copyRepairButton.textContent = "Copied";
  } catch (_error) {
    copyRepairButton.textContent = "Copy failed";
  }
});


select.addEventListener("change", () => {
  const call = select.selectedOptions[0]?.call;
  summary.textContent = call
    ? `${call.subject} · expects ${call.expected_main_json}`
    : "No prepared calls.";
});


chrome.runtime.onMessage.addListener((message) => {
  if (message?.type === "HANDOFF_STATUS") {
    refresh();
  }
});


async function refresh() {
  try {
    const state = await send({ type: "GET_STATUS" });
    renderReady(state.ready);
    renderRunning(state.handoffs, state.active);
    repairTarget = state.repairExchangeId;
    repairButton.hidden = !state.canRepair;
    resumeButton.hidden = !(state.active?.length && state.handoffs.length === 0);
    if (state.handoffs.length === 0) {
      status.textContent = state.active?.length
        ? "A call is active but this Chrome session lost its tab. Resume it."
        : "Ready.";
      attachments.replaceChildren();
    }
    renderReport(state.lastReport);
  } catch (error) {
    status.textContent = `Local companion unavailable: ${error.message}`;
    goButton.disabled = true;
  }
}


function renderReady(ready) {
  select.replaceChildren();
  for (const call of ready) {
    const option = document.createElement("option");
    option.value = call.exchange_id;
    option.textContent = call.subject;
    option.call = call;
    select.append(option);
  }
  select.dispatchEvent(new Event("change"));
  goButton.disabled = ready.length === 0;
}


function renderRunning(handoffs, active) {
  running.replaceChildren();
  if (handoffs.length === 0) {
    return;
  }
  status.textContent = `${handoffs.length} call${handoffs.length === 1 ? "" : "s"} in flight.`;
  attachments.replaceChildren();
  for (const handoff of handoffs) {
    running.append(runningRow(handoff));
  }
  const armed = handoffs.find((one) => one.armed);
  if (armed) {
    for (const name of armed.attachmentNames ?? []) {
      const item = document.createElement("li");
      item.textContent = name;
      attachments.append(item);
    }
  }
}


function runningRow(handoff) {
  const row = document.createElement("div");
  row.className = "summary";

  const title = document.createElement("div");
  title.textContent = handoff.exchangeId;
  row.append(title);

  const detail = document.createElement("div");
  detail.textContent = handoff.message ?? handoff.status;
  row.append(detail);

  row.append(actionButton("Done and validate", "primary", { type: "DONE", exchangeId: handoff.exchangeId }));
  row.append(actionButton("Stop", "secondary", { type: "STOP", exchangeId: handoff.exchangeId }));
  return row;
}


function actionButton(label, className, message) {
  const button = document.createElement("button");
  button.type = "button";
  button.className = className;
  button.textContent = label;
  button.addEventListener("click", async () => {
    setBusy(true);
    try {
      const result = await send(message);
      if (message.type === "DONE") {
        renderReport(result);
      }
      await refresh();
    } catch (error) {
      status.textContent = error.message;
    } finally {
      setBusy(false);
    }
  });
  return button;
}


function showRepairPrompt(handoff) {
  if (!handoff?.repairPrompt) {
    return;
  }
  repairPrompt.textContent = handoff.repairPrompt;
  repairCard.hidden = false;
  copyRepairButton.textContent = "Copy prompt";
}


function renderReport(report) {
  if (!report) {
    validationReport.hidden = true;
    validationReport.textContent = "";
    return;
  }
  const details = [];
  if (report.missing_files?.length) {
    details.push(`Missing: ${report.missing_files.join(", ")}`);
  }
  if (report.invalid_files?.length) {
    details.push(`Invalid: ${report.invalid_files.join(", ")}`);
  }
  validationReport.textContent = report.status === "COMPLETE"
    ? "Complete. Main JSON and required artifacts validated."
    : `Incomplete. ${details.join("\n") || "See validation report."}`;
  validationReport.hidden = false;
}


function setBusy(busy) {
  goButton.disabled = busy || select.options.length === 0;
  resumeButton.disabled = busy;
  repairButton.disabled = busy;
  for (const button of running.querySelectorAll("button")) {
    button.disabled = busy;
  }
}


async function send(message) {
  const response = await chrome.runtime.sendMessage(message);
  if (!response?.ok) {
    throw new Error(response?.error ?? "Extension command failed");
  }
  return response.result;
}


refresh();
