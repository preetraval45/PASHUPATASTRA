"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { useCourse } from "@/components/course";
import { DailyQuestion } from "@/components/dailyquestion";
import { Icon } from "@/components/sidebar";
import { levelReached, MODULES } from "@/lib/training";

/**
 * The Android app's home screen: an app's home, not the website's landing page.
 *
 * The website's home pitches the product to a newcomer. In the app the reader
 * has already chosen it, so the first screen is about doing: ask Sati, see
 * what is open, pick up training where they left it, and today's question.
 * Rendered only when the request comes from the app (its user agent says
 * PashupatastraApp); the website is unchanged.
 */
type Props = { open: number | null; awaiting: number | null; critical: number | null };

function greeting(hour: number): string {
  if (hour < 5) return "Working late";
  if (hour < 12) return "Good morning";
  if (hour < 18) return "Good afternoon";
  return "Good evening";
}

const TILES = [
  { href: "/incidents", icon: "alert", title: "Incidents", tone: "crit" },
  { href: "/observatory", icon: "radar", title: "Live attacks", tone: "warn", note: "polled hourly" },
  { href: "/models", icon: "cube", title: "Sati models", tone: "astra", note: "nine, live" },
  { href: "/findings", icon: "news", title: "Findings", tone: "ok", note: "what we measured" },
] as const;

export function AppHome({ open, awaiting, critical }: Props) {
  const [hello, setHello] = useState("Welcome");
  const { store } = useCourse();
  useEffect(() => setHello(greeting(new Date().getHours())), []);
  const level = levelReached((slug) => Boolean(store[slug]?.passed));
  const next = MODULES[level];

  return (
    <div className="space-y-5 pb-6">
      <header className="pt-1">
        <p className="text-sm text-[rgb(var(--muted))]">{hello}</p>
        <h1 className="mt-0.5 text-2xl font-semibold tracking-tight">What do you want to do?</h1>
      </header>

      {/* The main action: ask Sati, as an input-shaped button that opens the chat. */}
      <Link
        href="/ask"
        className="focusable relative isolate block overflow-hidden rounded-3xl border border-[rgb(var(--astra))]/40 p-5"
        style={{
          background:
            "linear-gradient(135deg, rgb(var(--astra) / 0.22), rgb(var(--panel)) 55%), rgb(var(--panel))",
        }}
      >
        <div aria-hidden="true" className="hero-glow pointer-events-none absolute -inset-10 -z-10 opacity-70" />
        <p className="flex items-center gap-2 text-sm font-semibold text-[rgb(var(--astra))]">
          <Icon name="chat" /> Sati AI
        </p>
        <p className="mt-2 text-lg font-semibold leading-snug">Ask about an attack, a technique or a defence</p>
        <p className="mt-1 text-sm text-[rgb(var(--muted))]">
          Sati, the investigation agent, and its nine specialist models answer with sources.
        </p>
        <span className="mt-4 flex items-center justify-between rounded-2xl border border-[rgb(var(--edge-strong))] bg-[rgb(var(--ground))]/70 px-4 py-3 text-sm text-[rgb(var(--faint))]">
          Ask Sati anything…
          <span className="inline-flex h-8 w-8 items-center justify-center rounded-xl bg-[rgb(var(--astra))] text-[rgb(var(--ground))]">
            <svg aria-hidden="true" viewBox="0 0 24 24" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth={2.2}>
              <path d="M12 19V5M5 12l7-7 7 7" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          </span>
        </span>
      </Link>

      {/* Status at a glance, then the places to go, as tiles a thumb can hit. */}
      <ul className="grid grid-cols-2 gap-3">
        {TILES.map((t) => {
          const note =
            t.href === "/incidents"
              ? open === null
                ? "status unavailable"
                : `${open} open${awaiting ? ` · ${awaiting} need you` : ""}`
              : t.note;
          return (
            <li key={t.href}>
              <Link
                href={t.href}
                className="focusable flex h-full min-h-[7.5rem] flex-col justify-between rounded-2xl border border-[rgb(var(--edge))] bg-[rgb(var(--panel))] p-4 active:scale-[0.98] transition"
              >
                <span
                  className="inline-flex h-10 w-10 items-center justify-center rounded-xl"
                  style={{ background: `rgb(var(--${t.tone}) / 0.15)`, color: `rgb(var(--${t.tone}))` }}
                >
                  <Icon name={t.icon} />
                </span>
                <span>
                  <span className="block font-semibold">{t.title}</span>
                  <span className="block text-xs text-[rgb(var(--muted))]">{note}</span>
                </span>
              </Link>
            </li>
          );
        })}
      </ul>

      {critical ? (
        <Link
          href="/incidents?severity=critical"
          className="focusable flex items-center gap-3 rounded-2xl border border-[rgb(var(--crit))]/40 bg-[rgb(var(--crit))]/10 p-4 text-sm"
        >
          <span aria-hidden="true" className="h-2.5 w-2.5 shrink-0 animate-pulse rounded-full bg-[rgb(var(--crit))]" />
          <span className="flex-1">
            <strong>{critical} critical</strong> incident{critical === 1 ? "" : "s"} open
          </span>
          <span aria-hidden="true">→</span>
        </Link>
      ) : null}

      {/* Training, picked up where this phone left it. */}
      <Link
        href={next ? `/training/${next.slug}` : "/training"}
        className="focusable block rounded-2xl border border-[rgb(var(--edge))] bg-[rgb(var(--panel))] p-4"
      >
        <span className="flex items-center justify-between text-sm">
          <span className="flex items-center gap-2 font-semibold">
            <Icon name="cap" /> Your training
          </span>
          <span className="tnum text-xs text-[rgb(var(--muted))]">
            level {level} of {MODULES.length}
          </span>
        </span>
        <span className="mt-3 flex gap-1" aria-hidden="true">
          {MODULES.map((m) => (
            <span
              key={m.slug}
              className={`h-1.5 flex-1 rounded-full ${store[m.slug]?.passed ? "bg-[rgb(var(--astra))]" : "bg-[rgb(var(--raised))]"}`}
            />
          ))}
        </span>
        <span className="mt-3 block text-sm">
          {next ? (
            <>
              {level === 0 ? "Start" : "Continue"} with <strong>{next.title}</strong> →
            </>
          ) : (
            "All nine levels passed. Try the hands-on labs →"
          )}
        </span>
      </Link>

      <DailyQuestion />

      <Link
        href="/training"
        className="focusable flex items-center gap-3 rounded-2xl border border-[rgb(var(--edge))] bg-[rgb(var(--panel))] p-4 text-sm"
      >
        <span className="inline-flex h-10 w-10 items-center justify-center rounded-xl bg-[rgb(var(--astra))]/15 text-[rgb(var(--astra))]">
          <Icon name="shield" />
        </span>
        <span className="flex-1">
          <span className="block font-semibold">Hands-on labs</span>
          <span className="block text-xs text-[rgb(var(--muted))]">Spot a phish, read a log, name the technique</span>
        </span>
        <span aria-hidden="true">→</span>
      </Link>
    </div>
  );
}
