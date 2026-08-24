import type { Metadata } from "next";
import Link from "next/link";

import { BuiltWith } from "@/components/builtwith";
import { Badge, Offline, Page, Panel, statusForRisk } from "@/components/ui";
import { getActions, getHealth, getPolicyModel, tierLabel } from "@/lib/api";

/**
 * For the visitor who got interested and now wants to know whether to believe
 * it.
 *
 * Every claim the landing page makes has a section here that substantiates it,
 * and substantiating means *showing the thing*, not describing it. The risk
 * table is generated from the policy engine, the action counts are counted from
 * the registry, and the two execution gates are read from the running
 * deployment — because a page that restates them from memory is a second answer
 * to "who may approve this", and the day the two disagree the wrong one is the
 * one on the marketing site.
 *
 * This is where the delisted Audit page earns its keep. The argument it makes
 * is "you can check every claim", which is an argument rather than a dashboard,
 * and it belongs beside the claims rather than in the navigation.
 */

export const metadata: Metadata = {
  title: "How it works",
  description:
    "The seven stages, the risk tiers and who may authorise each, the two gates that keep this deployment in dry run, and the audit trail you can read yourself.",
};

export const dynamic = "force-dynamic";

const STAGES = [
  ["Observe", "Signals are normalised into one event shape, whatever emitted them."],
  [
    "Understand",
    "Related events become one incident with a causal chain, each step mapped to an ATT&CK technique and citing the signal it rests on.",
  ],
  ["Predict", "Blast radius over observed access — what else this can reach."],
  ["Decide", "Each action is scored and assigned a tier before anyone sees it."],
  ["Act", "Execution requires a verdict. There is no path around the policy engine."],
  ["Verify", "Observed state is compared against what the action said it expected."],
  ["Learn", "Outcomes are recorded against the prediction that preceded them."],
];

export default async function HowItWorksPage() {
  const [policy, actions, health] = await Promise.all([
    getPolicyModel(),
    getActions(),
    getHealth(),
  ]);

  if (policy === null) return <Offline />;

  const registry = actions ?? [];
  const readOnly = registry.filter((action) => action.read_only);
  const irreversible = registry.filter((action) => action.irreversible);
  const withRollback = registry.filter((action) => action.rollback_action_id);

  return (
    <Page
      title="How it works"
      description="Every claim on the front page, with the thing that backs it. The numbers below are read from the running system, not written into this page."
    >
      {/* --- the loop ---------------------------------------------------- */}
      <Panel title="The seven stages" aside="Observe → … → Learn">
        <ol className="space-y-3">
          {STAGES.map(([name, what], index) => (
            <li key={name} className="flex gap-4">
              <span className="mono w-6 shrink-0 text-xs text-[rgb(var(--faint))]">
                {String(index + 1).padStart(2, "0")}
              </span>
              <span className="min-w-0">
                <span className="text-sm font-medium">{name}</span>
                <span className="ml-2 text-sm text-[rgb(var(--muted))]">{what}</span>
              </span>
            </li>
          ))}
        </ol>
        <p className="mt-4 border-t border-[rgb(var(--edge))] pt-3 text-xs text-[rgb(var(--faint))]">
          Most tools stop after the second. Everything from Decide onwards is
          what makes the difference between explaining an incident and closing
          it.
        </p>
      </Panel>

      <Panel title="Steps are named in a shared vocabulary" aside="MITRE ATT&CK">
        <p className="text-sm leading-relaxed text-[rgb(var(--muted))]">
          Each step in a causal chain carries the technique it corresponds to,
          so a reader who does not recognise a described behaviour can go and
          read what it is. The identifier is a citation, not a finding — it says
          what a step resembles, not that the step is proven.
        </p>
        <ul className="mt-3 space-y-1.5 text-sm">
          {[
            ["T1071.001", "Web Protocols", "Command and Control"],
            ["T1021.002", "SMB/Windows Admin Shares", "Lateral Movement"],
            ["T1053.005", "Scheduled Task", "Persistence"],
          ].map(([id, name, tactic]) => (
            <li key={id} className="flex flex-wrap items-baseline gap-x-2">
              <a
                href={`https://attack.mitre.org/techniques/${id.replace(".", "/")}/`}
                target="_blank"
                rel="noopener noreferrer"
                className="focusable mono rounded text-xs underline decoration-dotted underline-offset-2 hover:text-[rgb(var(--astra))]"
              >
                {id}
              </a>
              <span className="text-[rgb(var(--muted))]">{name}</span>
              <span className="text-xs text-[rgb(var(--faint))]">· {tactic}</span>
            </li>
          ))}
        </ul>
        <p className="mt-3 text-xs text-[rgb(var(--faint))]">
          Those three are the chain of one incident on this site, in order.
        </p>
      </Panel>

      {/* --- risk tiers, generated --------------------------------------- */}
      <Panel
        title="Risk decides who may authorise"
        aside="generated from the policy engine"
      >
        <div className="overflow-x-auto">
          <table className="stacked w-full min-w-[34rem] text-left text-sm">
            <caption className="sr-only">
              Risk bands, the tier each produces, and who may authorise it
            </caption>
            <thead>
              <tr className="border-b border-[rgb(var(--edge))] text-[rgb(var(--muted))]">
                <th scope="col" className="py-2 pr-4 font-medium">Effective risk</th>
                <th scope="col" className="py-2 pr-4 font-medium">Tier</th>
                <th scope="col" className="py-2 font-medium">Who may authorise</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[rgb(var(--edge))]">
              {policy.tiers.map((band) => (
                <tr key={band.tier}>
                  <td data-label="Effective risk" className="mono py-2 pr-4 text-xs">
                    {band.min_risk}–{band.max_risk}
                  </td>
                  <td data-label="Tier" className="py-2 pr-4">
                    <Badge status={statusForRisk(band.max_risk)}>
                      {tierLabel(band.tier)}
                    </Badge>
                  </td>
                  <td
                    data-label="Who may authorise"
                    className="py-2 text-[rgb(var(--muted))]"
                  >
                    {band.approvers.length > 0
                      ? band.approvers.join(", ")
                      : band.tier === "autonomous"
                        ? "nobody — it runs unattended"
                        : "nobody — it does not run"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <p className="mt-4 text-sm leading-relaxed text-[rgb(var(--muted))]">
          Risk starts from the action&rsquo;s own score and rises with the
          situation: how far the blast radius reaches, how confident the
          diagnosis is, whether the action can be undone, and whether it has
          been run here before. Adjustments only ever raise it — an action
          cannot argue its way into a lower tier — and a blast radius over{" "}
          <span className="mono text-[rgb(var(--ink))]">
            {policy.escalation.blast_radius_entities}
          </span>{" "}
          entities or{" "}
          <span className="mono text-[rgb(var(--ink))]">
            {policy.escalation.blast_radius_users}
          </span>{" "}
          users escalates it a whole tier on its own.
        </p>

        <p className="mt-3 text-sm text-[rgb(var(--muted))]">
          <Link
            href="/actions"
            className="focusable rounded underline decoration-dotted underline-offset-2 hover:text-[rgb(var(--astra))]"
          >
            The {registry.length} registered actions and their scores →
          </Link>
        </p>
      </Panel>

      {/* --- what the registry actually requires -------------------------- */}
      <Panel title="What an action has to declare" aside="counted from the registry">
        <dl className="grid gap-4 sm:grid-cols-3">
          {[
            {
              value: `${withRollback.length}/${registry.length}`,
              label: "declare a rollback",
              body: "An action states how to undo it before it is allowed to run. The exceptions are the reads and the ones that are irreversible by nature.",
            },
            {
              value: `${readOnly.length}`,
              label: "change nothing",
              body: "Read-only is declared on the action, not inferred from its risk — which is why the assistant can be given these and nothing else.",
            },
            {
              value: `${irreversible.length}`,
              label: "irreversible",
              body: "Marked as such and never autonomous, whatever their score. There is no undo to declare.",
            },
          ].map((fact) => (
            <div key={fact.label}>
              <dt className="text-2xl font-semibold tabular-nums">{fact.value}</dt>
              <dd className="label mb-1">{fact.label}</dd>
              <dd className="text-xs leading-relaxed text-[rgb(var(--muted))]">
                {fact.body}
              </dd>
            </div>
          ))}
        </dl>
      </Panel>

      {/* --- the two gates ------------------------------------------------ */}
      <Panel title="Two gates, and both are shut" aside="read from this deployment">
        <p className="mb-4 text-sm leading-relaxed text-[rgb(var(--muted))]">
          One flag is one accident away from a production outage, so live
          execution needs two independent things to be true at once.
        </p>
        <dl className="space-y-3">
          <Gate
            name="Dry run"
            open={!policy.gates.dry_run}
            detail={
              policy.gates.dry_run
                ? "On. Actions are evaluated and recorded; nothing executes."
                : "Off. Actions may execute if the second gate also opens."
            }
          />
          <Gate
            name="Environment on the live list"
            open={policy.gates.live_environments.includes(policy.gates.environment)}
            detail={
              policy.gates.live_environments.length === 0
                ? `No environment is listed as live. This one reports itself as "${policy.gates.environment}".`
                : `Live: ${policy.gates.live_environments.join(", ")}. This one is "${policy.gates.environment}".`
            }
          />
        </dl>
        <p className="mt-4 border-t border-[rgb(var(--edge))] pt-3 text-sm">
          {policy.gates.live_execution_enabled ? (
            <span className="text-[rgb(var(--crit))]">
              ▲ Both gates are open. This deployment can execute.
            </span>
          ) : (
            <span className="text-[rgb(var(--muted))]">
              Both must open before anything runs. On this deployment neither
              does, which is why every verdict you see here is a decision that
              was recorded rather than carried out.
            </span>
          )}
        </p>
      </Panel>

      {/* --- the audit argument ------------------------------------------- */}
      <Panel title="You can check every claim" aside="which is the point">
        <p className="text-sm leading-relaxed text-[rgb(var(--muted))]">
          Observations, hypotheses, decisions, approvals, executions and
          verifications are append-only records, written before an action runs
          rather than after. Every citation on this site resolves to the event
          it names, and every answer the assistant gives is checked against what
          was actually retrieved before it is shown.
        </p>
        <ul className="mt-4 space-y-2 text-sm">
          <li>
            <Link
              href="/audit"
              className="focusable rounded underline decoration-dotted underline-offset-2 hover:text-[rgb(var(--astra))]"
            >
              The audit trail
            </Link>
            <span className="text-[rgb(var(--muted))]">
              {" "}
              — {health?.audit_records ?? "the"} records, and every agent turn
              carries the model, the prompt version and the lookups it made.
            </span>
          </li>
          <li>
            <Link
              href="/observatory"
              className="focusable rounded underline decoration-dotted underline-offset-2 hover:text-[rgb(var(--astra))]"
            >
              The Observatory
            </Link>
            <span className="text-[rgb(var(--muted))]">
              {" "}
              — real advisories from CISA and abuse.ch, polled hourly, each
              linked to the publisher. A community report is never labelled
              confirmed.
            </span>
          </li>
          <li>
            <Link
              href="/blue-team"
              className="focusable rounded underline decoration-dotted underline-offset-2 hover:text-[rgb(var(--astra))]"
            >
              Blue team mode
            </Link>
            <span className="text-[rgb(var(--muted))]">
              {" "}
              — work an incident yourself and see whether the reasoning holds up
              when you are the one doing it.
            </span>
          </li>
        </ul>
      </Panel>

      <Panel title="Built with" aside="read from the repository">
        <BuiltWith />
      </Panel>

      <p className="text-xs text-[rgb(var(--faint))]">
        The incidents on this site are written scenarios and are labelled as
        such. The threat intelligence is real. Nothing here executes anything.
      </p>
    </Page>
  );
}

function Gate({
  name,
  open,
  detail,
}: {
  name: string;
  open: boolean;
  detail: string;
}) {
  return (
    <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
      <dt className="flex w-56 shrink-0 items-center gap-2 text-sm">
        <span
          aria-hidden="true"
          className={open ? "text-[rgb(var(--crit))]" : "text-[rgb(var(--ok))]"}
        >
          {open ? "○" : "●"}
        </span>
        {name}
        <span className="sr-only">{open ? "open" : "shut"}</span>
      </dt>
      <dd className="min-w-0 flex-1 text-sm text-[rgb(var(--muted))]">{detail}</dd>
    </div>
  );
}
