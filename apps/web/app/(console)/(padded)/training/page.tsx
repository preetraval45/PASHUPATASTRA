import type { Metadata } from "next";
import Link from "next/link";

import { TrainingBoard } from "@/components/training";
import { Offline, Page } from "@/components/ui";
import { getScenarios } from "@/lib/api";

export const metadata: Metadata = {
  title: "Training",
  description:
    "Cyber defence practice: work an incident from a single alert — investigate, diagnose, respond in proportion — and get scored on how you got there.",
};

export const dynamic = "force-dynamic";

/**
 * Cyber defence training. The drills are the Blue team exercises, presented as
 * what they are for a learner: a scored practice loop with a record, and the
 * skills it exercises named rather than implied.
 */
export default async function TrainingPage() {
  const scenarios = await getScenarios();
  if (scenarios === null) return <Offline />;

  return (
    <Page
      title="Training"
      description="Cyber defence practice. One alert, and the investigation is yours: open the evidence, find the real cause, choose a proportionate response — and see what you missed."
    >
      <section className="grid gap-4 md:grid-cols-3">
        <Step
          n={1}
          title="Investigate"
          points={20}
          body="Open the entities behind the alert. Points go to opening the evidence that rules the wrong explanation out — being right by luck scores less."
        />
        <Step
          n={2}
          title="Diagnose"
          points={50}
          body="Pick the explanation the evidence supports. One option is always plausible and wrong; it is the one a hurried analyst picks."
        />
        <Step
          n={3}
          title="Respond"
          points={30}
          body="Choose the action. Proportionality counts both ways: doing too little and doing too much are both marked down, the way policy would."
        />
      </section>

      <TrainingBoard scenarios={scenarios} />

      <section className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
        <div className="rounded-xl border border-[rgb(var(--edge))] bg-[rgb(var(--panel))] p-5">
          <h2 className="text-base font-semibold">Skills these drills exercise</h2>
          <ul className="mt-3 space-y-2 text-sm text-[rgb(var(--muted))]">
            <li><strong className="text-[rgb(var(--ink))]">Triage under ambiguity</strong> — starting from one alert, not a finished report.</li>
            <li><strong className="text-[rgb(var(--ink))]">Evidence-led diagnosis</strong> — every conclusion tied to something you opened.</li>
            <li><strong className="text-[rgb(var(--ink))]">Ruling out the plausible wrong answer</strong> — the habit that separates analysis from guessing.</li>
            <li><strong className="text-[rgb(var(--ink))]">Proportionate response</strong> — choosing an action a policy engine would authorise, and no more.</li>
          </ul>
        </div>
        <div className="rounded-xl border border-[rgb(var(--edge))] bg-[rgb(var(--panel))] p-5">
          <h2 className="text-base font-semibold">Go deeper</h2>
          <ul className="mt-3 space-y-2 text-sm">
            <Further href="/attack" title="ATT&CK coverage" body="The adversary techniques the incident library has observed, tactic by tactic." />
            <Further href="/detections" title="Detection rules" body="Sigma rules drafted from incidents — read what catches each technique." />
            <Further href="/actions" title="The action registry" body="Every response action, its risk score, and its rollback." />
            <Further href="/ask" title="Sati AI" body="Ask the investigation agent how it reached a diagnosis, with citations." />
          </ul>
        </div>
      </section>
    </Page>
  );
}

function Step({ n, title, points, body }: { n: number; title: string; points: number; body: string }) {
  return (
    <div className="rounded-xl border border-[rgb(var(--edge))] bg-[rgb(var(--panel))] p-5">
      <p className="flex items-center gap-2">
        <span className="tnum inline-flex h-7 w-7 items-center justify-center rounded-full bg-[rgb(var(--astra))]/15 text-sm font-semibold text-[rgb(var(--astra))]">
          {n}
        </span>
        <span className="font-semibold">{title}</span>
        <span className="tnum ml-auto text-xs text-[rgb(var(--faint))]">{points} pts</span>
      </p>
      <p className="mt-3 text-sm leading-relaxed text-[rgb(var(--muted))]">{body}</p>
    </div>
  );
}

function Further({ href, title, body }: { href: string; title: string; body: string }) {
  return (
    <li>
      <Link href={href} className="focusable group block rounded-lg px-2 py-1.5 -mx-2 hover:bg-[rgb(var(--raised))]">
        <span className="font-medium text-[rgb(var(--ink))] group-hover:text-[rgb(var(--astra))]">{title} →</span>
        <span className="block text-xs text-[rgb(var(--faint))]">{body}</span>
      </Link>
    </li>
  );
}
