import assert from "node:assert/strict";
import { test } from "node:test";

import { foldAudit } from "./fold.ts";

const line = (n: number, summary = "isolate_host: risk 67 → senior", actor = "dharma", kind = "policy_evaluation") => ({
  kind,
  summary,
  actor,
  at: `2026-09-12T10:${String(n).padStart(2, "0")}:00+00:00`,
});

test("a known run folds to one row carrying its count", () => {
  // Newest first, as the API serves it: 144 identical evaluations, then one
  // approval, then an evaluation of something else.
  const records = [
    ...Array.from({ length: 144 }, (_, i) => line(59 - (i % 60))),
    line(1, "approved isolate_host at tier senior", "human:operator", "approval"),
    line(0, "revoke_session: risk 31 → approval"),
  ];
  const folds = foldAudit(records);
  assert.equal(folds.length, 3);
  assert.equal(folds[0].count, 144);
  assert.equal(folds[1].count, 1);
  assert.equal(folds[2].count, 1);
});

test("no record is lost between input and output", () => {
  const records = [
    line(5), line(4), line(3),
    line(2, "approved isolate_host at tier senior", "human:operator", "approval"),
    line(1), line(0),
  ];
  const folds = foldAudit(records);
  const indices = folds.flatMap((f) => f.members.map((m) => m.index)).sort((a, b) => a - b);
  assert.deepEqual(indices, records.map((_, i) => i));
  assert.equal(folds.reduce((n, f) => n + f.count, 0), records.length);
});

test("identical lines separated by another record are not folded across it", () => {
  const records = [
    line(3), line(2),
    line(1, "approved isolate_host at tier senior", "human:operator", "approval"),
    line(0),
  ];
  const folds = foldAudit(records);
  assert.deepEqual(folds.map((f) => f.count), [2, 1, 1]);
});

test("the span of a fold is the earliest and latest record in the run", () => {
  const folds = foldAudit([line(9), line(4), line(1)]);
  assert.equal(folds[0].latest, line(9).at);
  assert.equal(folds[0].earliest, line(1).at);
});

test("a single record is a fold of one and is left alone", () => {
  const [only] = foldAudit([line(0)]);
  assert.equal(only.count, 1);
  assert.equal(only.members.length, 1);
});
