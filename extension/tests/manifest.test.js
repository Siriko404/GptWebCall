import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";


test("manifest requests only the approved permissions", async () => {
  const manifest = JSON.parse(
    await readFile(new URL("../manifest.json", import.meta.url), "utf8"),
  );

  assert.equal(manifest.manifest_version, 3);
  assert.deepEqual(manifest.permissions, [
    "sidePanel",
    "nativeMessaging",
    "debugger",
    "downloads",
    "storage",
  ]);
  assert.equal(manifest.host_permissions, undefined);
  assert.equal(manifest.content_scripts, undefined);
});
