"use client";

import { useEffect } from "react";

/**
 * Draws the causal chain once, so a reader watches the dots being connected
 * rather than arriving after the fact.
 *
 * Three constraints shape all of this, and each one rules out the obvious
 * implementation.
 *
 * **The chain is complete in the DOM from the first paint.** Nothing here
 * creates, reorders or reveals content — the markup is finished before this
 * runs, and all this does is add one class that lets CSS animate properties
 * that were already at their final values. If the JavaScript never runs, never
 * loads, or throws, the page is the finished chain. Phase 5's rule is that
 * nothing new delays real data, and a reveal that *is* the rendering path is a
 * spinner wearing a costume.
 *
 * **No text is unreadable at any point.** That rules out the usual fade-in:
 * text at opacity 0.3 is text you cannot read, and half a second of it on every
 * incident page is half a second of a console being decorative during an
 * incident. So nothing animates on the text at all. What moves is the rail
 * drawing downward and each numbered marker lighting as the line reaches it —
 * every word at full contrast the entire time.
 *
 * **Once, and not again on that page.** Keyed by incident id in
 * `sessionStorage`, so returning from an entity page does not replay it. An
 * animation that repeats stops being a reveal and becomes a tic.
 */

const KEY = "pashupatastra:chain:seen";

export function ChainReveal({ incidentId }: { incidentId: string }) {
  useEffect(() => {
    const chain = document.querySelector<HTMLElement>("[data-chain]");
    if (!chain) return;

    // Respected here as well as in CSS. The media query already renders it
    // complete and instant, but not adding the class at all means no animation
    // is even queued — a reader who asked for no motion should not be relying
    // on a stylesheet to cancel one.
    if (window.matchMedia?.("(prefers-reduced-motion: reduce)").matches) return;

    let seen: string[] = [];
    try {
      seen = JSON.parse(window.sessionStorage.getItem(KEY) ?? "[]");
    } catch {
      // A private window can throw rather than return null. Falling through
      // with an empty list plays it once, which is the right failure: the
      // animation is additive, so the cost of getting this wrong is a repeat,
      // not a broken page.
      seen = [];
    }
    if (Array.isArray(seen) && seen.includes(incidentId)) return;

    chain.classList.add("chain-building");

    try {
      window.sessionStorage.setItem(
        KEY,
        JSON.stringify([...(Array.isArray(seen) ? seen : []), incidentId].slice(-20)),
      );
    } catch {
      /* the animation already ran; remembering is the optional half */
    }
  }, [incidentId]);

  return null;
}
