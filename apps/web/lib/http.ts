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

/** Per attempt. A read the API cannot answer in ten seconds is unavailable —
 *  the measured cost of the one slow read (R99) was 5 to 30 seconds, and a
 *  page that waited the full thirty and then tried again would have spent a
 *  minute on a palette index before it could show anything. */
export const TIMEOUT_MS = 10_000;

export interface RequestOptions {
  method?: "GET" | "POST";
  body?: unknown;
  /** Try once more on a 5xx or a dropped connection. Default true. */
  retry?: boolean;
  /** Per-attempt ceiling in milliseconds. Default `TIMEOUT_MS`. */
  timeoutMs?: number;
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

  const attempts = options.retry === false ? 1 : 2;
  const timeoutMs = options.timeoutMs ?? TIMEOUT_MS;
  let last: Failure = { kind: "offline", status: null };
  for (let attempt = 0; attempt < attempts; attempt += 1) {
    if (attempt > 0) await pause(RETRY_AFTER_MS);
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), timeoutMs);
    try {
      const response = await fetchImpl(url, { ...init, signal: controller.signal });
      if (response.ok) return { ok: true, data: (await response.json()) as T };
      last = { kind: classify(response.status), status: response.status };
      if (last.kind === "missing") return { ok: false, failure: last };
    } catch {
      // A timeout and a refused connection are the same thing to the page:
      // nothing usable answered. Both are `offline`, and both are retried once.
      last = { kind: "offline", status: null };
    } finally {
      clearTimeout(timer);
    }
  }
  return { ok: false, failure: last };
}
