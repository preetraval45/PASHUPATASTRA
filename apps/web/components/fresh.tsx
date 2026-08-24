"use client";

import { useEffect } from "react";

/**
 * Marks entries that arrived since this visitor last looked.
 *
 * R61 is specific about the order — **the entry renders first and is
 * highlighted after, never the reverse** — so this is deliberately not a prop
 * on the row. The server renders the list with no highlight in it at all, and
 * this runs after paint and adds a class to the rows that qualify. A highlight
 * baked into the markup would arrive *with* the row, which means a visitor's
 * first ever page load would flash every entry as new, and a feed that had not
 * moved in a day would look like it had just landed.
 *
 * The watermark is per browser, in `sessionStorage`. It is a convenience, not a
 * record: there are no accounts, nothing about it reaches the server, and it is
 * gone when the tab closes. Reads and writes are wrapped because a private
 * window can throw on access rather than return null, and a page that fails to
 * render because it could not remember a timestamp has its priorities backwards.
 */

const KEY = "pashupatastra:observatory:seen";

export function Fresh({ newest }: { newest: string | null }) {
  useEffect(() => {
    if (!newest) return;

    let seen: string | null = null;
    try {
      seen = window.sessionStorage.getItem(KEY);
    } catch {
      // Private window, or site data blocked. Nothing is marked, which is the
      // correct outcome: without a watermark there is no "since when".
      return;
    }

    // First visit in this tab establishes the watermark and highlights nothing.
    // Highlighting everything on a first load would make the effect meaningless
    // — the point is *what changed*, and on a first load nothing has.
    if (seen) {
      const rows = document.querySelectorAll<HTMLElement>("[data-entry-at]");
      for (const row of rows) {
        const at = row.dataset.entryAt;
        if (at && at > seen) row.classList.add("just-landed");
      }
    }

    try {
      if (!seen || newest > seen) window.sessionStorage.setItem(KEY, newest);
    } catch {
      /* nothing to do; the highlight above already ran */
    }
  }, [newest]);

  return null;
}
