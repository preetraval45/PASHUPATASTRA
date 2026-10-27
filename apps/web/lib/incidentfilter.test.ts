import assert from "node:assert/strict";
import { test } from "node:test";

import type { Incident, IncidentState } from "./api.ts";
import { applyQuery, hrefFor, parseQuery } from "./incidentfilter.ts";

const inc = (id: string, severity: Incident["severity"], state: IncidentState, opened_at: string) => ({
  id,
  severity,
  state,
  opened_at,
});

const list = [
  inc("a", "low", "detected", "2026-10-01T00:00:00Z"),
  inc("b", "critical", "resolved", "2026-10-02T00:00:00Z"),
  inc("c", "high", "escalated", "2026-10-03T00:00:00Z"),
];

test("an unknown value means everything, never an empty list", () => {
  const q = parseQuery({ severity: "catastrophic", status: "maybe", sort: "random" });
  assert.deepEqual(q, { severity: null, status: null, sort: "newest" });
  assert.deepEqual(applyQuery(list, q).map((i) => i.id), ["c", "b", "a"]);
});

test("escalated is open: a human owns it, it is not done", () => {
  const open = applyQuery(list, parseQuery({ status: "open" })).map((i) => i.id);
  assert.deepEqual(open, ["c", "a"]);
  assert.deepEqual(applyQuery(list, parseQuery({ status: "closed" })).map((i) => i.id), ["b"]);
});

test("severity sort puts critical first, newest within a severity", () => {
  assert.deepEqual(applyQuery(list, parseQuery({ sort: "severity" })).map((i) => i.id), ["b", "c", "a"]);
});

test("links drop defaults, so the unfiltered list is plain /incidents", () => {
  const q = parseQuery({ severity: "high" });
  assert.equal(hrefFor(q, { severity: null }), "/incidents");
  assert.equal(hrefFor(q, { sort: "severity" }), "/incidents?severity=high&sort=severity");
});
