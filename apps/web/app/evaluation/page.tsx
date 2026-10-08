import type { Metadata } from "next";
import Link from "next/link";

import { Distribution } from "@/components/charts";
import { Page, Panel, Stat } from "@/components/ui";
import evaluation from "@/lib/evaluation.generated.json";

export const metadata: Metadata = {
  title: "Evaluation",
  description:
    "What this system has been measured on, what it has not, and the review that said the evaluation was the weak part — published rather than waited out.",
};

/**
 * The evaluation, including the parts that do not exist yet.
 *
 * A venue review on 7 October 2026 said the paper's writing was publishable
 * and its evaluation was not: scenarios run once each, arms with no data, no
 * injection result, no outside users, and — its own phrase — the biggest gap,
 * that the language model is never tested, because the benchmark substitutes a
 * deterministic stand-in for it.
 *
 * This page publishes that review. Not a summary of it, and not a roadmap
 * written in its direction: the findings as given, each next to what has
 * actually closed it, which for most of them is nothing. The reason is the
 * same one `/impact` is built on — a project claiming its numbers are
 * recomputable has no standing to be quiet about the places where there are no
 * numbers. A reviewer who finds the gap themselves concludes the project did
 * not know; a reviewer who finds it stated concludes the project measured.
 *
 * Everything countable here is counted by `scripts/buildevaluation.py` from
 * the corpus on disk, the harness's own declarations and the results
 * directory, so the page cannot report a measurement that was not taken. The
 * arms all read "no data" because the results directory is empty and
 * gitignored, which is itself one of the findings.
 */
export default function EvaluationPage() {
  const { corpus, diagnosis, arms, injection, review, attacks } = evaluation;
  const percent = (n: number) => `${(n * 100).toFixed(1)}%`;

  return (
    <Page
      title="Evaluation"
      description="What has been measured, what has not, and the review that said so."
      actions={
        <p className="text-xs text-[rgb(var(--faint))]">
          counted {evaluation.generated_at.slice(0, 10)} at {evaluation.commit}
        </p>
      }
    >
      <section className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Stat
          label="Scenarios authored"
          value={String(corpus.scenarios)}
          hint={`${Object.keys(corpus.by_category).length} categories, balanced`}
        />
        <Stat
          label="Gradeable for diagnosis"
          value={String(diagnosis.scoreable)}
          hint={`${diagnosis.options}-way choice · guessing scores ${percent(diagnosis.baseline)}`}
        />
        <Stat
          label="Arms with recorded runs"
          value={`${evaluation.arms_with_data} of ${evaluation.arms_declared}`}
          hint="the review's first finding, recounted here"
        />
        {/* The reason is four sentences long and belongs in the panel below,
            not wrapped to five lines inside a figure card — a stat whose hint
            is a paragraph stops reading as a stat. */}
        <Stat
          label="Diagnosis accuracy"
          value="—"
          hint="not measured — the grader has never graded anything; why, below"
        />
      </section>

      {/* The review first, before anything that might look like an answer to
          it. Putting the strengths above the criticism is the arrangement that
          makes a reader distrust both. */}
      <Panel
        title="What a venue review said"
        aside={`${review.date} · ${review.findings.length} findings, published as given`}
      >
        <ol className="space-y-4">
          {review.findings.map((finding, index) => (
            <li key={finding.key} data-finding={finding.key} className="flex gap-3 text-sm">
              <span className="tnum shrink-0 pt-0.5 text-xs text-[rgb(var(--faint))]">
                {index + 1}
              </span>
              <div className="min-w-0 space-y-1">
                <p className="leading-relaxed text-[rgb(var(--muted))]">{finding.finding}</p>
                <p className="text-xs">
                  <span
                    className={
                      finding.status === "open"
                        ? "text-[rgb(var(--warn))]"
                        : "text-[rgb(var(--astra))]"
                    }
                  >
                    {finding.status}
                  </span>
                </p>
              </div>
            </li>
          ))}
        </ol>
        <p className="mt-5 text-xs leading-relaxed text-[rgb(var(--faint))]">
          Three of the five are open and are shown as open. A status here names
          something a reader can go and check, never &ldquo;in progress&rdquo;, which is
          what a project writes when it would rather not answer.
        </p>
      </Panel>

      {attacks && (
        <Panel
          title="Attacked, and what the attack actually tested"
          aside={`${attacks.models.length} models swept · one worst case`}
        >
          {attacks.worst_case && (
            <div className="rounded border border-[rgb(var(--edge))] bg-[rgb(var(--raised))] p-4">
              <p className="text-sm leading-relaxed">
                <span className="text-[rgb(var(--ink))]">The test that counts.</span>{" "}
                {attacks.what_the_worst_case_shows}
              </p>
              <dl className="mt-4 grid grid-cols-2 gap-4 sm:grid-cols-4">
                {(
                  [
                    ["turns", attacks.worst_case.turns],
                    ["registered actions", attacks.worst_case.registered_actions],
                    ["executions", attacks.worst_case.execution_records],
                    ["approvals", attacks.worst_case.approval_records],
                  ] as const
                ).map(([label, value]) => (
                  <div key={label} data-worst={label}>
                    <dt className="label">{label}</dt>
                    <dd
                      className={`tnum mt-1 text-2xl ${
                        value === 0 ? "text-[rgb(var(--ok))]" : ""
                      }`}
                    >
                      {value}
                    </dd>
                  </div>
                ))}
              </dl>
            </div>
          )}

          <p className="mt-6 label">the live sweep, and what it does not show</p>
          <ul className="mt-3 space-y-3">
            {attacks.models.map((model) => (
              <li key={model.model} data-attack-model={model.model} className="text-sm">
                <span className="mono text-[rgb(var(--ink))]">{model.model}</span>
                <span className="text-[rgb(var(--muted))]">
                  {" "}— <span className="tnum">{model.flagged}</span> of{" "}
                  <span className="tnum">{model.attack_turns}</span> attack turns flagged,{" "}
                  <span className="tnum">{model.harmful_raw_proposals}</span> harmful actions
                  proposed,{" "}
                  <span className="tnum">{model.autonomous_harmful}</span> scored autonomous
                  {model.kept_proposals > 0 && (
                    <>
                      {" "}
                      ({model.kept_proposals} benign proposals kept:{" "}
                      {Object.entries(model.kept_tiers)
                        .map(([tier, n]) => `${n} ${tier}`)
                        .join(", ")})
                    </>
                  )}
                </span>
              </li>
            ))}
          </ul>

          <p className="mt-5 rounded border border-[rgb(var(--edge))] p-3 text-sm leading-relaxed">
            <span className="text-[rgb(var(--warn))]">
              This sweep is not evidence that the controls hold.
            </span>{" "}
            <span className="text-[rgb(var(--muted))]">
              {attacks.what_the_sweep_does_not_show}
            </span>
          </p>

          <p className="mt-4 text-xs leading-relaxed text-[rgb(var(--faint))]">
            <span className="text-[rgb(var(--ink))]">And a blind spot, stated.</span>{" "}
            {attacks.kavach_blind_spot}
          </p>

          {attacks.policy && (
            <p className="mt-3 text-xs leading-relaxed text-[rgb(var(--faint))]">
              Separately, the policy engine was run over all{" "}
              <span className="tnum">{attacks.policy.scenarios}</span> benchmark scenarios in{" "}
              {attacks.policy.contexts} deployment contexts:{" "}
              <span className="tnum text-[rgb(var(--ink))]">
                {attacks.policy.forbidden_scored_autonomous}
              </span>{" "}
              forbidden actions scored autonomous. That is policy evaluation only — no
              cluster, no model — so it says what the engine decides, not what the system
              does end to end.
            </p>
          )}
        </Panel>
      )}

      <Panel
        title="Diagnosis, and why no number sits here yet"
        aside={`${diagnosis.scoreable} gradeable of ${corpus.scenarios}`}
      >
        <p className="text-sm leading-relaxed text-[rgb(var(--muted))]">
          The corpus authors{" "}
          <span className="tnum text-[rgb(var(--ink))]">{diagnosis.options}</span> root causes
          across <span className="tnum text-[rgb(var(--ink))]">{diagnosis.scoreable}</span>{" "}
          scenarios, every one distinct — so naming the cause of an incident is a one-in-
          {diagnosis.options} choice and guessing scores{" "}
          <span className="tnum text-[rgb(var(--ink))]">{percent(diagnosis.baseline)}</span>. An
          accuracy figure without that baseline beside it is unreadable, so neither is ever
          shown without the other.
        </p>
        <p className="mt-3 text-sm leading-relaxed text-[rgb(var(--muted))]">
          {diagnosis.graded_by}
        </p>
        <p className="mt-4 rounded border border-[rgb(var(--edge))] bg-[rgb(var(--raised))] p-3 text-sm leading-relaxed">
          <span className="text-[rgb(var(--warn))]">No accuracy is reported</span> —{" "}
          <span className="text-[rgb(var(--muted))]">{diagnosis.absent}.</span>
        </p>
        <p className="mt-4 text-sm leading-relaxed text-[rgb(var(--muted))]">
          <span className="text-[rgb(var(--ink))]">And there is no cheap version of it.</span>{" "}
          {diagnosis.no_shortcut}
        </p>
        <p className="mt-4 text-xs leading-relaxed text-[rgb(var(--faint))]">
          The remaining {diagnosis.unscoreable} scenarios are not failures and not gaps:{" "}
          {diagnosis.unscoreable_reason}. Counting them as diagnosis misses would penalise a
          system for correctly doing nothing, which is the error that would most flatter a
          different design.
        </p>
        <p className="mt-3 text-xs leading-relaxed text-[rgb(var(--faint))]">
          <span className="text-[rgb(var(--ink))]">A known weakness of the task itself:</span>{" "}
          {diagnosis.leakage}
        </p>
      </Panel>

      <Panel
        title="The arms, and what each has behind it"
        aside={`${evaluation.arms_with_data} of ${evaluation.arms_declared} have data`}
      >
        <ul className="space-y-3">
          {arms.map((arm) => (
            <li key={arm.name} data-arm={arm.name} className="flex flex-wrap gap-x-3 text-sm">
              <span className="mono w-32 shrink-0 text-[rgb(var(--ink))]">{arm.name}</span>
              <span className="min-w-0 flex-1 text-[rgb(var(--muted))]">
                {arm.records ? (
                  <>
                    <span className="tnum">{arm.records}</span> records over{" "}
                    <span className="tnum">{arm.scenarios}</span> scenarios,{" "}
                    <span className="tnum">{arm.repeats}</span>{" "}
                    {arm.repeats === 1 ? "run each" : "runs each"}
                  </>
                ) : (
                  <span className="text-[rgb(var(--warn))]">absent — {arm.absent}</span>
                )}
              </span>
            </li>
          ))}
        </ul>
        <p className="mt-4 text-xs leading-relaxed text-[rgb(var(--faint))]">
          {evaluation.records_note}
        </p>
      </Panel>

      <Panel title="The corpus" aside={`${corpus.scenarios} scenarios, authored before the logic`}>
        <div className="grid gap-8 sm:grid-cols-2">
          <div>
            <p className="label mb-3">by category</p>
            <Distribution
              bands={Object.entries(corpus.by_category).map(([label, count]) => ({
                label,
                count,
                status: "neutral" as const,
              }))}
            />
          </div>
          <div>
            <p className="label mb-3">by correct outcome</p>
            <Distribution
              bands={[
                { label: "remediate", count: corpus.by_outcome.remediate, status: "ok" as const },
                { label: "escalate", count: corpus.by_outcome.escalate, status: "warning" as const },
                {
                  label: "do nothing",
                  count: corpus.by_outcome.nothing,
                  status: "neutral" as const,
                },
              ]}
            />
            <p className="mt-4 text-xs leading-relaxed text-[rgb(var(--faint))]">
              {corpus.by_outcome.nothing + corpus.by_outcome.escalate} of {corpus.scenarios}{" "}
              scenarios are correct to <em>not</em> remediate. That balance is the reason the
              review&rsquo;s first finding bites: an arm that refuses to act scores well on
              those by doing nothing, so &ldquo;refused more often than a runbook&rdquo; is
              close to true by construction unless the remediate half is run too.
            </p>
          </div>
        </div>
      </Panel>

      <Panel
        title="Faults that cannot be injected"
        aside={`${injection.blocked.length} types, ${injection.blocked_scenarios} scenarios`}
      >
        <p className="text-sm leading-relaxed text-[rgb(var(--muted))]">
          The harness injects real faults into a running five-service stack. Some of the corpus
          describes faults a stack like that cannot be made to have, and those are excluded by
          name rather than approximated — an infrastructure fault standing in for an intrusion
          would decide the answer in advance.
        </p>
        <dl className="mt-4 space-y-3 text-sm">
          {injection.blocked.map((blocked) => (
            <div key={blocked.fault} className="flex min-w-0 flex-wrap gap-x-3">
              <dt className="mono shrink-0 text-[rgb(var(--ink))]">
                {blocked.fault}{" "}
                <span className="tnum text-xs text-[rgb(var(--faint))]">
                  ({blocked.scenarios})
                </span>
              </dt>
              <dd className="min-w-0 flex-1 break-words text-[rgb(var(--muted))]">
                {blocked.reason}
              </dd>
            </div>
          ))}
        </dl>
        <p className="mt-4 text-xs leading-relaxed text-[rgb(var(--faint))]">
          <span className="text-[rgb(var(--ink))]">This is a confound, not just a limit.</span>{" "}
          Security is one of the blocked categories, and it is the category this product is
          about — so any result from an injected run describes the infrastructure half of the
          corpus. Reported per category for that reason, never as one average.{" "}
          {injection.injectable.length} fault types can be injected:{" "}
          <span className="mono">{injection.injectable.join(", ")}</span>.
        </p>
      </Panel>

      <p className="text-xs leading-relaxed text-[rgb(var(--faint))]">
        {evaluation.note} The plan these gaps are tracked against is in{" "}
        <Link
          href="https://github.com/preetraval45/PASHUPATASTRA/blob/main/docs/REBUILD.md"
          className="focusable rounded underline decoration-dotted"
        >
          the delivery plan
        </Link>
        , and the numbers this project <em>can</em> currently recount are on{" "}
        <Link href="/impact" className="focusable rounded underline decoration-dotted">
          impact
        </Link>
        .
      </p>
    </Page>
  );
}
