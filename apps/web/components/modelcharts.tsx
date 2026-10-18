"use client";

/**
 * Model-versus-baseline bars with their confidence intervals (Models page).
 *
 * Each row is one held-out split; the two bars are the trained model and the
 * no-learning baseline on exactly the same incidents. The whisker is the
 * Wilson 95% interval — drawn, not footnoted, because two bars whose whiskers
 * overlap are not a win, whatever their lengths say.
 */

import { useState } from "react";

export type CompareRow = {
  label: string;
  hint?: string;
  model: { value: number; ci: number[] };
  baseline: { value: number; ci: number[] };
  n: number;
};

const MODEL = "47 163 160";
const BASE = "148 163 184";

export function CompareBars({ rows, metric }: { rows: CompareRow[]; metric: string }) {
  const [hover, setHover] = useState<string | null>(null);
  return (
    <div>
      <div className="mb-3 flex flex-wrap items-center gap-4 text-xs text-[rgb(var(--muted))]">
        <span className="flex items-center gap-1.5">
          <span aria-hidden="true" className="h-2.5 w-2.5 rounded-sm" style={{ background: `rgb(${MODEL})` }} />
          trained model
        </span>
        <span className="flex items-center gap-1.5">
          <span aria-hidden="true" className="h-2.5 w-2.5 rounded-sm" style={{ background: `rgb(${BASE})` }} />
          no-learning baseline
        </span>
        <span className="text-[rgb(var(--faint))]">whiskers: 95% interval</span>
      </div>
      <ul className="space-y-3">
        {rows.map((row) => (
          <li
            key={row.label}
            onPointerEnter={() => setHover(row.label)}
            onPointerLeave={() => setHover(null)}
            className={`rounded-lg px-2 py-1.5 transition ${hover === row.label ? "bg-[rgb(var(--raised))]" : ""}`}
          >
            <div className="mb-1 flex items-baseline gap-2 text-sm">
              <span className="font-medium">{row.label}</span>
              {row.hint && <span className="text-xs text-[rgb(var(--faint))]">{row.hint}</span>}
              <span className="tnum ml-auto text-xs text-[rgb(var(--faint))]">n = {row.n}</span>
            </div>
            {(["model", "baseline"] as const).map((which) => {
              const bar = row[which];
              const tone = which === "model" ? MODEL : BASE;
              return (
                <div key={which} className="flex items-center gap-2">
                  <div className="relative h-3 flex-1 rounded-full bg-[rgb(var(--raised))]">
                    <div
                      className="h-full rounded-full transition-[width] duration-700"
                      style={{ width: `${bar.value * 100}%`, background: `rgb(${tone})` }}
                    />
                    {bar.ci.length === 2 && (
                      <div
                        aria-hidden="true"
                        className="absolute top-1/2 h-px -translate-y-1/2 bg-[rgb(var(--ink))]/70"
                        style={{ left: `${bar.ci[0] * 100}%`, width: `${(bar.ci[1] - bar.ci[0]) * 100}%` }}
                      >
                        <span className="absolute -top-1 left-0 h-2 w-px bg-[rgb(var(--ink))]/70" />
                        <span className="absolute -top-1 right-0 h-2 w-px bg-[rgb(var(--ink))]/70" />
                      </div>
                    )}
                  </div>
                  <span className="tnum w-24 text-right text-xs">
                    <span className={which === "model" ? "font-semibold text-[rgb(var(--ink))]" : "text-[rgb(var(--muted))]"}>
                      {(bar.value * 100).toFixed(1)}%
                    </span>
                    {hover === row.label && bar.ci.length === 2 && (
                      <span className="block text-[10px] text-[rgb(var(--faint))]">
                        {(bar.ci[0] * 100).toFixed(1)}–{(bar.ci[1] * 100).toFixed(1)}
                      </span>
                    )}
                  </span>
                </div>
              );
            })}
          </li>
        ))}
      </ul>
      <p className="mt-2 text-[11px] text-[rgb(var(--faint))]">{metric}</p>
    </div>
  );
}
