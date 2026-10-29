import assert from "node:assert/strict";
import { test } from "node:test";

import { arranged, MODULES } from "./training.ts";

const all = MODULES.flatMap((m) => m.quiz);

test("arranging keeps every question's right answer and options", () => {
  for (const q of all) {
    const a = arranged(q);
    assert.equal(a.options[a.answer], q.options[q.answer]);
    assert.deepEqual([...a.options].sort(), [...q.options].sort());
    assert.deepEqual(arranged(q), a, "the same order every time");
  }
});

test("no answer position is a shortcut: none holds more than half the right answers", () => {
  const counts = new Map<number, number>();
  for (const q of all) {
    const at = arranged(q).answer;
    counts.set(at, (counts.get(at) ?? 0) + 1);
  }
  for (const [position, n] of counts) {
    assert.ok(n / all.length <= 0.5, `position ${position} holds ${n} of ${all.length} right answers`);
  }
});
