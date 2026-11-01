import assert from "node:assert/strict";
import { test } from "node:test";

import { daysUntil } from "./duedate.ts";

test("days until a due date count calendar days, negative once it has passed", () => {
  const now = new Date(2026, 10, 1, 23, 30);
  assert.equal(daysUntil("2026-11-01", now), 0);
  assert.equal(daysUntil("2026-11-08", now), 7);
  assert.equal(daysUntil("2026-10-30", now), -2);
});
