"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

/**
 * The loop, as something to explore rather than a line of words.
 *
 * Each stage says what happens there, which of Sati's models work at it, and
 * where on the site to see it. It steps through on its own until a visitor
 * picks a stage, and never moves for anyone who asked for reduced motion. The
 * content is the architecture's (docs/ARCHITECTURE.md), stated as plainly as
 * the rest of the site: where no model works, it says so.
 */
const STAGES = [
  {
    name: "Observe",
    what: "Alerts, metrics, logs and flows from every tool become one kind of event, each keeping a link to where it came from.",
    models: [
      { name: "Shailaputri", job: "server metric anomalies", id: "sati-shailaputri" },
      { name: "Kalaratri", job: "log anomalies", id: "sati-kalaratri" },
      { name: "Chandraghanta", job: "network intrusion", id: "sati-chandraghanta" },
    ],
    see: { href: "/observatory", label: "Today's real attacks" },
  },
  {
    name: "Understand",
    what: "Events that touch the same entities close together in time become one incident, with a causal chain and each step mapped to ATT&CK.",
    models: [
      { name: "Brahmacharini", job: "behaviour to technique", id: "sati-brahmacharini" },
      { name: "Katyayani", job: "root-cause service", id: "sati-katyayani" },
    ],
    see: { href: "/incidents", label: "Open an incident" },
  },
  {
    name: "Predict",
    what: "The topology graph says what else is exposed: the blast radius, before anything is touched.",
    models: [{ name: "Siddhidatri", job: "one verdict from several detectors", id: "sati-siddhidatri" }],
    see: { href: "/incidents", label: "See a blast radius" },
  },
  {
    name: "Decide",
    what: "Sati, the investigation agent, proposes a response; Dharma, the policy engine, scores its risk and decides who must approve it. No model decides.",
    models: [{ name: "Kushmanda", job: "writes the explanation", id: "sati-kushmanda" }],
    see: { href: "/how-it-works", label: "How risk decides" },
  },
  {
    name: "Act",
    what: "An action runs only with a live verdict, as a dry run by default, and declares its rollback before it starts.",
    models: [{ name: "Skandamata", job: "which defences fit", id: "sati-skandamata" }],
    see: { href: "/actions", label: "The action registry" },
  },
  {
    name: "Verify",
    what: "The system is compared with the state the action promised, over a window, not one glance.",
    models: [{ name: "Mahagauri", job: "is it really over?", id: "sati-mahagauri" }],
    see: { href: "/models#mahagauri-results", label: "How well it knows" },
  },
  {
    name: "Learn",
    what: "Outcomes are stored so the next incident starts from them, and people practise the same loop in training.",
    models: [],
    see: { href: "/training", label: "Practise it" },
  },
] as const;

const STEP_MS = 4200;

export function LoopExplorer() {
  const [current, setCurrent] = useState(0);
  const [touched, setTouched] = useState(false);

  useEffect(() => {
    if (touched || window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    const timer = window.setInterval(() => setCurrent((c) => (c + 1) % STAGES.length), STEP_MS);
    return () => window.clearInterval(timer);
  }, [touched]);

  const pick = (index: number) => {
    setTouched(true);
    setCurrent(index);
  };
  const stage = STAGES[current];

  return (
    <div className="rounded-2xl border border-[rgb(var(--edge))] bg-[rgb(var(--panel))] p-4 sm:p-6">
      <div role="tablist" aria-label="The loop" className="no-scrollbar fade-x -mx-1 flex gap-1 overflow-x-auto px-3 pb-1">
        {STAGES.map((s, index) => {
          const active = index === current;
          return (
            <button
              key={s.name}
              type="button"
              role="tab"
              aria-selected={active}
              aria-controls="loop-stage"
              onClick={() => pick(index)}
              className={`focusable relative flex shrink-0 items-center gap-2 rounded-full px-3.5 py-2 text-sm font-medium transition ${
                active
                  ? "bg-[rgb(var(--astra))] text-[rgb(var(--ground))] shadow-sm"
                  : "text-[rgb(var(--muted))] hover:bg-[rgb(var(--raised))] hover:text-[rgb(var(--ink))]"
              }`}
            >
              <span className={`tnum text-[11px] ${active ? "opacity-80" : "text-[rgb(var(--faint))]"}`}>{index + 1}</span>
              {s.name}
            </button>
          );
        })}
      </div>

      {/* Progress through the loop, so the auto-advance never looks like a glitch. */}
      <div aria-hidden="true" className="mt-3 h-0.5 overflow-hidden rounded-full bg-[rgb(var(--edge))]">
        <div
          className="h-full rounded-full bg-[rgb(var(--astra))] transition-[width] duration-500"
          style={{ width: `${((current + 1) / STAGES.length) * 100}%` }}
        />
      </div>

      <div id="loop-stage" role="tabpanel" key={stage.name} className="rise mt-5 grid gap-5 md:grid-cols-[1fr_auto] md:items-end">
        <div className="space-y-4">
          <p className="max-w-2xl text-[0.9375rem] leading-relaxed text-[rgb(var(--ink))]">{stage.what}</p>
          {stage.models.length > 0 ? (
            <ul className="flex flex-wrap gap-2">
              {stage.models.map((m) => (
                <li key={m.id}>
                  <Link
                    href={`/models#${m.id}`}
                    className="focusable inline-flex items-center gap-2 rounded-lg border border-[rgb(var(--edge-strong))] px-3 py-1.5 text-sm transition hover:border-[rgb(var(--astra))]/60 hover:bg-[rgb(var(--raised))]"
                  >
                    <span className="h-1.5 w-1.5 rounded-full bg-[rgb(var(--astra))]" aria-hidden="true" />
                    <span className="text-[rgb(var(--muted))]">{m.job}</span>
                    <span className="font-medium">{m.name}</span>
                  </Link>
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-sm text-[rgb(var(--faint))]">No model works here: this stage is records and people.</p>
          )}
        </div>
        <Link
          href={stage.see.href}
          className="focusable inline-flex min-h-[44px] items-center justify-center rounded-lg border border-[rgb(var(--edge-strong))] px-4 text-sm font-medium transition hover:bg-[rgb(var(--raised))]"
        >
          {stage.see.label} →
        </Link>
      </div>
    </div>
  );
}
