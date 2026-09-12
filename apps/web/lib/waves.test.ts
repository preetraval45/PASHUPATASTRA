import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";

/**
 * R100: the incident page fetches in two waves, not six.
 *
 * Read from the source rather than measured, because the number of sequential
 * round trips is a property of how the page is written: every top-level
 * `await` on an API call in the component is one more wait in line. Two
 * `Promise.all`s are allowed — the id-only wave and the wave that needs what
 * the first returned — and nothing else may be awaited on its own.
 */
const source = readFileSync(new URL("../app/incidents/[id]/page.tsx", import.meta.url), "utf-8");
const body = source.slice(source.indexOf("export default async function IncidentDetailPage"));

test("the incident page awaits exactly two Promise.all waves", () => {
  const waves = body.match(/await Promise\.all\(/g) ?? [];
  assert.equal(waves.length, 2);
});

test("no API call is awaited on its own between the waves", () => {
  // `await params` and the not-found fallback (`await getActions()` on the
  // error path only) are the two permitted solitary awaits.
  const solitary = (body.match(/await (?!Promise\.all\(|params\b)[a-zA-Z]+\(/g) ?? []).filter(
    (call) => call !== "await getActions(",
  );
  assert.deepEqual(solitary, []);
});

test("the metadata shares the page's incident fetch", () => {
  assert.match(source, /const incidentOnce = cache\(/);
  assert.match(source, /generateMetadata[\s\S]*?await incidentOnce\(id\)/);
});
