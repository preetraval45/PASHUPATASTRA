import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";

/**
 * R109: the press manifest is the only source of what the page shows.
 *
 * A caption typed by hand drifts from the picture it labels, and a media kit
 * is written to be republished — so the one mistake here travels. These hold
 * the manifest to the shape the page depends on, without needing a browser.
 */
const manifest = JSON.parse(
  readFileSync(new URL("./press.generated.json", import.meta.url), "utf-8"),
);

test("every shot records the URL it came from", () => {
  assert.ok(manifest.shots.length >= 3, "a kit with two pictures is not a kit");
  for (const shot of manifest.shots) {
    assert.ok(shot.route.startsWith("/"), `${shot.name} has no route`);
    assert.ok(shot.url.endsWith(shot.route), `${shot.name}: url and route disagree`);
    assert.ok(shot.file.startsWith("/press/"), `${shot.name} is not served from /press`);
    assert.ok(shot.caption.length > 20, `${shot.name} has no caption worth reading`);
    assert.equal(shot.width, 1440);
  }
});

test("the capture is attributable to a commit and a moment", () => {
  assert.match(manifest.commit, /^[0-9a-f]{7,40}$/);
  assert.ok(!Number.isNaN(Date.parse(manifest.captured_at)));
});

test("no two shots are the same picture", () => {
  const files = manifest.shots.map((s) => s.file);
  const routes = manifest.shots.map((s) => s.route);
  assert.equal(new Set(files).size, files.length);
  assert.equal(new Set(routes).size, routes.length);
});
