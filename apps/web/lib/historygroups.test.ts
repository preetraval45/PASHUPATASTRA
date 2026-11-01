import assert from "node:assert/strict";
import { test } from "node:test";

import { historyGroups } from "./historygroups.ts";

const now = new Date(2026, 10, 1, 15, 0).getTime();
const at = (daysAgo: number, hour = 12) => new Date(2026, 10, 1 - daysAgo, hour).getTime();

test("conversations fall under Today, Yesterday, Previous 7 days and Older, newest first", () => {
  const items = [
    { title: "old", updated: at(30) },
    { title: "today late", updated: at(0, 14) },
    { title: "today early", updated: at(0, 1) },
    { title: "yesterday", updated: at(1) },
    { title: "last week", updated: at(5) },
  ];
  const groups = historyGroups(items, now);
  assert.deepEqual(groups.map((g) => g.label), ["Today", "Yesterday", "Previous 7 days", "Older"]);
  assert.deepEqual(groups[0].items.map((i) => i.title), ["today late", "today early"]);
});

test("a search keeps only matching titles and drops empty groups", () => {
  const items = [
    { title: "What is phishing?", updated: at(0) },
    { title: "Ransomware defences", updated: at(3) },
  ];
  const groups = historyGroups(items, now, "PHISH");
  assert.equal(groups.length, 1);
  assert.equal(groups[0].items[0].title, "What is phishing?");
});
