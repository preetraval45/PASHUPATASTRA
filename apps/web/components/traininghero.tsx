"use client";

import Link from "next/link";
import type { CSSProperties } from "react";

import { useCourse } from "@/components/course";
import { hue } from "@/lib/hues";
import { levelReached, MODULES } from "@/lib/training";

/**
 * The top of the training page: where this learner stands and the one next step.
 *
 * A ring for the level reached, the nine levels as a path in their models'
 * colours, and a button that continues where they left off. Progress is read
 * from this browser's own record (course.tsx); a first visit shows level 0.
 */
const SECTIONS = [
  { href: "#labs", label: "Labs" },
  { href: "#levels", label: "Nine levels" },
  { href: "#drills", label: "Drills" },
  { href: "#evaluation", label: "Your record" },
];

export function TrainingHero({ minutes, questions }: { minutes: number; questions: number }) {
  const { store } = useCourse();
  const level = levelReached((slug) => Boolean(store[slug]?.passed));
  const next = MODULES[level];
  const share = level / MODULES.length;
  const r = 42;
  const around = 2 * Math.PI * r;

  return (
    <section className="relative isolate overflow-hidden rounded-3xl border border-[rgb(var(--edge))] bg-[rgb(var(--panel))] p-5 sm:p-7">
      <div aria-hidden="true" className="hero-glow pointer-events-none absolute -inset-10 -z-10 opacity-80" />
      <div className="flex flex-col gap-6 sm:flex-row sm:items-center">
        <div className="relative h-28 w-28 shrink-0" role="img" aria-label={`Level ${level} of ${MODULES.length} reached`}>
          <svg viewBox="0 0 100 100" className="h-full w-full -rotate-90">
            <circle cx="50" cy="50" r={r} fill="none" strokeWidth="8" className="stroke-[rgb(var(--edge-strong))]" />
            <circle
              cx="50"
              cy="50"
              r={r}
              fill="none"
              strokeWidth="8"
              strokeLinecap="round"
              className="stroke-[rgb(var(--astra))] transition-[stroke-dashoffset] duration-700"
              strokeDasharray={around}
              strokeDashoffset={around * (1 - share)}
            />
          </svg>
          <span className="absolute inset-0 flex flex-col items-center justify-center">
            <span className="tnum text-3xl font-semibold leading-none">{level}</span>
            <span className="mt-1 text-[11px] text-[rgb(var(--muted))]">of {MODULES.length}</span>
          </span>
        </div>

        <div className="min-w-0 flex-1">
          <p className="label text-[rgb(var(--astra))]">Your level</p>
          <p className="mt-1 text-xl font-semibold tracking-tight sm:text-2xl">
            {level === 0
              ? "Start with the foundation"
              : next
                ? `Level ${level} reached. Next: ${next.title}`
                : "All nine levels passed"}
          </p>
          <p className="mt-1 text-sm text-[rgb(var(--muted))]">
            {MODULES.length} levels, about {minutes} minutes, {questions} questions. Each one explained.
          </p>

          <ol className="mt-4 flex gap-1.5" aria-label="The nine levels">
            {MODULES.map((m) => {
              const passed = Boolean(store[m.slug]?.passed);
              const current = next?.slug === m.slug;
              return (
                <li key={m.slug} className="flex-1">
                  <Link
                    href={`/training/${m.slug}`}
                    title={`Level ${m.level}: ${m.title}${passed ? " (passed)" : ""}`}
                    style={hue(m.form) as CSSProperties}
                    className={`focusable block h-2.5 rounded-full transition hover:scale-y-150 ${
                      passed ? "sp-dot" : current ? "bg-[rgb(var(--sp)/0.35)] animate-pulse" : "bg-[rgb(var(--raised))]"
                    }`}
                  >
                    <span className="sr-only">
                      Level {m.level}, {m.title}
                      {passed ? ", passed" : ""}
                    </span>
                  </Link>
                </li>
              );
            })}
          </ol>

          <div className="mt-5 flex flex-wrap items-center gap-2">
            <Link
              href={next ? `/training/${next.slug}` : "#labs"}
              className="focusable inline-flex items-center gap-2 rounded-xl bg-[rgb(var(--astra))] px-4 py-2.5 text-sm font-semibold text-white shadow-lg shadow-[rgb(var(--astra))]/20 transition hover:brightness-110"
            >
              {level === 0 ? "Start level 1" : next ? `Continue: level ${next.level}` : "Try the labs"}
              <span aria-hidden="true">→</span>
            </Link>
            <nav aria-label="On this page" className="no-scrollbar flex gap-1.5 overflow-x-auto">
              {SECTIONS.map((s) => (
                <a
                  key={s.href}
                  href={s.href}
                  className="focusable shrink-0 rounded-full border border-[rgb(var(--edge))] px-3 py-1.5 text-xs text-[rgb(var(--muted))] transition hover:border-[rgb(var(--astra))]/50 hover:text-[rgb(var(--ink))]"
                >
                  {s.label}
                </a>
              ))}
            </nav>
          </div>
        </div>
      </div>
    </section>
  );
}
