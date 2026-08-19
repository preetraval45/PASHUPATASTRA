import { IncidentView } from "@/components/incident";
import { Empty, Offline, Page } from "@/components/ui";
import { getActions, getIncidents } from "@/lib/api";

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
        <Empty title="No incidents.">
          They appear when Drishti correlates failures that are adjacent in the topology
          graph and in time — two unrelated accounts alerting in the same minute stay two
          incidents.
        </Empty>
      ) : (
        incidents.map((incident) => (
          <IncidentView key={incident.id} incident={incident} risk={risk} linkToDetail />
        ))
      )}
    </Page>
  );
}
