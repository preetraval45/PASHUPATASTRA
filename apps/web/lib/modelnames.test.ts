import assert from "node:assert/strict";
import { test } from "node:test";

import { isShown, servedName, shownEntries, shownName } from "./modelnames.ts";

test("every model is shown by its form's name, with no version", () => {
  for (const key of ["shailaputri-v0", "mahagauri-v2 + 3σ agreement", "katyayani (trained on RCAEval, zero-shot)"]) {
    assert.doesNotMatch(shownName(key), /\bv\d\b|-v\d/i, key);
  }
  assert.equal(shownName("mahagauri-v2 + 3σ agreement"), "Mahagauri");
  assert.equal(shownName("bm25"), "bm25"); // baselines keep their names
  assert.equal(shownName("some-model-v3"), "some-model"); // an unmapped key still loses its version
});

test("superseded variants are hidden, the current one and baselines kept", () => {
  const rows = { "mahagauri-v0": 1, "mahagauri-v1 + 3σ agreement": 2, "mahagauri-v2 + 3σ agreement": 3, "back within 3σ": 4 };
  assert.deepEqual(shownEntries(rows).map(([k]) => k), ["mahagauri-v2 + 3σ agreement", "back within 3σ"]);
  assert.equal(isShown("chandraghanta-v1 (either)"), false);
});

test("a served model id reads as its form", () => {
  assert.equal(servedName("sati-skandamata-serve-v0"), "Skandamata");
  assert.equal(servedName("llama3"), "llama3");
});
