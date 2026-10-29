import assert from "node:assert/strict";
import { test } from "node:test";

import { installedBuild, releasedBuild } from "./appbuild.ts";

test("the app's build is read from its user agent, the latest from the release title", () => {
  assert.equal(installedBuild("Mozilla/5.0 (Linux; Android 14) Chrome/130 Mobile PashupatastraApp/0.1.4"), 4);
  assert.equal(installedBuild("Mozilla/5.0 (Linux; Android 14) Chrome/130 Mobile"), null);
  assert.equal(releasedBuild("Android app (test build 7)"), 7);
});
