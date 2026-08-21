"use client";

/**
 * What you have done here before, and how to make that stop.
 *
 * Renders nothing until there is something to render. A visitor who has never
 * played sees no mention of tokens, storage or streaks — telling them about an
 * identifier they do not have is both noise and slightly alarming.
 *
 * The forget button is not a courtesy. What is held is one opaque token and the
 * rows it keys; with the token gone there is nothing to join those rows to, so
 * removing it locally *is* the deletion path rather than a request for one.
 */

import { useCallback, useEffect, useState } from "react";

import { getProgress, type PlayerProgress } from "@/lib/api";
import { forgetPlayer, readPlayer } from "@/lib/player";
import { Panel } from "@/components/ui";

export function Progress({ scenarios }: { scenarios: number }) {
  const [progress, setProgress] = useState<PlayerProgress | null>(null);
  const [durable, setDurable] = useState(true);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    // `readPlayer`, never `ensurePlayer`: rendering a page must not mint an
    // identifier. One is created when an attempt is submitted, which is the
    // first moment there is anything to remember.
    const player = readPlayer();
    if (!player) {
      setLoaded(true);
      return;
    }
    getProgress(player).then((result) => {
      if (result) {
        setProgress(result.player);
        setDurable(result.durable);
      }
      setLoaded(true);
    });
  }, []);

  const forget = useCallback(() => {
    forgetPlayer();
    setProgress(null);
  }, []);

  if (!loaded || !progress || progress.attempts === 0) return null;

  return (
    <Panel title="Your record" aside={`${progress.attempts} attempts`}>
      <dl className="flex flex-wrap gap-x-8 gap-y-3">
        <Figure label="streak" value={progress.streak} />
        <Figure label="best streak" value={progress.best_streak} />
        <Figure
          label="cleared"
          value={`${progress.cleared.length}/${scenarios}`}
        />
      </dl>

      {!durable && (
        <p className="mt-4 text-xs text-[rgb(var(--warn))]">
          Not stored durably — this will be lost when the server restarts.
        </p>
      )}

      <p className="mt-4 text-xs text-[rgb(var(--faint))]">
        Kept against a random token your browser generated. No account, no name,
        nothing that identifies you.{" "}
        <button
          type="button"
          onClick={forget}
          className="focusable rounded underline decoration-dotted underline-offset-2 hover:text-[rgb(var(--ink))]"
        >
          Forget my record
        </button>
        .
      </p>
    </Panel>
  );
}

function Figure({ label, value }: { label: string; value: number | string }) {
  return (
    <div>
      <dt className="label mb-1">{label}</dt>
      <dd className="text-2xl font-semibold tabular-nums">{value}</dd>
    </div>
  );
}
