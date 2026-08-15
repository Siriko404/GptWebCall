/* Pure panel logic, kept out of the DOM so it can be tested.
 *
 * downloadGuard is the important one. Clicking Done stops monitoring, so a file
 * still in flight at that moment is never collected and has to be copied into
 * the exchange by hand afterwards. The guard turns that into something visible:
 * Done stays disabled while an expected file is missing, and enabling it is a
 * deliberate act rather than an accident of timing.
 */

const STAGES = {
  WAITING_FOR_ATTACH_CLICK: "Waiting for you to click Attach files in ChatGPT.",
  ATTACHED: "Files attached. Review them, then click Send.",
  COLLECTING: "Collecting downloads.",
  REPAIR_PROMPTED: "Correction prompt is in the composer. Click Send.",
};

export function describeStage(status) {
  return STAGES[status] ?? String(status ?? "Running.");
}

export function formatBytes(bytes) {
  const value = Number(bytes);
  if (!Number.isFinite(value) || value < 0) {
    return "";
  }
  if (value < 1024) {
    return `${value} B`;
  }
  const units = ["KB", "MB", "GB"];
  let scaled = value / 1024;
  let unit = 0;
  while (scaled >= 1024 && unit < units.length - 1) {
    scaled /= 1024;
    unit += 1;
  }
  return `${scaled < 10 ? scaled.toFixed(1) : Math.round(scaled)} ${units[unit]}`;
}

export function formatElapsed(startedAt, nowMs) {
  const started = Date.parse(startedAt ?? "");
  if (!Number.isFinite(started)) {
    return "";
  }
  const seconds = Math.max(0, Math.round((nowMs - started) / 1000));
  if (seconds < 60) {
    return `${seconds}s`;
  }
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) {
    return `${minutes}m ${String(seconds % 60).padStart(2, "0")}s`;
  }
  return `${Math.floor(minutes / 60)}h ${String(minutes % 60).padStart(2, "0")}m`;
}

export function downloadGuard(progress, forced = false) {
  // Without progress data we cannot know, so we must not block the operator.
  if (!progress || !Array.isArray(progress.files) || progress.files.length === 0) {
    return { blockDone: false, warning: "", doneLabel: "Done and validate" };
  }
  const missing = progress.files.filter((file) => !file.arrived).map((file) => file.filename);
  if (missing.length === 0) {
    return {
      blockDone: false,
      warning: "",
      doneLabel: `Done and validate (${progress.files.length}/${progress.files.length})`,
    };
  }
  const noun = missing.length === 1 ? "file has" : "files have";
  return {
    blockDone: !forced,
    warning:
      `${missing.length} ${noun} not arrived yet: ${missing.join(", ")}. ` +
      "Done stops monitoring, so anything still downloading will not be collected.",
    doneLabel: `Done and validate (${progress.received}/${progress.expected})`,
  };
}


/* The report carries three independent facts that were being read as one word.
 *
 * `status` is the delivery: did every promised file arrive intact. `response_
 * status` is the responder's own account of the work. `manifest_verified` says
 * whether the declared hashes were usable. A PARTIAL piece of work delivered
 * intact is COMPLETE + PARTIAL + true, and collapsing that into any single
 * word has already misled the operator once. The panel therefore renders all
 * three, each with its own tone, and this function is the one place the
 * mapping lives.
 */
export function resultFacts(report) {
  if (!report || typeof report !== "object") {
    return [];
  }
  const delivery = report.status ?? null;
  const work = report.response_status ?? null;
  const manifest = report.manifest_verified;
  return [
    {
      key: "delivery",
      label: "Delivery",
      value: delivery ?? "—",
      tone: delivery === "COMPLETE" ? "ok" : delivery === "INCOMPLETE" ? "bad" : "neutral",
      detail:
        delivery === "COMPLETE"
          ? "Every promised file arrived intact."
          : delivery === "INCOMPLETE"
            ? "A promised file is missing or corrupt."
            : "No delivery verdict.",
    },
    {
      key: "work",
      label: "Work",
      value: work ?? "unreported",
      tone: work === "COMPLETE" ? "ok" : work === "PARTIAL" ? "wait" : work === "BLOCKED" ? "bad" : "neutral",
      detail:
        work === "PARTIAL"
          ? "The responder declared gaps. Read them; do not repair an intact delivery."
          : work === "BLOCKED"
            ? "The responder said it could not do the work."
            : work === "COMPLETE"
              ? "The responder's own account of the work."
              : "The responder did not report on its work.",
    },
    {
      key: "manifest",
      label: "Hashes",
      value: manifest === true ? "verified" : manifest === false ? "unusable" : "—",
      tone: manifest === true ? "ok" : manifest === false ? "wait" : "neutral",
      detail:
        manifest === false
          ? "Declared hashes could not be used; read before trusting."
          : "Each file checked against the hash the responder declared.",
    },
  ];
}


export function describeDownloadFailure(failure) {
  // The operator needs the recovery, not the stack trace: the bytes are safe in
  // the downloads folder and the exchange is still waiting for them.
  if (!failure || typeof failure.message !== "string" || failure.message === "") {
    return "";
  }
  const which = Number.isInteger(failure.downloadId)
    ? `Download ${failure.downloadId}`
    : "A download";
  return (
    `${which} was not filed into its call: ${failure.message}. ` +
    "The file is still in your downloads folder. Copy it into the exchange's " +
    "response folder, or download it again before clicking Done."
  );
}
