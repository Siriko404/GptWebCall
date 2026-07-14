function validDownloadId(value) {
  return Number.isInteger(value) && value >= 0;
}

function parseTime(value) {
  if (typeof value !== "string") {
    return Number.NaN;
  }
  return Date.parse(value);
}

export function shouldObserveDownload(active, downloadItem) {
  if (!active?.monitoring || !validDownloadId(downloadItem?.id)) {
    return false;
  }

  const startedAt = parseTime(active.monitoringStartedAt);
  const downloadStartedAt = parseTime(downloadItem.startTime);
  if (!Number.isFinite(startedAt) || !Number.isFinite(downloadStartedAt)) {
    return false;
  }
  if (downloadStartedAt < startedAt) {
    return false;
  }

  const baseline = new Set(active.downloadBaseline ?? []);
  const observed = new Set(active.observedDownloadIds ?? []);
  return !baseline.has(downloadItem.id) && !observed.has(downloadItem.id);
}

export function completedTrackedDownload(active, trackedIds, delta) {
  return Boolean(
    active?.monitoring
      && validDownloadId(delta?.id)
      && Array.isArray(trackedIds)
      && trackedIds.includes(delta.id)
      && delta.state?.current === "complete",
  );
}

export function claimCompletedDownload(tracker, downloadId) {
  if (
    !tracker
    || !validDownloadId(downloadId)
    || !Array.isArray(tracker.ids)
    || !Array.isArray(tracker.processing)
    || !tracker.ids.includes(downloadId)
    || tracker.processing.includes(downloadId)
  ) {
    return false;
  }
  tracker.processing.push(downloadId);
  return true;
}
