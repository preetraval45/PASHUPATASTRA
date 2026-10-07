/**
 * Is this request a reader arriving at a page, or the machinery talking to
 * itself?
 *
 * Separated from `middleware.ts` so it can be tested without a Next runtime,
 * and because the answer is the whole meaning of the "page renders" figure on
 * `/impact`. Get it wrong one way and the number under-reports; get it wrong
 * the other way and it measures how long tabs stay open.
 *
 * The two shapes were measured against a real browser, not inferred:
 *
 * | what happened                      | `Sec-Fetch-Dest` | `Next-Url`      |
 * | ---------------------------------- | ---------------- | --------------- |
 * | typed the URL, or reloaded         | `document`       | absent          |
 * | clicked a link to another route    | `empty`          | the route left  |
 * | `router.refresh()` from `<Live />` | `empty`          | absent          |
 * | the duplicate fetch beside a nav   | `empty`          | absent          |
 *
 * So: a document load is an arrival, and a fetch is an arrival only when it
 * names a route the reader is coming *from* that is not the one being asked
 * for. Everything else is a re-render of a page already counted.
 */
export function isAnArrival(headers: {
  get(name: string): string | null;
}, pathname: string): boolean {
  if (headers.get("Sec-Fetch-Dest") === "document") return true;
  const from = headers.get("Next-Url");
  return from !== null && from !== pathname;
}
