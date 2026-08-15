import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const css = () => readFile(new URL("../sidepanel.css", import.meta.url), "utf8");


/* Line design: structure comes from space and single-pixel rules. Filled,
 * shadowed, blurred containers are what made the panel read as crowded in a
 * strip this narrow, and they creep back one property at a time. */
test("the panel is drawn with rules, not with boxes", async () => {
  const style = await css();

  assert.doesNotMatch(style, /backdrop-filter/);
  assert.doesNotMatch(style, /box-shadow/);
  assert.doesNotMatch(style, /text-shadow/);
  // Sections are separated by a hairline and nothing else.
  assert.match(style, /\.card \{[^}]*border-top: 1px solid/);
});


/* "Minimize the animations." Nothing moves on load, and nothing transforms on
 * interaction; only colour changes, which carries meaning. */
test("nothing animates on load and nothing moves on interaction", async () => {
  const style = await css();

  assert.doesNotMatch(style, /@keyframes/);
  assert.doesNotMatch(style, /animation:/);
  assert.doesNotMatch(style, /transition:/);
  // Anchored, so `text-transform` does not read as movement.
  assert.doesNotMatch(style, /(^|[\s;{])transform:/m);
});


/* A native select paints its own light chrome over a dark page, which is what
 * made the dropdowns look wrong. Both halves are needed: the control is drawn
 * here, and the option list is coloured so the OS popup follows. */
test("selects are drawn by this stylesheet, popup included", async () => {
  const style = await css();

  assert.match(style, /select \{[^}]*appearance: none/);
  assert.match(style, /select option \{[^}]*background-color/);
  // The arrow the native control no longer draws.
  assert.match(style, /background-image: url\("data:image\/svg\+xml/);
  // color-scheme tells Chrome to render the popup dark in the first place.
  assert.match(style, /color-scheme: dark/);
});


/* Navy ground, one green. A second accent hue is how a two-colour scheme
 * becomes a five-colour one; amber and red stay, but only as status. */
test("the palette is navy and one green", async () => {
  const style = await css();

  const tokens = style.slice(style.indexOf(":root"), style.indexOf("* {"));
  assert.match(tokens, /--navy: #0a1628/);
  assert.match(tokens, /--green: #38f06b/);
  // Status colours are the only other hues, and each has exactly one job.
  const hues = [...tokens.matchAll(/--([a-z-]+): (#[0-9a-f]{6})/g)].map((m) => m[1]);
  assert.deepEqual(
    hues.filter((name) => !name.startsWith("navy") && !name.startsWith("line")
      && !["ink", "muted", "faint"].includes(name)),
    ["green", "green-dim", "amber", "red"],
  );
});


/* One filled control at a time: the thing to press now. Everything else is an
 * outline, so the eye has a single target in a narrow strip. */
/* This used to read `id="repair-button" class="accent"` out of the HTML. Every
 * control is built in JavaScript now — the panel is a list of calls and a
 * call's buttons depend on the state it is in — so the rule is pinned where the
 * controls are made instead of where they used to sit.
 *
 * The rule itself is unchanged: one filled control, and it is the thing to
 * press now. Filled belongs to the top list (Go, Done, Resume); a finished call
 * is finished, so everything in its drawer is outlined.
 */
test("only the immediate next action is filled", async () => {
  const style = await css();
  const panel = await readFile(new URL("../sidepanel.js", import.meta.url), "utf8");

  assert.match(style, /\.primary \{[^}]*background: var\(--green\)/);
  assert.doesNotMatch(style, /\.accent \{[^}]*background: var\(--green\)/);

  // Correction and resend are available, not urgent.
  assert.match(panel, /accent\("Open correction round"/);
  assert.match(panel, /accent\("Prepare a copy"/);
  // And the archive drawer reaches for the filled control nowhere at all.
  const archive = panel.slice(
    panel.indexOf("async function archiveDrawer"),
    panel.indexOf("/* ---------- pieces"),
  );
  assert.ok(archive.length > 0, "the archive drawer is where this test thinks");
  assert.doesNotMatch(archive, /primary\(/);
});
