import { Filter, FilterRow } from "@/components/filter";
import { IncidentView } from "@/components/incident";
import { Scenarios } from "@/components/scenarios";
import { TriageItem, TriageList } from "@/components/triage";
import { Empty, Offline, Page } from "@/components/ui";
import { getActions, getIncidents } from "@/lib/api";
import { SEVERITIES, applyQuery, hrefFor, parseQuery } from "@/lib/incidentfilter";

import type { Metadata } from "next";
import Link from "next/link";

export const metadata: Metadata = {
  title: "Incidents",
  description:
    "Open security incidents, each with the evidence behind its diagnosis and the alternative reading it ruled out.",
};

export const dynamic = "force-dynamic";

export default async function IncidentsPage({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const q = parseQuery(await searchParams);
  const [all, actions] = await Promise.all([getIncidents(), getActions()]);
  if (!all) return <Offline />;
  const incidents = applyQuery(all, q);
  const filtered = q.severity !== null || q.status !== null;

  const risk = new Map((actions ?? []).map((a) => [a.id, a.base_risk]));

  return (
    <Page
      title="Incidents"
      description="One incident per failure, not one per alert. Every diagnosis cites the telemetry that supports it."
    >
      {all.length > 0 && (
        <div className="mb-6 space-y-3">
          <FilterRow label="Status">
            <Filter href={hrefFor(q, { status: null })} label="All" active={!q.status} />
            <Filter href={hrefFor(q, { status: "open" })} label="Open" active={q.status === "open"} />
            <Filter href={hrefFor(q, { status: "closed" })} label="Closed" active={q.status === "closed"} />
          </FilterRow>
          <FilterRow label="Severity">
            <Filter href={hrefFor(q, { severity: null })} label="Any" active={!q.severity} />
            {SEVERITIES.map((s) => (
              <Filter key={s} href={hrefFor(q, { severity: s })} label={s} active={q.severity === s} />
            ))}
          </FilterRow>
          <FilterRow label="Sort">
            <Filter href={hrefFor(q, { sort: "newest" })} label="Newest" active={q.sort === "newest"} />
            <Filter href={hrefFor(q, { sort: "severity" })} label="Most severe" active={q.sort === "severity"} />
          </FilterRow>
          <p className="text-xs text-[rgb(var(--faint))]" aria-live="polite">
            Showing {incidents.length} of {all.length}
          </p>
        </div>
      )}
      {all.length > 0 && incidents.length === 0 && filtered ? (
        <Empty art="quiet" title="Nothing matches these filters.">
          {all.length} incident{all.length === 1 ? "" : "s"} exist under other filters.{" "}
          <Link className="underline underline-offset-4" href="/incidents">
            Show all
          </Link>
          .
        </Empty>
      ) : incidents.length === 0 ? (
        <Empty art="quiet" title="No incidents.">
          They appear when Drishti correlates failures that are adjacent in the topology
          graph and in time — two unrelated accounts alerting in the same minute stay two
          incidents.
        </Empty>
      ) : (
        <>
          <Scenarios incidents={all} />
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
