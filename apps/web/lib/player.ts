/**
 * The token that lets a score survive a visit, and nothing else.
 *
 * Generated in the browser, kept in `localStorage`, sent with an attempt. The
 * server can tell that two attempts came from the same browser and can tell
 * nothing else — not who, not where, not whether it is even the same person.
 * Clearing site data ends the association permanently, because there is nothing
 * on the other side to join it to.
 *
 * A UUID rather than anything derived from the visitor. A fingerprint would be
 * stabler and is the wrong trade: the point is to be forgettable.
 */

const KEY = "pashupatastra.player";
const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;

/**
 * Read the token, or `null` — never create one as a side effect of asking.
 *
 * A page that mints an identifier just because it rendered has decided on the
 * visitor's behalf. `ensurePlayer` is the call that decides, and it is made
 * when somebody submits an attempt.
 */
export function readPlayer(): string | null {
  try {
    const value = window.localStorage.getItem(KEY);
    return value && UUID.test(value) ? value : null;
  } catch {
    // Private mode, or storage disabled. Playing still works; the score simply
    // does not outlive the tab, which is a smaller loss than an error.
    return null;
  }
}

/** Read the token, creating one if there is none. Called when an attempt is
 *  submitted — the first moment there is anything to remember. */
export function ensurePlayer(): string | null {
  const existing = readPlayer();
  if (existing) return existing;
  try {
    const fresh =
      typeof crypto !== "undefined" && "randomUUID" in crypto
        ? crypto.randomUUID()
        : null;
    if (!fresh || !UUID.test(fresh)) return null;
    window.localStorage.setItem(KEY, fresh);
    return fresh;
  } catch {
    return null;
  }
}

/** Forget everything. The whole deletion path, because the whole of what is
 *  held is one token and the rows it keys — with nothing to join them to, an
 *  orphaned row is not a record of anybody. */
export function forgetPlayer(): void {
  try {
    window.localStorage.removeItem(KEY);
  } catch {
    /* nothing to forget */
  }
}
