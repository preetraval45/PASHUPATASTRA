import type { Metadata } from "next";
import Link from "next/link";

import { Badge, Empty, Offline, Page, Panel, statusForSeverity } from "@/components/ui";
import { getScenarios } from "@/lib/api";

export const metadata: Metadata = {
  title: "Blue team",
  description:
    "Work an incident forwards from a single alert: investigate, diagnose, choose a proportionate response, and see what you missed.",
};

export const dynamic = "force-dynamic";

export default async function BlueTeamPage() {
  const scenarios = await getScenarios();
  if (scenarios === null) return <Offline />;

  return (
    <Page
      title="Blue team"
      description="One alert, and the rest is yours. The console shows finished investigations; this asks you to do one."
    >
      <Panel title="How it is scored">
        <ul className="space-y-2 text-sm text-[rgb(var(--muted))]">
          <li>
            <strong className="text-[rgb(var(--ink))]">Diagnosis, 50.</strong> One
            of the explanations is plausible and wrong.
          </li>
          <li>
            <strong className="text-[rgb(var(--ink))]">Response, 30.</strong>{" "}
            Proportionality counts. Doing too little and doing too much are both
            marked down.
          </li>
          <li>
            <strong className="text-[rgb(var(--ink))]">Investigation, 20.</strong>{" "}
            Did you open the evidence that rules the wrong explanation out, or
            were you right by luck?
          </li>
        </ul>
      </Panel>

      {scenarios.length === 0 ? (
        <Panel title="Nothing to play">
          <Empty art="ledger" title="No scenarios are loaded." />
        </Panel>
      ) : (
        <Panel title="Scenarios" aside={`${scenarios.length} available`}>
          <ol className="divide-y divide-[rgb(var(--edge))]">
            {scenarios.map((scenario) => (
              <li key={scenario.incident_id} className="py-3 first:pt-0 last:pb-0">
                <Link
                  href={`/blue-team/${encodeURIComponent(scenario.incident_id)}`}
                  className="focusable group flex flex-wrap items-center gap-x-3 gap-y-2 rounded"
                >
                  <Badge status={statusForSeverity(scenario.severity)}>
                    {scenario.severity}
                  </Badge>
                  {/* The opening alert and nothing else. A list that summarised
                      each incident would answer the exercise before it opened. */}
                  <span className="min-w-0 flex-1 text-sm group-hover:text-[rgb(var(--astra))]">
                    {scenario.opening}
                  </span>
                  <span className="text-xs text-[rgb(var(--faint))]">
                    {scenario.steps} steps to reconstruct
                  </span>
                </Link>
              </li>
            ))}
          </ol>
        </Panel>
      )}
    </Page>
  );
}
