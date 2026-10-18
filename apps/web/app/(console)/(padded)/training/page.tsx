import type { Metadata } from "next";
import Link from "next/link";

import { Evaluation, ModuleStatus } from "@/components/course";
import { TrainingBoard } from "@/components/training";
import { Page, Panel } from "@/components/ui";
import { getScenarios } from "@/lib/api";
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
      <section className="grid gap-4 md:grid-cols-4">
        {[
          { n: "1", t: "Learn", b: `${MODULES.length} modules, about ${minutes} minutes in all` },
          { n: "2", t: "Apply", b: "a real-life checklist with every module" },
          { n: "3", t: "Test", b: `${questions} questions, each answer explained` },
          { n: "4", t: "Practise", b: "scored drills on full incidents" },
        ].map((step) => (
          <div key={step.t} className="rounded-xl border border-[rgb(var(--edge))] bg-[rgb(var(--panel))] p-4">
            <p className="flex items-center gap-2">
              <span className="tnum inline-flex h-7 w-7 items-center justify-center rounded-full bg-[rgb(var(--astra))]/15 text-sm font-semibold text-[rgb(var(--astra))]">
                {step.n}
              </span>
              <span className="font-semibold">{step.t}</span>
            </p>
            <p className="mt-2 text-sm text-[rgb(var(--muted))]">{step.b}</p>
          </div>
        ))}
      </section>

      <Panel title="Your evaluation" aside="kept in this browser only">
        <Evaluation />
      </Panel>

      <section className="space-y-4">
        <h2 className="text-xl font-semibold tracking-tight">Course modules</h2>
        <ol className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {MODULES.map((m, i) => (
            <li key={m.slug}>
              <Link
                href={`/training/${m.slug}`}
                data-module={m.slug}
                className="focusable lift group flex h-full flex-col rounded-xl border border-[rgb(var(--edge-strong))] bg-[rgb(var(--panel))] p-5 transition hover:border-[rgb(var(--astra))]/50"
              >
                <span className="flex items-center gap-2">
                  <span className="label">Module {i + 1}</span>
                  <span className="text-xs text-[rgb(var(--faint))]">· {m.level} · {m.minutes} min</span>
                  <span className="ml-auto"><ModuleStatus slug={m.slug} /></span>
                </span>
                <span className="mt-3 text-base font-semibold group-hover:text-[rgb(var(--astra))]">{m.title}</span>
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
                <span className="mt-3 text-xs text-[rgb(var(--faint))]">{m.quiz.length}-question test</span>
              </Link>
            </li>
          ))}
        </ol>
      </section>

      <section className="space-y-4">
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
    </Page>
  );
}
