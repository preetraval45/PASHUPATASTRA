"use client";

import { useEffect, useState } from "react";

import { getServerIncidents, runServerIncident, type ServerIncidents, type ServerRun } from "@/lib/api";

const W = 640;
const H = 120;

/**
 * Run Shailaputri, Siddhidatri and Mahagauri on a server incident from a
 * machine group none of them trained on. Everything is computed by the API on
 * request; the labelled anomaly is drawn under their answers.
 */
export function TryServers() {
  const [list, setList] = useState<ServerIncidents | null | undefined>(undefined);
  const [picked, setPicked] = useState("");
  const [run, setRun] = useState<ServerRun | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    getServerIncidents().then((l) => {
      setList(l);
      if (l?.incidents.length) setPicked(l.incidents[0].id);
    });
  }, []);

  if (list === undefined) return <p className="text-sm text-[rgb(var(--faint))]">Loading the incidents…</p>;
  if (list === null || list.incidents.length === 0)
    return (
      <p className="text-sm text-[rgb(var(--faint))]">
        The live models are not reachable right now. Their measured results are below.
      </p>
    );

  const x = (i: number, n: number) => (i / Math.max(1, n - 1)) * W;

  return (
    <div className="space-y-4" data-try="servers">
      <p className="text-sm text-[rgb(var(--muted))]">
        Real incidents from {list.held_out_group}, a group of servers none of the three models trained on
        (they learned from {list.trained_on.join(" and ")}). Run one: Shailaputri flags the anomalous minutes,
        Siddhidatri states a probability, and Mahagauri says when it is over. The labelled anomaly is shaded.
      </p>
      <div className="flex flex-wrap items-center gap-2">
        <label htmlFor="server-incident" className="sr-only">Incident</label>
        <select
          id="server-incident"
          value={picked}
          onChange={(e) => setPicked(e.target.value)}
          className="focusable max-w-full rounded-lg border border-[rgb(var(--edge-strong))] bg-[rgb(var(--panel))] px-3 py-2 text-sm"
        >
          {list.incidents.map((d) => (
            <option key={d.id} value={d.id}>
              {d.machine} · {d.length}-minute anomaly
            </option>
          ))}
        </select>
        <button
          type="button"
          onClick={async () => {
            setBusy(true);
            setRun(await runServerIncident(picked));
            setBusy(false);
          }}
          disabled={busy || !picked}
          className="focusable rounded-lg bg-[rgb(var(--astra))] px-4 py-2 text-sm font-semibold text-white transition hover:opacity-90 disabled:opacity-50"
        >
          {busy ? "Running…" : "Run the three models"}
        </button>
      </div>

      {run && (
        <div aria-live="polite" className="space-y-3">
          <svg viewBox={`0 0 ${W} ${H}`} className="w-full rounded-lg border border-[rgb(var(--edge))]" role="img"
               aria-label="Minute by minute: the labelled anomaly, Shailaputri's flags, Siddhidatri's probability and Mahagauri's all-clear">
            <rect x={x(run.incident[0], run.minutes)} y={0} height={H}
                  width={Math.max(2, x(run.incident[1], run.minutes) - x(run.incident[0], run.minutes))}
                  className="fill-rose-500/15" />
            <polyline fill="none" strokeWidth={1.5} className="stroke-sky-500"
                      points={run.siddhidatri.probability.map((p, i) => `${x(i, run.minutes)},${H - 14 - p * (H - 34)}`).join(" ")} />
            {run.shailaputri.flags.map((f, i) =>
              f ? <rect key={i} x={x(i, run.minutes) - 1} y={H - 10} width={2.5} height={8} className="fill-amber-500" /> : null,
            )}
            {run.mahagauri.declared_over !== null && (
              <line x1={x(run.mahagauri.declared_over, run.minutes)} x2={x(run.mahagauri.declared_over, run.minutes)}
                    y1={0} y2={H} strokeWidth={2} strokeDasharray="4 3" className="stroke-emerald-500" />
            )}
          </svg>
          <ul className="flex flex-wrap gap-x-5 gap-y-1 text-xs text-[rgb(var(--muted))]">
            <li><span className="mr-1 inline-block h-2.5 w-3 bg-rose-500/30 align-middle" />labelled anomaly</li>
            <li><span className="mr-1 inline-block h-2.5 w-1 bg-amber-500 align-middle" />Shailaputri flag</li>
            <li><span className="mr-1 inline-block h-0.5 w-3 bg-sky-500 align-middle" />Siddhidatri probability</li>
            <li><span className="mr-1 inline-block h-2.5 w-0.5 bg-emerald-500 align-middle" />Mahagauri: over</li>
          </ul>
          <dl className="grid gap-2 text-sm sm:grid-cols-3">
            <div className="rounded-lg border border-[rgb(var(--edge))] p-3">
              <dt className="label">Shailaputri</dt>
              <dd className="mt-1">
                {run.shailaputri.caught
                  ? `Caught it, ${run.shailaputri.first_flag! - run.incident[0]} min after onset`
                  : "Missed it"}
                {run.shailaputri.false_flags_before > 0 && `; ${run.shailaputri.false_flags_before} false flags before`}
              </dd>
            </div>
            <div className="rounded-lg border border-[rgb(var(--edge))] p-3">
              <dt className="label">Siddhidatri</dt>
              <dd className="mt-1">
                Peak probability {Math.round(Math.max(...run.siddhidatri.probability.slice(run.incident[0], run.incident[1])) * 100)}% during
                the anomaly
              </dd>
            </div>
            <div className="rounded-lg border border-[rgb(var(--edge))] p-3">
              <dt className="label">Mahagauri</dt>
              <dd className="mt-1">
                {run.mahagauri.verdict === "confirmed"
                  ? `Declared over ${run.mahagauri.declared_over! - run.incident[1]} min after it ended`
                  : run.mahagauri.verdict === "premature"
                    ? "Declared over too early"
                    : "Did not declare it over: left to a person"}
              </dd>
            </div>
          </dl>
        </div>
      )}
    </div>
  );
}
