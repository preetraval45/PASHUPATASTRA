import type { Metadata } from "next";
import Link from "next/link";
import type { CSSProperties } from "react";

import { Evaluation, ModuleStatus } from "@/components/course";
import { DailyQuestion } from "@/components/dailyquestion";
import { Labs } from "@/components/labs";
import { TrainingBoard } from "@/components/training";
import { TrainingHero } from "@/components/traininghero";
import { Page, Panel } from "@/components/ui";
import { getScenarios } from "@/lib/api";
import { hue } from "@/lib/hues";
import { MODULES } from "@/lib/training";

export const metadata: Metadata = {
  title: "Training",
  description:
    "A cyber defence course: learn a skill you will use in real life, test it, then practise it on a scored investigation.",
};

export const dynamic = "force-dynamic";

/**
 * Cyber defence training: learn → test → practise → see your evaluation.
 *
 * Learn and test are the course modules (content in `lib/training.ts`, every
 * fact from NIST, MITRE ATT&CK or CISA). Practise is the scored drills, which
 * start from one alert on a full incident. The evaluation is the learner's own
 * record, kept in their browser.
 */
export default async function TrainingPage() {
  const scenarios = await getScenarios();
  const minutes = MODULES.reduce((sum, m) => sum + m.minutes, 0);
  const questions = MODULES.reduce((sum, m) => sum + m.quiz.length, 0);

  return (
    <Page
      title="Training"
      description="A cyber defence course you can use at work tomorrow. Each module teaches one skill, shows how to apply it in real life, and tests you on it — then the drills let you practise on a full investigation."
    >
      <TrainingHero minutes={minutes} questions={questions} />

      <DailyQuestion />

      <section id="labs" className="scroll-mt-24 space-y-4">
        <div>
          <h2 className="text-xl font-semibold tracking-tight">Hands-on labs</h2>
          <p className="mt-1 max-w-3xl text-sm text-[rgb(var(--muted))]">
            Do the analyst&apos;s work yourself: inspect an email, read a log, name the technique. Every tap explains
            itself.
          </p>
        </div>
        <Labs />
      </section>

      <section id="levels" className="scroll-mt-24 space-y-4">
        <div>
          <h2 className="text-xl font-semibold tracking-tight">Nine levels of cyber awareness</h2>
          <p className="mt-1 max-w-3xl text-sm text-[rgb(var(--muted))]">
            One level for each of the nine Sati models&rsquo; forms, from Shailaputri, the foundation, to
            Siddhidatri, mastery. Pass a level&rsquo;s test to reach it; your level is the highest one with
            every level below it passed.
          </p>
        </div>
        <ol className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {MODULES.map((m) => (
            <li key={m.slug}>
              <Link
                href={`/training/${m.slug}`}
                data-module={m.slug}
                style={hue(m.form) as CSSProperties}
                className="focusable lift sp-hover group relative flex h-full flex-col overflow-hidden rounded-2xl border border-[rgb(var(--edge))] bg-[rgb(var(--panel))] p-5 transition"
              >
                <span aria-hidden="true" className="sp-dot absolute inset-x-0 top-0 h-1 opacity-70" />
                <span className="flex items-center gap-3">
                  <span className="sp-solid tnum inline-flex h-10 w-10 shrink-0 items-center justify-center rounded-xl text-base font-semibold">
                    {m.level}
                  </span>
                  <span className="min-w-0">
                    <span className="sp-text block text-xs font-semibold uppercase tracking-wide">{m.form}</span>
                    <span className="block text-xs text-[rgb(var(--faint))]">{m.minutes} min · {m.quiz.length} questions</span>
                  </span>
                  <span className="ml-auto"><ModuleStatus slug={m.slug} /></span>
                </span>
                <span className="mt-4 text-base font-semibold">{m.title}</span>
                <span className="mt-1.5 flex-1 text-sm leading-relaxed text-[rgb(var(--muted))]">{m.summary}</span>
                {m.attack && (
                  <span className="mt-3 flex flex-wrap gap-1.5">
                    {m.attack.map((t) => (
                      <span key={t.id} className="mono rounded border border-[rgb(var(--edge))] px-1.5 py-0.5 text-[10.5px] text-[rgb(var(--faint))]">
                        {t.id}
                      </span>
                    ))}
                  </span>
                )}
                <span className="sp-text mt-4 text-sm font-medium transition group-hover:translate-x-0.5">Open level {m.level} →</span>
              </Link>
            </li>
          ))}
        </ol>
      </section>

      <section id="drills" className="scroll-mt-24 space-y-4">
        <div>
          <h2 className="text-xl font-semibold tracking-tight">Practice drills</h2>
          <p className="mt-1 max-w-3xl text-sm text-[rgb(var(--muted))]">
            One alert, and the investigation is yours. Investigate (20 points for opening the evidence
            that rules the wrong explanation out), diagnose (50 — one option is always plausible and
            wrong), respond (30 — doing too little and too much are both marked down).
          </p>
        </div>
        {scenarios === null ? (
          <p className="rounded-xl border border-dashed border-[rgb(var(--edge))] p-6 text-sm text-[rgb(var(--faint))]">
            The drills come from the live API, which did not answer. The course above works without it.
          </p>
        ) : (
          <TrainingBoard scenarios={scenarios} />
        )}
      </section>

      <section id="evaluation" className="scroll-mt-24">
        <Panel title="Your record" aside="kept in this browser only">
          <Evaluation />
        </Panel>
      </section>
    </Page>
  );
}
