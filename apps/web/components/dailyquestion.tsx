"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";

import { arranged, MODULES } from "@/lib/training";

/**
 * One question a day from the course, the same for everyone on that day.
 *
 * A minute's practice that brings people back: answer it here, see at once
 * whether you were right and why, and keep a streak of days answered. Like the
 * rest of the course, the record lives only in this browser.
 */
const KEY = "pashu.daily.v1";
type Daily = { day: number; picked: number | null; streak: number; lastDay: number };

const ALL = MODULES.flatMap((m) => m.quiz.map((q) => ({ q: arranged(q), module: m })));

function today(): number {
  return Math.floor(Date.now() / 86_400_000);
}

function read(): Daily {
  try {
    return JSON.parse(localStorage.getItem(KEY) ?? "null") ?? { day: -1, picked: null, streak: 0, lastDay: -1 };
  } catch {
    return { day: -1, picked: null, streak: 0, lastDay: -1 };
  }
}

export function DailyQuestion() {
  const [day, setDay] = useState<number | null>(null);
  const [state, setState] = useState<Daily>({ day: -1, picked: null, streak: 0, lastDay: -1 });

  useEffect(() => {
    setDay(today());
    setState(read());
  }, []);

  // Rendered only once the day is known in the browser, so the server and the phone never disagree.
  const item = useMemo(() => (day === null ? null : ALL[(day * 7919) % ALL.length]), [day]);
  if (day === null || !item) return <div className="h-40 animate-pulse rounded-2xl bg-[rgb(var(--panel))]" />;

  const picked = state.day === day ? state.picked : null;
  const answered = picked !== null;
  const right = answered && picked === item.q.answer;

  const pick = (option: number) => {
    if (answered) return;
    const streak = state.lastDay === day - 1 ? state.streak + 1 : 1;
    const next = { day, picked: option, streak, lastDay: day };
    setState(next);
    try {
      localStorage.setItem(KEY, JSON.stringify(next));
    } catch {
      // Not remembered; the answer still shows.
    }
  };

  return (
    <section
      aria-label="Question of the day"
      className="relative overflow-hidden rounded-2xl border border-[rgb(var(--astra))]/40 bg-[rgb(var(--panel))] p-5 sm:p-6"
    >
      <div aria-hidden="true" className="hero-glow pointer-events-none absolute -inset-10 -z-0 opacity-60" />
      <div className="relative">
        <p className="flex flex-wrap items-center gap-x-3 gap-y-1">
          <span className="label text-[rgb(var(--astra))]">Question of the day</span>
          <span className="text-xs text-[rgb(var(--faint))]">from level {item.module.level} · {item.module.title}</span>
          {state.streak > 0 && state.lastDay >= day - 1 && (
            <span className="ml-auto rounded-full bg-[rgb(var(--astra))]/15 px-2.5 py-0.5 text-xs font-semibold text-[rgb(var(--astra))]">
              {state.streak}-day streak
            </span>
          )}
        </p>
        <p className="mt-3 text-lg font-semibold leading-snug">{item.q.q}</p>
        <div role="radiogroup" aria-label="Answers" className="mt-4 grid gap-2 sm:grid-cols-2">
          {item.q.options.map((option, i) => {
            const tone = !answered
              ? "border-[rgb(var(--edge-strong))] hover:border-[rgb(var(--astra))]/60 hover:bg-[rgb(var(--raised))]"
              : i === item.q.answer
                ? "border-[rgb(var(--ok))]/60 bg-[rgb(var(--ok))]/10"
                : i === picked
                  ? "border-[rgb(var(--crit))]/60 bg-[rgb(var(--crit))]/10"
                  : "border-[rgb(var(--edge))] opacity-60";
            return (
              <button
                key={option}
                type="button"
                role="radio"
                aria-checked={picked === i}
                disabled={answered}
                onClick={() => pick(i)}
                className={`focusable min-h-[44px] rounded-lg border px-3.5 py-2 text-left text-sm transition ${tone}`}
              >
                {answered && i === item.q.answer && <span aria-hidden="true" className="mr-1.5 text-[rgb(var(--ok))]">✓</span>}
                {answered && i === picked && i !== item.q.answer && <span aria-hidden="true" className="mr-1.5 text-[rgb(var(--crit))]">✗</span>}
                {option}
              </button>
            );
          })}
        </div>
        {answered && (
          <div aria-live="polite" className="rise mt-4 space-y-2">
            <p className="text-sm leading-relaxed">
              <strong className={right ? "text-[rgb(var(--ok))]" : "text-[rgb(var(--ink))]"}>{right ? "Correct. " : "Not quite. "}</strong>
              <span className="text-[rgb(var(--muted))]">{item.q.why}</span>
            </p>
            <p className="text-xs text-[rgb(var(--faint))]">
              A new question tomorrow.{" "}
              <Link href={`/training/${item.module.slug}`} className="focusable rounded font-medium text-[rgb(var(--astra))] hover:underline">
                Learn the whole level →
              </Link>
            </p>
          </div>
        )}
      </div>
    </section>
  );
}
