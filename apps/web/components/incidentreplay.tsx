"use client";

import { useEffect, useMemo, useRef, useState } from "react";

import type { AuditRecord } from "@/lib/api";

/**
 * The incident as it unfolded, played back: every recorded observation,
 * hypothesis and decision arrives in order, with the clock it was recorded at.
 *
 * A replay of the audit records, sped up, and labelled as one. The scenarios on
 * this site are written, so nothing here pretends to be happening now; what it
 * shows is the order and spacing of what was recorded, which a static list
 * flattens. Paused, it is the plain list, so nothing waits behind a button.
 */
const STEP_MS = 1100;

const KIND: Record<string, { label: string; tone: string }> = {
  observation: { label: "Observed", tone: "--warn" },
  hypothesis: { label: "Hypothesis", tone: "--astra" },
  policy_evaluation: { label: "Policy", tone: "--crit" },
  approval: { label: "Approval", tone: "--ok" },
  execution_attempt: { label: "Action", tone: "--crit" },
  execution_result: { label: "Action result", tone: "--ok" },
  verification: { label: "Verified", tone: "--ok" },
};

const ACTOR: Record<string, string> = {
  drishti: "Drishti, perception",
  buddhi: "Buddhi, reasoning",
  dharma: "Dharma, policy",
  astra: "Astra, actions",
};

function actorName(actor: string): string {
  if (actor.startsWith("agent:")) return `Sati, the investigation agent (${actor.slice(6)})`;
  return ACTOR[actor] ?? actor;
}

function clock(iso: string): string {
  return new Date(iso).toISOString().slice(11, 19);
}

function offset(ms: number): string {
  const s = Math.max(0, Math.round(ms / 1000));
  return `T+${String(Math.floor(s / 60)).padStart(2, "0")}:${String(s % 60).padStart(2, "0")}`;
}

export function IncidentReplay({ audit, incidentId }: { audit: AuditRecord[]; incidentId: string }) {
  const events = useMemo(
    () =>
      audit
        .filter((r) => r.incident_ref === incidentId && r.kind in KIND)
        .sort((a, b) => Date.parse(a.at) - Date.parse(b.at)),
    [audit, incidentId],
  );
  // null: not playing, everything shown. A number: how many have arrived so far.
  const [shown, setShown] = useState<number | null>(null);
  const end = useRef<HTMLLIElement>(null);

  useEffect(() => {
    if (shown === null || shown >= events.length) return;
    const t = setTimeout(() => setShown((n) => (n === null ? null : n + 1)), shown === 0 ? 300 : STEP_MS);
    return () => clearTimeout(t);
  }, [shown, events.length]);

  useEffect(() => {
    if (shown !== null && shown > 0) end.current?.scrollIntoView({ block: "nearest", behavior: "smooth" });
  }, [shown]);

  if (events.length === 0) return null;
  const start = Date.parse(events[0].at);
  const playing = shown !== null && shown < events.length;
  const visible = shown === null ? events : events.slice(0, shown);
  const current = visible[visible.length - 1];

  return (
    <section className="overflow-hidden rounded-2xl border border-[rgb(var(--edge))] bg-[rgb(var(--panel))]">
      <header className="flex flex-wrap items-center gap-3 border-b border-[rgb(var(--edge))] px-4 py-3 sm:px-5">
        <div className="min-w-0 flex-1">
          <h2 className="flex items-center gap-2 font-semibold">
            {playing && (
              <span className="relative flex h-2 w-2" aria-hidden="true">
                <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-[rgb(var(--crit))] opacity-75" />
                <span className="relative inline-flex h-2 w-2 rounded-full bg-[rgb(var(--crit))]" />
              </span>
            )}
            {playing ? "Replaying" : "As it happened"}
          </h2>
          <p className="text-xs text-[rgb(var(--faint))]">
            {events.length} recorded steps over {offset(Date.parse(events[events.length - 1].at) - start).slice(2)} minutes
            {" "}· a replay of the record, sped up
          </p>
        </div>
        {current && shown !== null && (
          <span className="tnum mono rounded-lg bg-[rgb(var(--raised))] px-2.5 py-1 text-sm" aria-live="polite">
            {clock(current.at)} UTC · {offset(Date.parse(current.at) - start)}
          </span>
        )}
        {playing ? (
          <button
            type="button"
            onClick={() => setShown(null)}
            className="focusable rounded-lg border border-[rgb(var(--edge))] px-3 py-1.5 text-sm text-[rgb(var(--muted))] hover:text-[rgb(var(--ink))]"
          >
            Show all
          </button>
        ) : (
          <button
            type="button"
            onClick={() => setShown(0)}
            className="focusable inline-flex items-center gap-1.5 rounded-lg bg-[rgb(var(--astra))] px-3 py-1.5 text-sm font-semibold text-white transition hover:brightness-110"
          >
            <span aria-hidden="true">▶</span> {shown === null ? "Replay it live" : "Replay again"}
          </button>
        )}
      </header>

      {shown !== null && (
        <div className="h-1 bg-[rgb(var(--raised))]" aria-hidden="true">
          <div
            className="h-full bg-[rgb(var(--astra))] transition-[width] duration-700"
            style={{ width: `${(Math.min(shown, events.length) / events.length) * 100}%` }}
          />
        </div>
      )}

      <ol className="max-h-[28rem] space-y-0 overflow-y-auto px-4 py-3 sm:px-5">
        {visible.map((r, i) => {
          const k = KIND[r.kind];
          return (
            <li
              key={`${r.at}-${i}`}
              ref={i === visible.length - 1 ? end : undefined}
              className="rise relative flex gap-3 pb-4 pl-1 last:pb-1"
            >
              <span className="relative flex flex-col items-center" aria-hidden="true">
                <span className="mt-1.5 h-2.5 w-2.5 rounded-full ring-4 ring-[rgb(var(--panel))]" style={{ background: `rgb(var(${k.tone}))` }} />
                {i < visible.length - 1 && <span className="mt-1 w-px flex-1 bg-[rgb(var(--edge-strong))]" />}
              </span>
              <div className="min-w-0 flex-1">
                <p className="flex flex-wrap items-baseline gap-x-2 text-xs">
                  <span className="font-semibold" style={{ color: `rgb(var(${k.tone}))` }}>
                    {k.label}
                  </span>
                  <span className="text-[rgb(var(--faint))]">{actorName(r.actor)}</span>
                  <span className="tnum mono ml-auto text-[rgb(var(--faint))]">{offset(Date.parse(r.at) - start)}</span>
                </p>
                <p className="mt-0.5 break-words text-sm leading-relaxed">{r.summary}</p>
              </div>
            </li>
          );
        })}
      </ol>
    </section>
  );
}
