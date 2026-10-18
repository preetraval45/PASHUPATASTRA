/**
 * The course's content holds together: a quiz whose answer points past its
 * options would mark every learner wrong, and a malformed technique id would
 * link to a page that does not exist.
 */
import assert from "node:assert/strict";
import test from "node:test";

import { MODULES, PASS_MARK } from "./training.ts";

test("module slugs are unique", () => {
  const slugs = MODULES.map((m) => m.slug);
  assert.equal(new Set(slugs).size, slugs.length);
});

test("every answer points at one of its options", () => {
  for (const m of MODULES) {
    for (const q of m.quiz) {
      assert.ok(q.answer >= 0 && q.answer < q.options.length, `${m.slug}: ${q.q}`);
      assert.ok(q.why.length > 20, `${m.slug}: an answer with no reason teaches nothing`);
    }
  }
});

test("every module teaches, applies and tests", () => {
  for (const m of MODULES) {
    assert.ok(m.lessons.length > 0, m.slug);
    assert.ok(m.realLife.length > 0, m.slug);
    // At least as many questions as it takes for the pass mark to mean something.
    assert.ok(m.quiz.length >= 4, m.slug);
    assert.ok(Math.ceil(m.quiz.length * PASS_MARK) < m.quiz.length + 1, m.slug);
  }
});

test("ATT&CK ids are well formed", () => {
  for (const m of MODULES) {
    for (const t of m.attack ?? []) assert.match(t.id, /^T\d{4}(\.\d{3})?$/, `${m.slug}: ${t.id}`);
  }
});
