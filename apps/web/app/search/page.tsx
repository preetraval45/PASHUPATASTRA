import Link from "next/link";

import { Ago, Badge, Empty, Ident, Offline, Page, Panel, statusForSeverity } from "@/components/ui";
import { getHealth, getIncidents, getTopology, isInfrastructure } from "@/lib/api";

export const dynamic = "force-dynamic";

const LIMIT = 25;

export default async function SearchPage({
  searchParams,
}: {
  searchParams: Promise<{ q?: string }>;
}) {
  const query = ((await searchParams).q ?? "").trim();
  const [health, topology, incidents] = await Promise.all([
    getHealth(),
    getTopology(),
    getIncidents(),
  ]);

  if (!health) return <Offline />;

  const needle = query.toLowerCase();
  const entities = query
    ? (topology?.nodes ?? []).filter(
        (node) =>
          node.name.toLowerCase().includes(needle) ||
          node.key.toLowerCase().includes(needle) ||
          (node.namespace ?? "").toLowerCase().includes(needle),
      )
    : [];

  // Incidents match on their id or on any entity they affect: during an
  // incident the name an analyst has is usually an account or a host, not an
  // incident number, and demanding the number would make search useless at
  // exactly the moment it is needed.
  const matched = query
    ? (incidents ?? []).filter(
        (incident) =>
          incident.id.toLowerCase().includes(needle) ||
          incident.affected_entities.some((entity) =>
            entity.name.toLowerCase().includes(needle),
          ),
      )
    : [];

  const total = entities.length + matched.length;

  return (
    <Page
      title={query ? `Search: ${query}` : "Search"}
      description={
        query
          ? `${total} match${total === 1 ? "" : "es"} across ${topology?.nodes.length ?? 0} entities and ${incidents?.length ?? 0} incidents.`
          : "Find an entity or an incident by name. Press / anywhere to focus the field."
      }
    >
      {!query && (
        <Empty art="search" title="Nothing searched yet" action={{ href: "/incidents", label: "Open a scenario →" }}>
          Type an account, host, asset, or incident id.
        </Empty>
      )}

      {query && total === 0 && (
        <Empty art="search" title={`No entity or incident matches "${query}"`} action={{ href: "/infrastructure", label: "Open the map →" }}>
          Search covers the topology graph and the incident list as the API reports them. An
          entity the platform has never observed will not appear.
        </Empty>
      )}

      {matched.length > 0 && (
        <Panel title={`Incidents (${matched.length})`}>
          <ul className="divide-y divide-[rgb(var(--edge))]">
            {matched.slice(0, LIMIT).map((incident) => (
              <li key={incident.id}>
                <Link
                  href={`/incidents/${encodeURIComponent(incident.id)}`}
                  className="focusable flex flex-wrap items-center gap-x-3 gap-y-1 px-4 py-3 hover:bg-[rgb(var(--raised))]"
                >
                  <Ident>{incident.id}</Ident>
                  <Badge status={statusForSeverity(incident.severity)}>{incident.severity}</Badge>
                  <span className="text-sm text-[rgb(var(--muted))]">
                    {incident.state.replace(/_/g, " ")}
                  </span>
                  <span className="ml-auto text-xs text-[rgb(var(--faint))]">
                    <Ago at={incident.opened_at} />
                  </span>
                </Link>
              </li>
            ))}
          </ul>
        </Panel>
      )}

      {entities.length > 0 && (
        <Panel title={`Entities (${entities.length})`}>
          <ul className="divide-y divide-[rgb(var(--edge))]">
            {entities.slice(0, LIMIT).map((node) => (
              <li key={node.key}>
                <Link
                  href={`/entity/${node.key.split("/").map(encodeURIComponent).join("/")}`}
                  className="focusable flex flex-wrap items-center gap-x-3 gap-y-1 px-4 py-3 hover:bg-[rgb(var(--raised))]"
                >
                  <Ident>{node.name}</Ident>
                  <span className="text-xs uppercase tracking-wide text-[rgb(var(--faint))]">
                    {node.kind}
                  </span>
                  {node.namespace && (
                    <span className="text-xs text-[rgb(var(--muted))]">{node.namespace}</span>
                  )}
                  {isInfrastructure(node) && (
                    <span className="text-[11px] text-[rgb(var(--faint))]">platform</span>
                  )}
                  {node.severity && (
                    <Badge status={statusForSeverity(node.severity)}>{node.severity}</Badge>
                  )}
                  <span className="ml-auto text-xs text-[rgb(var(--faint))]">
                    <Ago at={node.last_seen} />
                  </span>
                </Link>
              </li>
            ))}
          </ul>
        </Panel>
      )}

      {(entities.length > LIMIT || matched.length > LIMIT) && (
        <p className="text-xs text-[rgb(var(--faint))]">
          Showing the first {LIMIT} of each. Narrow the query rather than scrolling — a list
          longer than a screen is not an answer.
        </p>
      )}
    </Page>
  );
}
