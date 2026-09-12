/**
 * What the Observatory shows when `/intel` did not answer with data (R101).
 *
 * Kept out of the page so it can be tested without rendering one. The rule:
 * "no feed named X" is said only when a source was asked for *and* the API
 * said there is no such thing. Anything else — a 5xx, nothing answering, or a
 * failure with no source in the URL — is the offline state. The old page had
 * only `null` to go on and printed `No feed named "undefined"` for a request
 * that had simply failed, on the one page whose claim is that the data is real.
 */

import type { Failure } from "@/lib/http";

export type ObservatoryState = "offline" | "unknown-source";

export function observatoryState(failure: Failure, source: string | undefined): ObservatoryState {
  if (failure.kind === "missing" && source) return "unknown-source";
  return "offline";
}
