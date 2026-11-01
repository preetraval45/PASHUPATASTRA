import assert from "node:assert/strict";
import { test } from "node:test";

import { MATCH_PAIRS, PASSWORD_DUELS, PHISH_OR_LEGIT, URL_DETECTIVE, shuffled } from "./games.ts";
import { CARDS, TIERS } from "./questionbank.ts";

test("every game round explains its answer", () => {
  for (const r of [...PHISH_OR_LEGIT, ...URL_DETECTIVE, ...PASSWORD_DUELS]) assert.ok(r.why.length > 40, r.why);
});

test("both kinds of message appear in Phish or legit", () => {
  assert.ok(PHISH_OR_LEGIT.some((r) => r.phish));
  assert.ok(PHISH_OR_LEGIT.some((r) => !r.phish));
});

test("every URL answer is one of its options", () => {
  for (const r of URL_DETECTIVE) assert.ok(r.answer >= 0 && r.answer < r.options.length, r.url);
});

test("suspicious addresses use the reserved .example domain, never a live one", () => {
  const addresses = PHISH_OR_LEGIT.filter((r) => r.phish)
    .flatMap((r) => `${r.from} ${r.body}`.replace(/[\w.+-]+@/g, "").match(/\b[a-z0-9-]+(?:\.[a-z0-9-]+)+\b/gi) ?? [])
    .filter((a) => /[a-z]/i.test(a) && !/^\d/.test(a) && !/\.(html?|xlsx|docx|pdf|zip)$/i.test(a));
  for (const a of addresses) assert.match(a, /\.example$/i, a);
});

test("match pairs never repeat a term or a meaning", () => {
  assert.equal(new Set(MATCH_PAIRS.map((p) => p.term)).size, MATCH_PAIRS.length);
  assert.equal(new Set(MATCH_PAIRS.map((p) => p.meaning)).size, MATCH_PAIRS.length);
});

test("shuffling keeps every item and is the same for the same seed", () => {
  const a = shuffled(MATCH_PAIRS, 3);
  assert.deepEqual([...a].sort((x, y) => x.term.localeCompare(y.term)), [...MATCH_PAIRS].sort((x, y) => x.term.localeCompare(y.term)));
  assert.deepEqual(shuffled(MATCH_PAIRS, 3), a);
});

test("every practice level has questions, and none repeats", () => {
  for (const t of TIERS) assert.ok(CARDS.filter((c) => c.tier === t.id).length >= 6, t.id);
  assert.equal(new Set(CARDS.map((c) => c.q)).size, CARDS.length);
});
