const WINDOWS_ABSOLUTE_PATH = /^[A-Za-z]:\\/;


function validateArmedHandoff(handoff, source) {
  if (!handoff || handoff.armed !== true) {
    throw new Error("attachment handoff is not armed");
  }
  if (!source || source.tabId !== handoff.tabId) {
    throw new Error("file chooser did not come from the bound tab");
  }
  if (!Array.isArray(handoff.requestPaths) || handoff.requestPaths.length === 0) {
    throw new Error("approved request paths are empty");
  }
  if (!handoff.requestPaths.every((path) => (
    typeof path === "string" && WINDOWS_ABSOLUTE_PATH.test(path)
  ))) {
    throw new Error("every request path must be an absolute Windows path");
  }
}


export function buildFileAssignment(handoff, source, params) {
  validateArmedHandoff(handoff, source);
  if (!Number.isInteger(params?.backendNodeId) || params.backendNodeId < 0) {
    throw new Error("file chooser event has no valid backendNodeId");
  }
  return {
    method: "DOM.setFileInputFiles",
    params: {
      files: [...handoff.requestPaths],
      backendNodeId: params.backendNodeId,
    },
  };
}


/* ChatGPT's Attach control can open its chooser from something other than a
 * real <input type=file>, in which case Page.fileChooserOpened carries no
 * backendNodeId. The upload still lands on the composer's hidden file input,
 * so the service worker locates that input by DOM query and passes its nodeId
 * here. Same validation, same command, different node reference.
 */
export function buildFallbackAssignment(handoff, source, nodeId) {
  validateArmedHandoff(handoff, source);
  if (!Number.isInteger(nodeId) || nodeId <= 0) {
    throw new Error("no file input node available for fallback attachment");
  }
  return {
    method: "DOM.setFileInputFiles",
    params: {
      files: [...handoff.requestPaths],
      nodeId,
    },
  };
}


export function attachmentBasenames(paths) {
  if (!Array.isArray(paths)) {
    return [];
  }
  return paths.map((path) => path.split(/[\\/]/).at(-1));
}
