const WINDOWS_ABSOLUTE_PATH = /^[A-Za-z]:\\/;


export function buildFileAssignment(handoff, source, params) {
  if (!handoff || handoff.armed !== true) {
    throw new Error("attachment handoff is not armed");
  }
  if (!source || source.tabId !== handoff.tabId) {
    throw new Error("file chooser did not come from the bound tab");
  }
  if (!Number.isInteger(params?.backendNodeId) || params.backendNodeId < 0) {
    throw new Error("file chooser event has no valid backendNodeId");
  }
  if (!Array.isArray(handoff.requestPaths) || handoff.requestPaths.length === 0) {
    throw new Error("approved request paths are empty");
  }
  if (!handoff.requestPaths.every((path) => (
    typeof path === "string" && WINDOWS_ABSOLUTE_PATH.test(path)
  ))) {
    throw new Error("every request path must be an absolute Windows path");
  }
  return {
    method: "DOM.setFileInputFiles",
    params: {
      files: [...handoff.requestPaths],
      backendNodeId: params.backendNodeId,
    },
  };
}


export function attachmentBasenames(paths) {
  if (!Array.isArray(paths)) {
    return [];
  }
  return paths.map((path) => path.split(/[\\/]/).at(-1));
}
