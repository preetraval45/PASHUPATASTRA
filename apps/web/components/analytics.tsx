"use client";

/**
 * Interactive charts for the Analytics page (RP-52).
 *
 * Hand-drawn like `charts.tsx`, under the same rule: they plot what the API
 * returned and nothing else. No smoothing, no interpolation across an empty
 * bucket, no placeholder series when a source is missing — a missing source is
 * said in words by the page, not drawn as a flat line that looks like data.
 *
 * Interaction is what the old dashboard lacked: hover a bar for its exact
 * counts, click a legend entry to hide a series, switch the time range.
 */

import Link from "next/link";
import { useMemo, useState } from "react";

/** Distinct, colour-blind-safe series colours. Status colours (--ok, --warn,
 *  --high, --crit) are reserved for status and are never used for a series. */
const SERIES = [
  "47 163 160", // astra teal
  "129 140 248", // indigo
  "201 162 39", // gold
  "236 72 153", // pink
  "56 189 248", // sky
  "163 230 53", // lime
  "168 85 247", // violet
  "148 163 184", // slate
];

export type TimedEvent = { at: string; group: string };

type Range = "all" | "24h" | "7d";

/**
 * Events over time, stacked by group. The bucket width follows the span of the
 * data actually shown — five minutes for an hour of records, an hour for a
 * day, a day beyond that — so a short history is readable rather than one bar.
 */
export function TimeBars({ events, height = 220 }: { events: TimedEvent[]; height?: number }) {
  const [range, setRange] = useState<Range>("all");
  const [hidden, setHidden] = useState<Set<string>>(new Set());
  const [hover, setHover] = useState<number | null>(null);

  const groups = useMemo(() => {
    const counts = new Map<string, number>();
    for (const event of events) counts.set(event.group, (counts.get(event.group) ?? 0) + 1);
    return [...counts.entries()].sort((a, b) => b[1] - a[1]).map(([group]) => group);
  }, [events]);

  const { buckets, width, label } = useMemo(() => {
    const times = events.map((e) => Date.parse(e.at)).filter(Number.isFinite);
    if (times.length === 0) return { buckets: [], width: 0, label: "" };
    const latest = Math.max(...times);
    const floor =
      range === "24h" ? latest - 864e5 : range === "7d" ? latest - 7 * 864e5 : Math.min(...times);
    const span = Math.max(latest - floor, 1);
    const step =
      span <= 2 * 36e5 ? 5 * 6e4 : span <= 2 * 864e5 ? 36e5 : 864e5;
    const start = Math.floor(floor / step) * step;
    const count = Math.max(1, Math.floor((latest - start) / step) + 1);
    const rows: { start: number; counts: Record<string, number> }[] = Array.from({ length: count }, (_, i) => ({
      start: start + i * step,
      counts: {},
    }));
    for (const event of events) {
      const t = Date.parse(event.at);
      if (!Number.isFinite(t) || t < start) continue;
      const row = rows[Math.min(count - 1, Math.floor((t - start) / step))];
      row.counts[event.group] = (row.counts[event.group] ?? 0) + 1;
    }
    return {
      buckets: rows,
      width: step,
      label: step === 5 * 6e4 ? "5-minute buckets" : step === 36e5 ? "hourly buckets" : "daily buckets",
    };
  }, [events, range]);

  const visible = groups.filter((g) => !hidden.has(g));
  const totals = buckets.map((b) => visible.reduce((sum, g) => sum + (b.counts[g] ?? 0), 0));
  const max = Math.max(1, ...totals);
  const color = (group: string) => SERIES[groups.indexOf(group) % SERIES.length];

  const toggle = (group: string) =>
    setHidden((prior) => {
      const next = new Set(prior);
      if (next.has(group)) next.delete(group);
      else next.add(group);
      return next;
    });

  if (events.length === 0) {
    return <p className="py-10 text-center text-sm text-[rgb(var(--faint))]">No records in this window.</p>;
  }

  const fmt = (t: number) =>
    new Date(t).toLocaleString(undefined, width >= 864e5
      ? { month: "short", day: "numeric" }
      : { hour: "2-digit", minute: "2-digit" });

  const active = hover !== null ? buckets[hover] : null;

  return (
    <div>
      <div className="mb-3 flex flex-wrap items-center gap-2">
        <div className="flex rounded-md border border-[rgb(var(--edge))] p-0.5 text-xs" role="group" aria-label="Time range">
          {(["all", "7d", "24h"] as Range[]).map((r) => (
            <button
              key={r}
              type="button"
              aria-pressed={range === r}
              onClick={() => setRange(r)}
              className={`focusable rounded px-2.5 py-1 transition ${
                range === r ? "bg-[rgb(var(--raised))] text-[rgb(var(--ink))]" : "text-[rgb(var(--faint))] hover:text-[rgb(var(--ink))]"
              }`}
            >
              {r === "all" ? "All" : r}
            </button>
          ))}
        </div>
        <span className="text-[11px] text-[rgb(var(--faint))]">{label}</span>
        <ul className="ml-auto flex flex-wrap gap-1.5">
          {groups.map((group) => (
            <li key={group}>
              <button
                type="button"
                onClick={() => toggle(group)}
                aria-pressed={!hidden.has(group)}
                className={`focusable flex items-center gap-1.5 rounded-full border border-[rgb(var(--edge))] px-2 py-0.5 text-[11px] transition ${
                  hidden.has(group) ? "opacity-40" : "hover:bg-[rgb(var(--raised))]"
                }`}
              >
                <span aria-hidden="true" className="h-2 w-2 rounded-full" style={{ background: `rgb(${color(group)})` }} />
                {group.replaceAll("_", " ")}
              </button>
            </li>
          ))}
        </ul>
      </div>

      <div className="relative" onPointerLeave={() => setHover(null)}>
        <div className="flex items-end gap-[2px]" style={{ height }} role="img" aria-label={`Records over time, ${label}`}>
          {buckets.map((bucket, index) => (
            <div
              key={bucket.start}
              onPointerEnter={() => setHover(index)}
              className={`flex h-full min-w-[3px] flex-1 cursor-default flex-col-reverse rounded-sm ${hover === index ? "bg-[rgb(var(--raised))]" : ""}`}
            >
              {visible.map((group) => {
                const n = bucket.counts[group] ?? 0;
                if (!n) return null;
                return (
                  <div
                    key={group}
                    style={{ height: `${(n / max) * 100}%`, background: `rgb(${color(group)})` }}
                    className="w-full first:rounded-b-sm last:rounded-t-sm"
                  />
                );
              })}
            </div>
          ))}
        </div>
        <div className="mt-1.5 flex justify-between text-[10px] text-[rgb(var(--faint))]">
          <span className="tnum">{buckets.length ? fmt(buckets[0].start) : ""}</span>
          <span className="tnum">max {max} per bucket</span>
          <span className="tnum">{buckets.length ? fmt(buckets[buckets.length - 1].start) : ""}</span>
        </div>

        {active && (
          <div className="pointer-events-none absolute top-0 z-10 min-w-[10rem] rounded-lg border border-[rgb(var(--edge-strong))] bg-[rgb(var(--panel))] p-2.5 text-xs shadow-xl"
            style={{ left: `min(calc(${((hover ?? 0) / Math.max(1, buckets.length)) * 100}% + 8px), calc(100% - 11rem))` }}
          >
            <p className="tnum mb-1.5 font-medium">{fmt(active.start)}</p>
            {visible.filter((g) => active.counts[g]).map((group) => (
              <p key={group} className="flex items-center gap-2">
                <span aria-hidden="true" className="h-2 w-2 rounded-full" style={{ background: `rgb(${color(group)})` }} />
                <span className="text-[rgb(var(--muted))]">{group.replaceAll("_", " ")}</span>
                <span className="tnum ml-auto">{active.counts[group]}</span>
              </p>
            ))}
            {totals[hover ?? 0] === 0 && <p className="text-[rgb(var(--faint))]">nothing recorded</p>}
          </div>
        )}
      </div>
    </div>
  );
}

export type Slice = { label: string; value: number; tone?: string; href?: string; hint?: string };

/**
 * A ranked breakdown: one row per category, the bar's length its share. Rows
 * with an `href` are links, so a count is one click from the records behind it.
 */
export function Breakdown({ slices, unit = "" }: { slices: Slice[]; unit?: string }) {
  const [hover, setHover] = useState<string | null>(null);
  const total = slices.reduce((sum, s) => sum + s.value, 0);
  const max = Math.max(1, ...slices.map((s) => s.value));
  if (slices.length === 0 || total === 0) {
    return <p className="py-6 text-center text-sm text-[rgb(var(--faint))]">Nothing to break down yet.</p>;
  }
  return (
    <ul className="space-y-2.5">
      {slices.map((slice, index) => {
        const tone = slice.tone ?? SERIES[index % SERIES.length];
        const share = Math.round((slice.value / total) * 100);
        const row = (
          <>
            <span className="flex items-baseline gap-2 text-sm">
              <span className="min-w-0 truncate text-[rgb(var(--ink))]">{slice.label}</span>
              {slice.hint && <span className="hidden truncate text-xs text-[rgb(var(--faint))] sm:inline">{slice.hint}</span>}
              <span className="tnum ml-auto text-[rgb(var(--ink))]">
                {slice.value.toLocaleString()}
                {unit}
              </span>
              <span className={`tnum w-10 text-right text-xs ${hover === slice.label ? "text-[rgb(var(--ink))]" : "text-[rgb(var(--faint))]"}`}>
                {share}%
              </span>
            </span>
            <span className="mt-1 block h-2 overflow-hidden rounded-full bg-[rgb(var(--raised))]">
              <span
                className="block h-full rounded-full transition-[width] duration-500"
                style={{ width: `${(slice.value / max) * 100}%`, background: `rgb(${tone})`, opacity: hover && hover !== slice.label ? 0.45 : 1 }}
              />
            </span>
          </>
        );
        return (
          <li key={slice.label} onPointerEnter={() => setHover(slice.label)} onPointerLeave={() => setHover(null)}>
            {slice.href ? (
              <Link href={slice.href} className="focusable block rounded">
                {row}
              </Link>
            ) : (
              row
            )}
          </li>
        );
      })}
    </ul>
  );
}

/** Daily values as columns with a hover readout — for series that already come
 *  bucketed by day from the API, such as `/usage`. */
export function DayColumns({
  days,
  unit,
  height = 140,
  bucket = "day",
}: {
  days: { day: string; value: number; detail?: string }[];
  unit: string;
  height?: number;
  /** What one column is, for the hover hint ("Hover a month…"). */
  bucket?: string;
}) {
  const [hover, setHover] = useState<number | null>(null);
  const max = Math.max(1, ...days.map((d) => d.value));
  if (!days.some((d) => d.value > 0)) {
    return <p className="py-6 text-center text-sm text-[rgb(var(--faint))]">Nothing recorded in this window.</p>;
  }
  const active = hover !== null ? days[hover] : null;
  return (
    <div onPointerLeave={() => setHover(null)}>
      <div className="flex items-end gap-1" style={{ height }}>
        {days.map((d, i) => (
          <div key={d.day} onPointerEnter={() => setHover(i)} className="flex h-full flex-1 items-end">
            <div
              className="w-full rounded-t-sm transition-opacity"
              style={{
                height: `${Math.max(d.value > 0 ? 2 : 0, (d.value / max) * 100)}%`,
                background: "rgb(47 163 160)",
                opacity: hover === null || hover === i ? 1 : 0.4,
              }}
            />
          </div>
        ))}
      </div>
      {/* First, middle and last labels, so the axis is readable without hovering. */}
      <div aria-hidden="true" className="tnum mt-1.5 flex justify-between text-[10.5px] text-[rgb(var(--faint))]">
        <span>{days[0]?.day}</span>
        {days.length > 4 && <span>{days[Math.floor(days.length / 2)]?.day}</span>}
        <span>{days[days.length - 1]?.day}</span>
      </div>
      <p className="tnum mt-2 h-4 text-xs text-[rgb(var(--muted))]">
        {active ? (
          <>
            {active.day} · <span className="text-[rgb(var(--ink))]">{active.value.toLocaleString()}</span> {unit}
            {active.detail && ` · ${active.detail}`}
          </>
        ) : (
          <span className="text-[rgb(var(--faint))]">Hover or tap a {bucket} for its value</span>
        )}
      </p>
    </div>
  );
}
