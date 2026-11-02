import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";

import { MODULES, PASS_MARK } from "./training.ts";

const keys = JSON.parse(readFileSync(new URL("../../../services/api/app/quizkeys.json", import.meta.url), "utf-8"));

test("the API marks against the same questions and answers the site shows (run scripts/exportquiz.mjs)", () => {
  assert.equal(keys.pass_mark, PASS_MARK);
  for (const m of MODULES) {
    const served = keys.modules[m.slug];
    assert.ok(served, `${m.slug} has no answer key`);
    assert.deepEqual(
      served.map((q: { q: string; answer: string }) => [q.q, q.answer]),
      m.quiz.map((q) => [q.q, q.options[q.answer]]),
      `${m.slug}'s key is out of date`,
    );
  }
  assert.equal(Object.keys(keys.modules).length, MODULES.length);
});
