"use client";

import Link from "next/link";

import { useCourse } from "@/components/course";
import { MODULES } from "@/lib/training";

/**
 * Beginner to expert as four paths, each a short list of the steps on this
 * page that belong to it. Level steps tick themselves from this browser's
 * record (course.tsx); the rest are links.
 */
type Step = { label: string; href: string; slug?: string };

const levels = (tier: string): Step[] =>
  MODULES.filter((m) => m.tier === tier).map((m) => ({ label: `Level ${m.level}: ${m.title}`, href: `/training/${m.slug}`, slug: m.slug }));

const PATHS: { title: string; who: string; hue: string; steps: Step[] }[] = [
  {
    title: "Beginner",
    who: "Stay safe at work and at home",
    hue: "16 185 129",
    steps: [
      { label: "Play Phish or legit and URL detective", href: "#games" },
      { label: "Play Password duel", href: "#games" },
      { label: "Lab: inspect a phishing email", href: "#labs" },
      { label: "Practice: beginner questions", href: "#practice" },
    ],
  },
  {
    title: "Intermediate",
    who: "Think like an analyst",
    hue: "14 165 233",
    steps: [...levels("Foundation"), { label: "Practice: intermediate questions", href: "#practice" }],
  },
  {
    title: "Advanced",
    who: "Respond to an incident",
    hue: "245 158 11",
    steps: [
      ...levels("Practitioner"),
      { label: "Labs: read a log, map to ATT&CK", href: "#labs" },
      { label: "Practice: advanced questions", href: "#practice" },
    ],
  },
  {
    title: "Expert",
    who: "Hunt, detect and prove it",
    hue: "236 72 153",
    steps: [
      ...levels("Mastery"),
      { label: "Scored drills on full incidents", href: "#drills" },
      { label: "Practice: expert questions", href: "#practice" },
    ],
  },
];

export function Paths() {
  const { store } = useCourse();
  return (
    <ol className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
      {PATHS.map((p, i) => {
        const tracked = p.steps.filter((s) => s.slug);
        const passed = tracked.filter((s) => store[s.slug as string]?.passed).length;
        return (
          <li
            key={p.title}
            style={{ ["--sp" as string]: p.hue }}
            className="relative flex flex-col overflow-hidden rounded-2xl border border-[rgb(var(--edge))] bg-[rgb(var(--panel))] p-4"
          >
            <span aria-hidden="true" className="sp-dot absolute inset-x-0 top-0 h-1 opacity-80" />
            <p className="flex items-center gap-2">
              <span className="sp-solid tnum inline-flex h-7 w-7 items-center justify-center rounded-lg text-sm font-semibold">{i + 1}</span>
              <span className="font-semibold">{p.title}</span>
              {tracked.length > 0 && (
                <span className="tnum sp-text ml-auto text-xs font-medium">
                  {passed}/{tracked.length}
                </span>
              )}
            </p>
            <p className="mt-1 text-xs text-[rgb(var(--muted))]">{p.who}</p>
            <ul className="mt-3 space-y-1.5 text-sm">
              {p.steps.map((s) => {
                const done = s.slug ? Boolean(store[s.slug]?.passed) : false;
                return (
                  <li key={s.label}>
                    <Link href={s.href} className="focusable group flex items-start gap-2 rounded-md hover:text-[rgb(var(--ink))]">
                      <span
                        aria-hidden="true"
                        className={`mt-0.5 inline-flex h-4 w-4 shrink-0 items-center justify-center rounded-full border text-[10px] ${
                          done ? "sp-solid border-transparent" : "border-[rgb(var(--edge-strong))]"
                        }`}
                      >
                        {done ? "✓" : ""}
                      </span>
                      <span className={`${done ? "text-[rgb(var(--faint))] line-through" : "text-[rgb(var(--muted))]"} group-hover:text-[rgb(var(--ink))]`}>
                        {s.label}
                      </span>
                    </Link>
                  </li>
                );
              })}
            </ul>
          </li>
        );
      })}
    </ol>
  );
}
