/**
 * One request to the API, with a typed failure and a single retry (R99).
 *
 * Every page used to get `null` for a 404, a 503 and a connection refused
 * alike, and rendered all three as "API unreachable". The Observatory went one
 * worse and named the only failure it knew — `No feed named "undefined"` — for
 * a request that had simply failed. Pages need to know *which* thing happened,
 * so the failure carries a kind:
 *
 *   missing      the API answered and there is no such thing (404)
 *   unavailable  the API answered that it could not answer (5xx)
 *   offline      nothing answered at all
 *
 * A 5xx or a dropped connection is retried once after a short pause. Both
 * reviewers saw a first request fail and the next quietly succeed, and a page
 * that asks twice before declaring the API unreachable is not hiding anything —
 * the second failure still surfaces. A 404 is never retried: it is an answer.
 *
 * `fetchImpl` and `pause` exist so `node --test` can drive this without a
 * network; production callers leave both alone.
 */

export type FailureKind = "missing" | "unavailable" | "offline";

export interface Failure {
  kind: FailureKind;
  status: number | null;
}

export type Result<T> = { ok: true; data: T } | { ok: false; failure: Failure };

export const RETRY_AFTER_MS = 300;

export function classify(status: number | null): FailureKind {
  if (status === null) return "offline";
  if (status >= 500) return "unavailable";
  return "missing";
}

export interface RequestOptions {
  method?: "GET" | "POST";
  body?: unknown;
  fetchImpl?: typeof fetch;
  pause?: (ms: number) => Promise<void>;
}

const sleep = (ms: number) => new Promise<void>((resolve) => setTimeout(resolve, ms));

export async function request<T>(url: string, options: RequestOptions = {}): Promise<Result<T>> {
  const fetchImpl = options.fetchImpl ?? fetch;
  const pause = options.pause ?? sleep;
  const init: RequestInit = { cache: "no-store", method: options.method ?? "GET" };
  if (options.body !== undefined) {
    init.headers = { "Content-Type": "application/json" };
    init.body = JSON.stringify(options.body);
  }

  let last: Failure = { kind: "offline", status: null };
  for (let attempt = 0; attempt < 2; attempt += 1) {
    if (attempt > 0) await pause(RETRY_AFTER_MS);
    try {
      const response = await fetchImpl(url, init);
      if (response.ok) return { ok: true, data: (await response.json()) as T };
      last = { kind: classify(response.status), status: response.status };
      if (last.kind === "missing") return { ok: false, failure: last };
    } catch {
      last = { kind: "offline", status: null };
    }
  }
  return { ok: false, failure: last };
}
