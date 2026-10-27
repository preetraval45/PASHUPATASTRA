"use client";

import { useEffect, useState } from "react";

import { getKatyayaniCases, rankKatyayani, type KatyayaniCases, type KatyayaniRanking } from "@/lib/api";

/**
 * Run Katyayani on an incident it never trained on.
 *
 * The ranking is computed by the API on each request, from the served model,
 * and the true root cause is shown beside it, including when the model is
 * wrong. Nothing here is precomputed for the page.
 */
export function TryKatyayani() {
  const [cases, setCases] = useState<KatyayaniCases | null | undefined>(undefined);
  const [picked, setPicked] = useState<string>("");
  const [result, setResult] = useState<KatyayaniRanking | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    getKatyayaniCases().then((c) => {
      setCases(c);
      if (c?.cases.length) setPicked(c.cases[0].id);
    });
  }, []);

  async function run(id: string) {
    setBusy(true);
    setResult(await rankKatyayani(id));
    setBusy(false);
  }

  if (cases === undefined) return <p className="text-sm text-[rgb(var(--faint))]">Loading the incidents…</p>;
  if (cases === null || cases.cases.length === 0)
    return (
      <p className="text-sm text-[rgb(var(--faint))]">
        The live model is not reachable right now. Its measured results are below.
      </p>
    );

  return (
    <div className="space-y-4" data-try="katyayani">
      <p className="text-sm text-[rgb(var(--muted))]">
        Pick a real incident Katyayani never saw in training ({cases.reserved.incidents} kept aside from{" "}
        {cases.trained_on.incidents + cases.reserved.incidents}). It ranks the services live, and the true
        root cause is shown beside its answer.
        {cases.reserved["rca@1"] !== null && (
          <> On these incidents it names the root first {Math.round(cases.reserved["rca@1"] * 100)}% of the time.</>
        )}
      </p>
      <div className="flex flex-wrap items-center gap-2">
        <label htmlFor="katyayani-case" className="sr-only">Incident</label>
        <select
          id="katyayani-case"
          value={picked}
          onChange={(e) => setPicked(e.target.value)}
          className="focusable max-w-full rounded-lg border border-[rgb(var(--edge-strong))] bg-[rgb(var(--panel))] px-3 py-2 text-sm"
        >
          {cases.cases.map((c) => (
            <option key={c.id} value={c.id}>
              {c.system} · {c.id} · {c.services} services
            </option>
          ))}
        </select>
        <button
          type="button"
          onClick={() => run(picked)}
          disabled={busy || !picked}
          className="focusable rounded-lg bg-[rgb(var(--astra))] px-4 py-2 text-sm font-semibold text-white transition hover:opacity-90 disabled:opacity-50"
        >
          {busy ? "Ranking…" : "Find the root cause"}
        </button>
      </div>
      {result && (
        <div aria-live="polite" className="space-y-3">
          <p className={`text-sm font-medium ${result.correct ? "text-emerald-600 dark:text-emerald-400" : "text-amber-600 dark:text-amber-400"}`}>
            <span aria-hidden="true">{result.correct ? "✓ " : "✗ "}</span>
            {result.correct
              ? `Right: ${result.root} is the root cause, and Katyayani ranked it first.`
              : `Wrong: the root cause was ${result.root}; Katyayani ranked it ${result.position}${["st", "nd", "rd"][result.position - 1] ?? "th"}.`}
          </p>
          <ol className="divide-y divide-[rgb(var(--edge))] rounded-lg border border-[rgb(var(--edge))]">
            {result.ranking.slice(0, 6).map((r, i) => (
              <li key={r.service} className="flex flex-wrap items-baseline gap-x-3 gap-y-1 px-3 py-2 text-sm">
                <span className="tnum w-5 text-[rgb(var(--faint))]">{i + 1}</span>
                <span className="mono font-medium">{r.service}</span>
                {r.service === result.root && (
                  <span className="rounded-full bg-emerald-500/15 px-2 py-0.5 text-[11px] font-semibold text-emerald-700 dark:text-emerald-300">
                    true root cause
                  </span>
                )}
                <span className="ml-auto text-xs text-[rgb(var(--faint))]">
                  peak shift {r.evidence.peak ?? "—"}σ · went anomalous #{r.evidence.onset_rank ?? "—"}
                </span>
              </li>
            ))}
          </ol>
        </div>
      )}
    </div>
  );
}
