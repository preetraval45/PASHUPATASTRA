import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";

import { classify, scan, split } from "./indicators.ts";

/**
 * R78: the same cases the Python classifier runs, against this one.
 *
 * Read from `packages/core/pashupatastra/indicators.json` rather than copied,
 * because a copy is how two implementations start disagreeing about what an
 * indicator is — and the disagreement that matters is the one where this side
 * marks up something the lookup then refuses.
 */
const CASES = JSON.parse(
  readFileSync(new URL("../../../packages/core/pashupatastra/indicators.json", import.meta.url), "utf-8"),
);

test("classify matches the shared cases", () => {
  for (const testCase of CASES.classify) {
    assert.equal(
      classify(testCase.value),
      testCase.kind,
      `${JSON.stringify(testCase.value)} — ${testCase.why ?? ""}`,
    );
  }
});

test("scan matches the shared cases", () => {
  for (const testCase of CASES.scan) {
    const found = scan(testCase.text).map((span) => [span.value, span.kind]);
    assert.deepEqual(found, testCase.spans, `${testCase.text} — ${testCase.why ?? ""}`);
  }
});

test("a span knows where it sat, so the markup can be exact", () => {
  const text = "network_flow:ws-0148->198.51.100.74:8443";
  const [span] = scan(text);
  assert.equal(text.slice(span.start, span.end), span.value);
});

test("split covers the whole string and loses nothing", () => {
  for (const testCase of CASES.scan) {
    const rejoined = split(testCase.text)
      .map((piece) => ("value" in piece ? piece.value : piece.text))
      .join("");
    assert.equal(rejoined, testCase.text);
  }
});

test("an unknown suffix is not a domain rather than a guess", () => {
  assert.equal(classify("thing.zzzzz"), null);
  assert.equal(classify("thing.com"), "domain");
});

test("no entity key in this estate is ever an indicator", () => {
  for (const key of [
    "account:j.rivera",
    "host:ws-0148",
    "asset:oauth-app-Rep0rt-Sync",
    "process:app-07/schtasks",
  ]) {
    assert.equal(classify(key), null, key);
  }
});
