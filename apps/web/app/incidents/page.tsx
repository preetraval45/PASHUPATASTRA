import { IncidentView } from "@/components/incident";
import { Scenarios } from "@/components/scenarios";
import { TriageItem, TriageList } from "@/components/triage";
import { Empty, Offline, Page } from "@/components/ui";
import { getActions, getIncidents } from "@/lib/api";

import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Incidents",
  description:
    "Open security incidents, each with the evidence behind its diagnosis and the alternative reading it ruled out.",
};

export const dynamic = "force-dynamic";

export default async function IncidentsPage() {
  const [incidents, actions] = await Promise.all([getIncidents(), getActions()]);
  if (!incidents) return <Offline />;

  const risk = new Map((actions ?? []).map((a) => [a.id, a.base_risk]));

  return (
    <Page
      title="Incidents"
      description="One incident per failure, not one per alert. Every diagnosis cites the telemetry that supports it."
    >
      {incidents.length === 0 ? (
        <Empty art="quiet" title="No incidents.">
          They appear when Drishti correlates failures that are adjacent in the topology
          graph and in time — two unrelated accounts alerting in the same minute stay two
          incidents.
        </Empty>
      ) : (
        <>
          <Scenarios incidents={incidents} />
          {/* Each card is a screen tall, so this list is the one place on the
              site where reaching the next incident costs a scroll — which is
              what `j`/`k` are for. The compact list on the overview is not
              wrapped: every row there is one link and Tab already reaches it,
              so a second way to move would be a duplicate, not an accelerant. */}
          <TriageList>
            {incidents.map((incident, index) => (
              <TriageItem
                key={incident.id}
                index={index}
                href={`/incidents/${encodeURIComponent(incident.id)}`}
              >
                <IncidentView incident={incident} risk={risk} linkToDetail />
              </TriageItem>
            ))}
          </TriageList>
        </>
      )}
    </Page>
  );
}
