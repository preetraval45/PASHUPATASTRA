import assert from "node:assert/strict";
import { test } from "node:test";

import { stageState, type StageKey } from "./timelinestages.ts";

// The smallest incident the logic reads: its state, its transitions, its plan and hypotheses.
const incident = (state: string, over: Record<string, unknown> = {}) =>
  ({ state, transitions: [], plan: [], hypotheses: [], ...over }) as never;
const record = (kind: string, summary = "ok", detail: Record<string, unknown> = {}) =>
  ({ at: "2026-11-01T00:00:00Z", kind, actor: "test", incident_ref: "INC-1", summary, detail }) as never;
const keys: StageKey[] = ["detection", "hypothesis", "plan", "approval", "execution", "verification"];

test("the stage the loop sits in is active, not done", () => {
  const i = incident("awaiting_approval", { hypotheses: [{}], plan: [{}] });
  assert.equal(stageState("approval", 3, [record("approval")], i), "active");
  assert.equal(stageState("plan", 2, [], i), "done");
  assert.equal(stageState("execution", 4, [], i), "pending");
});

test("a resolved incident that never verified shows verification as skipped, not done", () => {
  // Reaching resolved is the claim verification would justify; taking it as evidence would be circular.
  const i = incident("resolved", { transitions: [{ to_state: "resolved" }], plan: [{}], hypotheses: [{}] });
  assert.equal(stageState("verification", 5, [], i), "skipped");
});

test("a failed record marks its stage failed, whatever else is true", () => {
  const i = incident("rolled_back");
  assert.equal(stageState("execution", 4, [record("execution_result", "ok", { succeeded: false })], i), "failed");
  assert.equal(stageState("approval", 3, [record("approval", "denied block_ip: not now")], i), "failed");
});

test("a stage proven by a transition counts as done even with no audit records", () => {
  const i = incident("planned", { transitions: [{ to_state: "detected" }] });
  assert.equal(stageState("detection", 0, [], i), "done");
});

test("every stage gets one of the five states", () => {
  const i = incident("escalated");
  for (const [index, key] of keys.entries()) {
    assert.ok(["done", "failed", "active", "pending", "skipped"].includes(stageState(key, index, [], i)));
  }
});
