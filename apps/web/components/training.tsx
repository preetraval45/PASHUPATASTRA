"use client";

/**
 * The training board: every drill, with this browser's record against it.
 *
 * The record comes from `/game/progress/{player}`, keyed by the anonymous token
 * in `lib/player.ts`. Reading the page never creates that token — a first-time
 * visitor simply sees every drill as not started.
 */

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import { Badge, statusForSeverity } from "@/components/ui";
import { getProgress, type PlayerProgress } from "@/lib/api";
import { forgetPlayer, readPlayer } from "@/lib/player";

type Scenario = {
  incident_id: string;
  severity: string;
  opened_at: string;
  opening: string;
  steps: number;
};

export function TrainingBoard({ scenarios }: { scenarios: Scenario[] }) {
  const [progress, setProgress] = useState<PlayerProgress | null>(null);

  useEffect(() => {
    const player = readPlayer();
    if (!player) return;
    getProgress(player).then((result) => result && setProgress(result.player));
  }, []);

  const forget = useCallback(() => {
    forgetPlayer();
    setProgress(null);
  }, []);

  const cleared = new Set(progress?.cleared ?? []);
  const done = scenarios.filter((s) => cleared.has(s.incident_id)).length;
  const share = scenarios.length ? Math.round((done / scenarios.length) * 100) : 0;

  return (
    <div className="space-y-8">
      <section className="grid gap-3 sm:grid-cols-4">
        <Tile label="Drills" value={scenarios.length} />
        <Tile label="Cleared" value={`${done}/${scenarios.length}`} />
        <Tile label="Streak" value={progress?.streak ?? 0} hint={progress ? `best ${progress.best_streak}` : "no attempts yet"} />
        <div className="rounded-xl border border-[rgb(var(--edge))] bg-[rgb(var(--panel))] p-4">
          <p className="label">Progress</p>
          <p className="tnum mt-1 text-2xl font-semibold">{share}%</p>
          <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-[rgb(var(--raised))]" aria-hidden="true">
            <div className="h-full rounded-full bg-[rgb(var(--astra))] transition-all" style={{ width: `${share}%` }} />
          </div>
        </div>
      </section>

      <section>
        <div className="mb-3 flex items-baseline justify-between">
          <h2 className="text-lg font-semibold tracking-tight">Drills</h2>
          {progress && progress.attempts > 0 && (
            <button
              type="button"
              onClick={forget}
              className="focusable rounded text-xs text-[rgb(var(--faint))] underline decoration-dotted underline-offset-2 hover:text-[rgb(var(--ink))]"
            >
              Forget my record
            </button>
          )}
        </div>
        {scenarios.length === 0 ? (
          <p className="rounded-xl border border-dashed border-[rgb(var(--edge))] p-6 text-sm text-[rgb(var(--faint))]">
            No drills are loaded right now.
          </p>
        ) : (
          <ul className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
            {scenarios.map((scenario, index) => {
              const best = progress?.best?.[scenario.incident_id];
              const isCleared = cleared.has(scenario.incident_id);
              return (
                <li key={scenario.incident_id}>
                  <Link
                    href={`/blue-team/${encodeURIComponent(scenario.incident_id)}`}
                    data-drill={scenario.incident_id}
                    className="focusable lift group flex h-full flex-col rounded-xl border border-[rgb(var(--edge-strong))] bg-[rgb(var(--panel))] p-5 transition hover:border-[rgb(var(--astra))]/50"
                  >
                    <span className="flex items-center gap-2">
                      <span className="label">Drill {index + 1}</span>
                      <span className="ml-auto">
                        <Badge status={statusForSeverity(scenario.severity)}>{scenario.severity}</Badge>
                      </span>
                    </span>
                    {/* The opening alert and nothing else — a summary would
                        answer the exercise before it opened. */}
                    <span className="mt-3 flex-1 text-[0.9375rem] leading-snug text-[rgb(var(--ink))]">
                      {scenario.opening}
                    </span>
                    <span className="mt-4 flex items-center gap-3 text-xs text-[rgb(var(--faint))]">
                      <span>{scenario.steps} steps to reconstruct</span>
                      <span className="ml-auto">
                        {isCleared ? (
                          <Badge status="ok">cleared · best {best ?? "—"}</Badge>
                        ) : best !== undefined ? (
                          <Badge status="warning">best {best}/100</Badge>
                        ) : (
                          <span className="text-[rgb(var(--astra))] group-hover:underline">Start drill →</span>
                        )}
                      </span>
                    </span>
                  </Link>
                </li>
              );
            })}
          </ul>
        )}
      </section>
    </div>
  );
}

function Tile({ label, value, hint }: { label: string; value: number | string; hint?: string }) {
  return (
    <div className="rounded-xl border border-[rgb(var(--edge))] bg-[rgb(var(--panel))] p-4">
      <p className="label">{label}</p>
      <p className="tnum mt-1 text-2xl font-semibold">{value}</p>
      {hint && <p className="mt-0.5 text-xs text-[rgb(var(--faint))]">{hint}</p>}
    </div>
  );
}
