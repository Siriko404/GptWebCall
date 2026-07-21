const select = document.querySelector("#call-select");
const summary = document.querySelector("#call-summary");
const status = document.querySelector("#status");
const attachments = document.querySelector("#attachments");
const goButton = document.querySelector("#go-button");
const resumeButton = document.querySelector("#resume-button");
const doneButton = document.querySelector("#done-button");
const stopButton = document.querySelector("#stop-button");
const repairButton = document.querySelector("#repair-button");
const repairCard = document.querySelector("#repair-card");
const repairPrompt = document.querySelector("#repair-prompt");
const copyRepairButton = document.querySelector("#copy-repair-button");
const validationReport = document.querySelector("#validation-report");


goButton.addEventListener("click", async () => {
  setBusy(true);
  try {
    const response = await send({ type: "GO", exchangeId: select.value });
    renderHandoff(response);
  } catch (error) {
    status.textContent = error.message;
  } finally {
    setBusy(false);
  }
});


stopButton.addEventListener("click", async () => {
  setBusy(true);
  try {
    await send({ type: "STOP" });
    await refresh();
  } catch (error) {
    status.textContent = error.message;
  } finally {
    setBusy(false);
  }
});


doneButton.addEventListener("click", async () => {
  setBusy(true);
  try {
    const report = await send({ type: "DONE" });
    renderReport(report);
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
    const handoff = await send({ type: "RESUME" });
    renderHandoff(handoff);
  } catch (error) {
    status.textContent = error.message;
  } finally {
    setBusy(false);
  }
});


repairButton.addEventListener("click", async () => {
  setBusy(true);
  try {
    const handoff = await send({ type: "REPAIR" });
    renderHandoff(handoff);
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
  } catch (error) {
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
    renderHandoff(message.handoff);
  }
});


async function refresh() {
  try {
    const state = await send({ type: "GET_STATUS" });
    renderReady(state.ready);
    repairButton.hidden = !state.canRepair;
    if (state.handoff) {
      renderHandoff(state.handoff);
      repairButton.hidden = !state.canRepair;
    } else if (state.active) {
      status.textContent = "A call is active. Stop it or resume after reopening Chrome.";
      stopButton.hidden = false;
      doneButton.hidden = false;
      resumeButton.hidden = false;
      goButton.disabled = true;
    } else {
      status.textContent = "Ready.";
      stopButton.hidden = true;
      doneButton.hidden = true;
      resumeButton.hidden = true;
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


function renderHandoff(handoff) {
  status.textContent = handoff.message;
  attachments.replaceChildren();
  for (const name of handoff.attachmentNames ?? []) {
    const item = document.createElement("li");
    item.textContent = name;
    attachments.append(item);
  }
  goButton.disabled = true;
  doneButton.hidden = false;
  resumeButton.hidden = true;
  stopButton.hidden = false;
  if (handoff.repairPrompt) {
    repairPrompt.textContent = handoff.repairPrompt;
    repairCard.hidden = false;
    copyRepairButton.textContent = "Copy prompt";
    repairButton.hidden = true;
  }
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
  stopButton.disabled = busy;
  doneButton.disabled = busy;
  resumeButton.disabled = busy;
  repairButton.disabled = busy;
}


async function send(message) {
  const response = await chrome.runtime.sendMessage(message);
  if (!response?.ok) {
    throw new Error(response?.error ?? "Extension command failed");
  }
  return response.result;
}


refresh();
