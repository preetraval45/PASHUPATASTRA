"use client";

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";

import { getIntel, type IntelGroup } from "@/lib/api";

/**
 * Happening now: real attacks reported in the last hours, from the public feeds
 * the API polls (URLhaus, ThreatFox, Feodo Tracker, ransomware.live, CISA KEV).
 *
 * The incidents below it are written scenarios; this strip is the opposite,
 * the outside world as it is reported, so the page shows something live without
 * pretending a scripted incident is one. Same rules as components/live.tsx: the
 * age is always on screen, polling stops while the tab is hidden, and only
 * reports that arrive after the first load are marked new (components/fresh.tsx).
 */
const POLL_MS = 60_000;

const SOURCE: Record<string, { label: string; tone: string; what: string }> = {
  "ransomware-live": { label: "Ransomware", tone: "--crit", what: "a victim claimed on a leak site" },
  threatfox: { label: "ThreatFox", tone: "--crit", what: "a malware indicator" },
  urlhaus: { label: "URLhaus", tone: "--warn", what: "a malware download site" },
  "feodo-tracker": { label: "Botnet C2", tone: "--warn", what: "a botnet command server" },
  "cisa-kev": { label: "Exploited CVE", tone: "--astra", what: "a vulnerability attacked in the wild" },
  nvd: { label: "NVD", tone: "--muted", what: "a newly published vulnerability" },
  hibp: { label: "Breach", tone: "--muted", what: "a published data breach" },
};

function since(iso: string, now: number): string {
  const s = Math.max(0, Math.round((now - Date.parse(iso)) / 1000));
  if (s < 60) return "just now";
  if (s < 3600) return `${Math.floor(s / 60)} min ago`;
  if (s < 86_400) return `${Math.floor(s / 3600)} h ago`;
  return `${Math.floor(s / 86_400)} d ago`;
}

export function HappeningNow() {
  const [groups, setGroups] = useState<IntelGroup[] | null | undefined>(undefined);
  const [fresh, setFresh] = useState<Set<string>>(new Set());
  const [checked, setChecked] = useState<number | null>(null);
  const [now, setNow] = useState(() => Date.now());
  const [more, setMore] = useState(false);
  const seen = useRef<Set<string> | null>(null);

  const load = useCallback(async () => {
    if (document.hidden) return;
    const data = await getIntel(40);
    setChecked(Date.now());
    if (!data) {
      setGroups((was) => (was === undefined ? null : was));
      return;
    }
    const list = [...data.groups].sort((a, b) => Date.parse(b.last_at) - Date.parse(a.last_at));
    const keys = list.map((g) => `${g.source}:${g.entity_key}:${g.last_at}`);
    if (seen.current) {
      const before = seen.current;
      setFresh(new Set(keys.filter((k) => !before.has(k))));
    }
    seen.current = new Set(keys);
    setGroups(list);
  }, []);

  useEffect(() => {
    load();
    const poll = setInterval(load, POLL_MS);
    const tick = setInterval(() => setNow(Date.now()), 15_000);
    const back = () => !document.hidden && load();
    document.addEventListener("visibilitychange", back);
    return () => {
      clearInterval(poll);
      clearInterval(tick);
      document.removeEventListener("visibilitychange", back);
    };
  }, [load]);

  const shown = (groups ?? []).slice(0, more ? 24 : 8);
  const bySource = new Map<string, number>();
  for (const g of groups ?? []) bySource.set(g.source, (bySource.get(g.source) ?? 0) + 1);

  return (
    <section
      aria-labelledby="happening-now"
      className="relative isolate overflow-hidden rounded-3xl border border-[rgb(var(--edge))] bg-[rgb(var(--panel))] p-4 sm:p-6"
    >
      <div aria-hidden="true" className="hero-glow pointer-events-none absolute -inset-10 -z-10 opacity-50" />
      <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
        <span className="inline-flex items-center gap-2 rounded-full bg-[rgb(var(--crit))]/15 px-2.5 py-1 text-xs font-semibold text-[rgb(var(--crit))]">
          <span className="relative flex h-2 w-2">
            <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-[rgb(var(--crit))] opacity-75" />
            <span className="relative inline-flex h-2 w-2 rounded-full bg-[rgb(var(--crit))]" />
          </span>
          Live
        </span>
        <h2 id="happening-now" className="text-lg font-semibold tracking-tight">
          Happening now, worldwide
        </h2>
        <span className="tnum ml-auto text-xs text-[rgb(var(--faint))]" aria-live="polite">
          {checked ? `checked ${since(new Date(checked).toISOString(), now)}` : "checking…"}
        </span>
      </div>
      <p className="mt-1 max-w-2xl text-sm text-[rgb(var(--muted))]">
        Real attacks reported in the last few hours by public threat feeds. This is the outside world, not your
        systems; it refreshes every minute.
      </p>

      {bySource.size > 0 && (
        <div className="no-scrollbar fade-x -mx-1 mt-3 flex gap-1.5 overflow-x-auto px-1">
          {[...bySource.entries()].map(([source, n]) => {
            const s = SOURCE[source] ?? { label: source, tone: "--muted" };
            return (
              <span
                key={source}
                className="tnum shrink-0 rounded-full px-2.5 py-1 text-xs font-medium"
                style={{ background: `rgb(var(${s.tone}) / 0.12)`, color: `rgb(var(${s.tone}))` }}
              >
                {n} · {s.label}
              </span>
            );
          })}
        </div>
      )}

      {groups === undefined ? (
        <ul className="mt-4 space-y-2">
          {Array.from({ length: 4 }, (_, i) => (
            <li key={i} className="h-14 animate-pulse rounded-xl bg-[rgb(var(--raised))]" />
          ))}
        </ul>
      ) : groups === null ? (
        <p className="mt-4 text-sm text-[rgb(var(--faint))]">The live feeds are not reachable right now.</p>
      ) : groups.length === 0 ? (
        <p className="mt-4 text-sm text-[rgb(var(--faint))]">Nothing reported in the last few hours.</p>
      ) : (
        <ol className="mt-4 space-y-2">
          {shown.map((g) => {
            const key = `${g.source}:${g.entity_key}:${g.last_at}`;
            const s = SOURCE[g.source] ?? { label: g.source, tone: "--muted", what: "a report" };
            const isNew = fresh.has(key);
            return (
              <li
                key={key}
                className={`rise flex gap-3 rounded-xl border p-3 transition ${
                  isNew ? "border-[rgb(var(--crit))]/50 bg-[rgb(var(--crit))]/5" : "border-[rgb(var(--edge))] bg-[rgb(var(--ground))]/40"
                }`}
              >
                <span aria-hidden="true" className="mt-1.5 h-2 w-2 shrink-0 rounded-full" style={{ background: `rgb(var(${s.tone}))` }} />
                <div className="min-w-0 flex-1">
                  <p className="flex flex-wrap items-baseline gap-x-2 text-sm">
                    <span className="font-semibold" style={{ color: `rgb(var(${s.tone}))` }}>
                      {s.label}
                    </span>
                    <span className="min-w-0 break-words text-[rgb(var(--ink))]">{g.title}</span>
                    {isNew && (
                      <span className="rounded-full bg-[rgb(var(--crit))] px-1.5 text-[10px] font-semibold uppercase text-white">new</span>
                    )}
                  </p>
                  <p className="mt-0.5 truncate text-xs text-[rgb(var(--muted))]">{g.summary || s.what}</p>
                </div>
                <span className="tnum shrink-0 text-xs text-[rgb(var(--faint))]">{since(g.last_at, now)}</span>
              </li>
            );
          })}
        </ol>
      )}

      {groups && groups.length > 0 && (
        <div className="mt-3 flex flex-wrap items-center gap-3 text-sm">
          {groups.length > 8 && (
            <button
              type="button"
              onClick={() => setMore((m) => !m)}
              className="focusable rounded-lg border border-[rgb(var(--edge))] px-3 py-1.5 text-[rgb(var(--muted))] hover:text-[rgb(var(--ink))]"
            >
              {more ? "Show fewer" : `Show ${Math.min(24, groups.length) - 8} more`}
            </button>
          )}
          <Link href="/observatory" className="text-[rgb(var(--astra))] underline-offset-4 hover:underline">
            Every source, with history →
          </Link>
        </div>
      )}
    </section>
  );
}
