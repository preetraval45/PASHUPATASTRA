import assert from "node:assert/strict";
import { test } from "node:test";

import { classify, request } from "./http.ts";

const reply = (status: number, body: unknown = {}) =>
  ({ ok: status >= 200 && status < 300, status, json: async () => body }) as Response;

function scripted(responses: (Response | Error)[]) {
  const calls: string[] = [];
  const fetchImpl = (async (url: string) => {
    calls.push(url);
    const next = responses.shift();
    if (next instanceof Error) throw next;
    if (!next) throw new Error("no more scripted responses");
    return next;
  }) as unknown as typeof fetch;
  return { fetchImpl, calls };
}

const noPause = async () => {};

test("a 503 followed by a 200 is the 200, and the page never learns", async () => {
  const { fetchImpl, calls } = scripted([reply(503), reply(200, { fine: true })]);
  const result = await request<{ fine: boolean }>("/x", { fetchImpl, pause: noPause });
  assert.deepEqual(result, { ok: true, data: { fine: true } });
  assert.equal(calls.length, 2);
});

test("a dropped connection is retried once, and a second drop is offline", async () => {
  const { fetchImpl, calls } = scripted([new Error("ECONNREFUSED"), new Error("ECONNREFUSED")]);
  const result = await request("/x", { fetchImpl, pause: noPause });
  assert.deepEqual(result, { ok: false, failure: { kind: "offline", status: null } });
  assert.equal(calls.length, 2);
});

test("a 404 is an answer and is never retried", async () => {
  const { fetchImpl, calls } = scripted([reply(404), reply(200)]);
  const result = await request("/x", { fetchImpl, pause: noPause });
  assert.deepEqual(result, { ok: false, failure: { kind: "missing", status: 404 } });
  assert.equal(calls.length, 1);
});

test("two 5xx in a row surface as unavailable with the last status", async () => {
  const { fetchImpl } = scripted([reply(503), reply(502)]);
  const result = await request("/x", { fetchImpl, pause: noPause });
  assert.deepEqual(result, { ok: false, failure: { kind: "unavailable", status: 502 } });
});

test("the retry waits before asking again", async () => {
  const waited: number[] = [];
  const { fetchImpl } = scripted([reply(500), reply(200)]);
  await request("/x", { fetchImpl, pause: async (ms) => { waited.push(ms); } });
  assert.deepEqual(waited, [300]);
});

test("classify names the three kinds and nothing else", () => {
  assert.equal(classify(null), "offline");
  assert.equal(classify(503), "unavailable");
  assert.equal(classify(404), "missing");
  assert.equal(classify(422), "missing");
});

test("retry: false asks exactly once", async () => {
  const { fetchImpl, calls } = scripted([reply(503), reply(200)]);
  const result = await request("/x", { fetchImpl, pause: noPause, retry: false });
  assert.equal(calls.length, 1);
  assert.deepEqual(result, { ok: false, failure: { kind: "unavailable", status: 503 } });
});

test("a request that outlives its timeout is offline, not a hang", async () => {
  const fetchImpl = ((_url: string, init: RequestInit) =>
    new Promise((_, reject) => {
      init.signal?.addEventListener("abort", () => reject(new Error("aborted")));
    })) as unknown as typeof fetch;
  const started = Date.now();
  const result = await request("/x", { fetchImpl, pause: noPause, retry: false, timeoutMs: 20 });
  assert.deepEqual(result, { ok: false, failure: { kind: "offline", status: null } });
  assert.ok(Date.now() - started < 1000, "did not wait on the hung request");
});
