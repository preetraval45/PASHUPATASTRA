import Link from "next/link";
import type { Metadata } from "next";
import { notFound } from "next/navigation";

import {
  Ago,
  Badge,
  Empty,
  Evidence,
  Ident,
  KeyValue,
  Offline,
  Page,
  Panel,
  statusForSeverity,
} from "@/components/ui";
import { apiIsReachable, getEntity, type EntityEvent } from "@/lib/api";

export const dynamic = "force-dynamic";

/** The entity key, so a tab and a search result both name the thing they show
 *  rather than all reading "Pashupatastra". */
export async function generateMetadata({
  params,
}: {
  params: Promise<{ key: string[] }>;
}): Promise<Metadata> {
  const key = (await params).key.map(decodeURIComponent).join("/");
  return {
    title: key,
    description: `What ${key} can reach, and what it has been observed doing.`,
  };
}

/**
 * Entity keys are `kind:name` and Kubernetes names carry a `/`, so the route is
 * a catch-all and the segments are rejoined here. Encoding the slash instead
 * would make the URL unreadable, and an operator pastes these into tickets.
 */
export default async function EntityPage({ params }: { params: Promise<{ key: string[] }> }) {
  const { key: segments } = await params;
  const key = segments.map(decodeURIComponent).join("/");
  const detail = await getEntity(key);

  if (detail === null) {
    // `null` covers both "no such entity" and "the API is unreachable". Without
    // asking a second question, following a causal-chain link to an entity that
    // is simply not in the graph reported that the whole system was down.
    if (!(await apiIsReachable())) return <Offline />;
    notFound();
  }
  if (!detail.entity) notFound();

  const { entity, blast_radius: blast, events } = detail;
  const worst = worstSeverity(events);

  return (
    <Page
      title={entity.name}
      description={`${entity.kind}${entity.namespace ? ` · ${entity.namespace}` : ""}`}
      actions={
        <Link
          href="/infrastructure"
          className="focusable rounded border border-[rgb(var(--edge-strong))] px-3 py-1.5 text-sm hover:bg-[rgb(var(--raised))]"
        >
          ← Map
        </Link>
      }
    >
      <Panel>
        <div className="flex flex-wrap items-center gap-3">
          <Ident>{entity.key}</Ident>
          <Badge status={statusForSeverity(worst)}>{worst ?? "no recent data"}</Badge>
          <span className="ml-auto text-xs text-[rgb(var(--faint))]">
            last seen <Ago at={entity.last_seen} />
          </span>
        </div>

        <dl className="mt-5 grid gap-5 sm:grid-cols-2 lg:grid-cols-4">
          <KeyValue label="Kind">{entity.kind}</KeyValue>
          <KeyValue label="Namespace">{entity.namespace ?? "—"}</KeyValue>
          <KeyValue label="Owner">{entity.owner ?? "unassigned"}</KeyValue>
          <KeyValue label="First seen">
            <Ago at={entity.first_seen} />
          </KeyValue>
        </dl>
      </Panel>

      <Panel
        title="Blast radius"
        aside={`${blast.entity_count} entities · ~${blast.estimated_users.toLocaleString()} users`}
      >
        {blast.entity_count === 0 ? (
          <Empty art="reach" title="Nothing observed reaching this." action={{ href: "/infrastructure", label: "Open the map →" }}>
            Either nothing can reach it, or nothing has yet shown what does — an observed
            connection or session creates an edge; seeing the entity alone does not.
          </Empty>
        ) : (
          <>
            <p className="text-sm text-[rgb(var(--muted))]">
              If <Ident>{entity.name}</Ident> fails, these break with it:
            </p>
            <ul className="mt-4 flex flex-wrap gap-2">
              {blast.affected.map((affected) => (
                <li key={affected}>
                  <Link
                    href={`/entity/${affected}`}
                    className="focusable mono rounded border border-[rgb(var(--edge))] px-2 py-1 text-xs hover:bg-[rgb(var(--raised))]"
                  >
                    {affected}
                  </Link>
                </li>
              ))}
            </ul>
            <p className="mt-4 text-xs text-[rgb(var(--faint))]">
              This number is an input to risk scoring: a larger blast radius raises an
              action&rsquo;s effective risk and can escalate it past autonomy.
            </p>
          </>
        )}
      </Panel>

      <Panel title="Recent events" aside={`${events.length} newest`}>
        {events.length === 0 ? (
          <Empty
            art="signal"
            title="No events recorded for this entity yet."
            action={{ href: "/incidents", label: "Open a scenario →" }}
          >
            It is in the graph because something referenced it — an owner, or the other
            end of a connection — but no collector has reported on it directly.
          </Empty>
        ) : (
          <ol className="divide-y divide-[rgb(var(--edge))]">
            {events.map((event) => (
              <EventRow key={event.id} event={event} />
            ))}
          </ol>
        )}
      </Panel>
    </Page>
  );
}

function EventRow({ event }: { event: EntityEvent }) {
  return (
    <li className="py-3 first:pt-0 last:pb-0">
      <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
        <span className="w-16 shrink-0 text-xs text-[rgb(var(--faint))]">
          <Ago at={event.occurred_at} />
        </span>
        {event.severity && (
          <Badge status={statusForSeverity(event.severity)}>{event.severity}</Badge>
        )}
        <span className="text-[11px] uppercase tracking-wide text-[rgb(var(--muted))]">
          {event.event_class.replace(/_/g, " ")}
        </span>
        <span className="text-sm">{summarize(event)}</span>
        <span className="ml-auto text-xs text-[rgb(var(--faint))]">{event.source}</span>
      </div>
      {/* Provenance is mandatory on every event, so it is always shown: any
          claim downstream can be traced back to a record a human can re-fetch. */}
      {event.provenance.query && <Evidence refs={[event.provenance.query]} />}
    </li>
  );
}

function summarize(event: EntityEvent): string {
  const p = event.payload as Record<string, string | number>;
  switch (event.event_class) {
    case "metric":
      return `${p.name} = ${p.value}${p.unit === "percent" ? "%" : ""}`;
    case "state_change":
      return p.previous_state
        ? `${p.previous_state} → ${p.new_state}`
        : String(p.new_state ?? "");
    case "deployment":
      return p.previous_version
        ? `${p.service}: ${p.previous_version} → ${p.version}`
        : `${p.service} at ${p.version}`;
    case "trace":
      return `${p.status} in ${p.duration_ms}ms`;
    case "log":
      return String(p.message ?? "");
    case "security":
      return String(p.detection_type ?? "");
    default:
      return "";
  }
}

/** Worst, not latest — an entity that went critical then reported info seconds
 *  later is flapping, and the newest reading would hide the incident. */
function worstSeverity(events: EntityEvent[]): "critical" | "warning" | "info" | null {
  const recent = events.filter(
    (e) => Date.now() - new Date(e.observed_at).getTime() < 15 * 60 * 1000,
  );
  if (recent.some((e) => e.severity === "critical")) return "critical";
  if (recent.some((e) => e.severity === "warning")) return "warning";
  if (recent.some((e) => e.severity === "info")) return "info";
  return null;
}
