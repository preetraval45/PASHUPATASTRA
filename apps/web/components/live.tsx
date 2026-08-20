"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";

const INTERVAL_MS = 15_000;

/**
 * Refreshes server components on an interval.
 *
 * Three rules, all of them about trust rather than convenience:
 *
 *  1. **The age of the data is always on screen.** A dashboard that stopped
 *     updating looks identical to one where nothing is happening, and those
 *     need opposite responses.
 *  2. **It can be paused, and pausing is obvious.** Auto-refresh mid-read yanks
 *     content out from under an operator who is trying to understand something.
 *  3. **It stops when the tab is hidden.** Polling a backgrounded tab costs the
 *     API real work for nobody's benefit.
 */
export function Live() {
  const router = useRouter();
  const [paused, setPaused] = useState(false);
  const [updatedAt, setUpdatedAt] = useState(() => Date.now());
  const [, forceTick] = useState(0);
  const pausedRef = useRef(paused);
  pausedRef.current = paused;

  useEffect(() => {
    const refresh = () => {
      if (pausedRef.current || document.hidden) return;
      router.refresh();
      setUpdatedAt(Date.now());
    };

    const poll = setInterval(refresh, INTERVAL_MS);
    // Re-render once a second so the age counts up rather than sitting stale
    // between refreshes — the number itself has to look alive.
    const tick = setInterval(() => forceTick((n) => n + 1), 1000);

    // Coming back to the tab, the first thing wanted is current data.
    const onVisible = () => {
      if (!document.hidden) refresh();
    };
    document.addEventListener("visibilitychange", onVisible);

    return () => {
      clearInterval(poll);
      clearInterval(tick);
      document.removeEventListener("visibilitychange", onVisible);
    };
  }, [router]);

  const seconds = Math.floor((Date.now() - updatedAt) / 1000);
  const stale = seconds > INTERVAL_MS / 1000 + 10;

  return (
    <div className="flex items-center gap-2 text-xs">
      <span
        className={
          paused
            ? "text-[rgb(var(--warn))]"
            : stale
              ? "text-[rgb(var(--warn))]"
              : "text-[rgb(var(--faint))]"
        }
        aria-live="polite"
      >
        {/* Same rule: one base string, an optional prefix. */}
        <span className="hidden xl:inline">{paused ? "updates " : "updated "}</span>
        {paused ? "paused" : seconds < 5 ? "just now" : `${seconds}s ago`}
      </span>
      <button
        type="button"
        onClick={() => {
          if (paused) {
            router.refresh();
            setUpdatedAt(Date.now());
          }
          setPaused((p) => !p);
        }}
        aria-pressed={paused}
        className="focusable inline-flex min-h-6 items-center rounded border border-[rgb(var(--edge))] px-2 text-[rgb(var(--muted))] hover:text-[rgb(var(--ink))]"
      >
        {paused ? "resume" : "pause"}
      </button>
    </div>
  );
}
