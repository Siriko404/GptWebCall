const select = document.querySelector("#call-select");
const summary = document.querySelector("#call-summary");
const status = document.querySelector("#status");
const attachments = document.querySelector("#attachments");
const goButton = document.querySelector("#go-button");
const stopButton = document.querySelector("#stop-button");


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
    if (state.handoff) {
      renderHandoff(state.handoff);
    } else if (state.active) {
      status.textContent = "A call is active. Stop it or resume after reopening Chrome.";
      stopButton.hidden = false;
      goButton.disabled = true;
    } else {
      status.textContent = "Ready.";
      stopButton.hidden = true;
    }
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
  stopButton.hidden = false;
}


function setBusy(busy) {
  goButton.disabled = busy || select.options.length === 0;
  stopButton.disabled = busy;
}


async function send(message) {
  const response = await chrome.runtime.sendMessage(message);
  if (!response?.ok) {
    throw new Error(response?.error ?? "Extension command failed");
  }
  return response.result;
}


refresh();
