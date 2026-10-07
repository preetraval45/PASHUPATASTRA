import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";

import { isAnArrival } from "./arrival.ts";

/** A stand-in for `request.headers`. */
const headers = (h: Record<string, string>) => ({
  get: (name: string) => h[name] ?? h[name.toLowerCase()] ?? null,
});

test("a fresh page load is an arrival", () => {
  assert.equal(isAnArrival(headers({ "Sec-Fetch-Dest": "document" }), "/overview"), true);
});

test("clicking through to another route is an arrival", () => {
  const h = headers({ "Sec-Fetch-Dest": "empty", "Next-Url": "/overview" });
  assert.equal(isAnArrival(h, "/attack"), true);
});

test("a live panel refreshing the page it is on is not an arrival", () => {
  // The one that matters. `<Live />` refreshes every 15 seconds; if this
  // returned true, "page renders" would count how long a tab stayed open
  // and would climb fastest wherever the figure itself is displayed.
  const h = headers({ "Sec-Fetch-Dest": "empty" });
  assert.equal(isAnArrival(h, "/overview"), false);
});

test("the duplicate fetch alongside a navigation is not counted twice", () => {
  // Next asks for the new route twice: once naming the route being left,
  // once with no `Next-Url`. One arrival, one count.
  const first = headers({ "Sec-Fetch-Dest": "empty", "Next-Url": "/overview" });
  const second = headers({ "Sec-Fetch-Dest": "empty" });
  assert.equal(isAnArrival(first, "/"), true);
  assert.equal(isAnArrival(second, "/"), false);
});

test("a refresh that names the route it is already on is not an arrival", () => {
  const h = headers({ "Sec-Fetch-Dest": "empty", "Next-Url": "/impact" });
  assert.equal(isAnArrival(h, "/impact"), false);
});

test("the matcher excludes every path with a file extension", () => {
  // The bug this replaced: the old matcher named the formats to exclude and
  // did not name `.webp`, the logo's format, present on every page — so
  // every visit was counted twice. A rule about dots cannot go stale when
  // somebody adds an asset in a new format.
  const text = readFileSync(new URL("../middleware.ts", import.meta.url), "utf8");
  const match = text.match(/matcher: \["(.+?)"\]/);
  assert.ok(match, "middleware.ts declares a matcher");
  const matcher = new RegExp(`^${match[1].replace(/\\/g, "\\")}$`);
  for (const asset of ["/logo.webp", "/icon.png", "/sitemap.xml", "/a/b/c.avif"]) {
    assert.equal(matcher.test(asset), false, `${asset} must not be counted`);
  }
  for (const page of ["/", "/overview", "/incidents/INC-2026-0903", "/blue-team"]) {
    assert.equal(matcher.test(page), true, `${page} must be counted`);
  }
});
