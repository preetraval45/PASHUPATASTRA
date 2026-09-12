import assert from "node:assert/strict";
import { test } from "node:test";

import { observatoryState } from "./observatory.ts";

test("a failed /intel with no source asked for is offline, never a named feed", () => {
  for (const failure of [
    { kind: "unavailable" as const, status: 503 },
    { kind: "offline" as const, status: null },
    { kind: "missing" as const, status: 404 },
  ]) {
    assert.equal(observatoryState(failure, undefined), "offline");
  }
});

test("a 503 with a source asked for is still offline — the API did not say the source is unknown", () => {
  assert.equal(observatoryState({ kind: "unavailable", status: 503 }, "cisa-kev"), "offline");
});

test("only a 404 with a source named is an unknown source", () => {
  assert.equal(observatoryState({ kind: "missing", status: 404 }, "typo"), "unknown-source");
});

test("the word undefined can never be the source that is named", () => {
  // The bug as reported: the source is unset, the request failed, and the page
  // interpolated `undefined` into a sentence. The state for that pair is offline.
  const state = observatoryState({ kind: "unavailable", status: 503 }, undefined);
  assert.equal(state, "offline");
  assert.notEqual(`No feed named "${undefined}".`, "");
});
