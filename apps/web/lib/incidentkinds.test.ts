import assert from "node:assert/strict";
import { test } from "node:test";

import { headline, isPast, isReal, kindOf, parseKind } from "./incidentkinds.ts";

test("the kind is read from the id the API built", () => {
  assert.equal(kindOf("LIVE-KEV-CVE-2026-1000"), "KEV");
  assert.equal(kindOf("PAST-BREACH-adobe"), "BREACH");
  assert.equal(kindOf("LIVE-C2-amos-20261102"), "C2");
  assert.equal(kindOf("INC-2026-0901"), null);
});

test("a written scenario is never taken for a real incident", () => {
  assert.equal(isReal("INC-2026-0904"), false);
  assert.equal(isReal("LIVE-RW-pear-20261102"), true);
  assert.equal(isPast("PAST-KEV-CVE-2021-44228"), true);
  assert.equal(isPast("LIVE-KEV-CVE-2026-1000"), false);
});

test("a headline is the first sentence, cut at a word", () => {
  assert.equal(headline("One claim. Then detail."), "One claim.");
  const long = headline("word ".repeat(60), 30);
  assert.ok(long.endsWith("…") && long.length <= 31 && !long.includes("wor…"));
});

test("an unknown kind in a link means every kind", () => {
  assert.equal(parseKind("kev"), "KEV");
  assert.equal(parseKind(["c2"]), "C2");
  assert.equal(parseKind("nonsense"), null);
  assert.equal(parseKind(undefined), null);
});
