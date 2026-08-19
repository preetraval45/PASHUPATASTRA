import Link from "next/link";
import { notFound } from "next/navigation";

import { Ago, Badge, Ident, KeyValue, Offline, Page, Panel, statusForSeverity } from "@/components/ui";
import { apiIsReachable, getEvent } from "@/lib/api";

export const dynamic = "force-dynamic";

/**
 * One piece of evidence.
 *
 * Every hypothesis and every causal step cites evidence by id. This page is
 * what makes those ids mean something: a reader who does not believe a claim
 * can follow it to the observation it rests on, and see where that observation
 * came from. Without it the citation is decoration — it looks checkable, so it
 * gets taken on trust, and a fabricated reference is indistinguishable from a
 * real one.
 */
export default async function EvidencePage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id: raw } = await params;
  const id = decodeURIComponent(raw);
  const event = await getEvent(id);

  if (event === null) {
    // `null` is both "no such event" and "the API is unreachable". Asking a
    // second question separates them, so a missing citation is not reported as
    // an outage.
    if (!(await apiIsReachable())) return <Offline />;
    notFound();
  }

  const scripted = event.provenance.source_system === "demo-scenario";
  const summary = event.labels?.summary;

  return (
    <Page
      title={id}
      description="One observation, and where it came from."
      actions={
        event.entity_key ? (
          <Link
            href={`/entity/${event.entity_key.split("/").map(encodeURIComponent).join("/")}`}
            className="focusable rounded border border-[rgb(var(--edge-strong))] px-3 py-1.5 text-sm hover:bg-[rgb(var(--raised))]"
          >
            View entity →
          </Link>
        ) : undefined
      }
    >
      <Panel title="What was observed">
        <div className="flex flex-wrap items-center gap-3">
          {event.severity && (
            <Badge status={statusForSeverity(event.severity)}>{event.severity}</Badge>
          )}
          <span className="text-xs uppercase tracking-wide text-[rgb(var(--faint))]">
            {event.event_class}
          </span>
          <span className="ml-auto text-xs text-[rgb(var(--faint))]">
            <Ago at={event.occurred_at} />
          </span>
        </div>
        {summary && <p className="mt-4 text-sm">{summary}</p>}
      </Panel>

      {/* Provenance is the point of the page. An observation whose origin cannot
          be named is not evidence, whatever it says. */}
      <Panel title="Where it came from">
        <dl className="grid gap-4 sm:grid-cols-2">
          <KeyValue label="Source system">
            <Ident>{event.provenance.source_system}</Ident>
          </KeyValue>
          <KeyValue label="Collector">
            <Ident>{event.source}</Ident>
          </KeyValue>
          {event.provenance.query && (
            <KeyValue label="Query or scenario">
              <Ident>{event.provenance.query}</Ident>
            </KeyValue>
          )}
          {event.entity_key && (
            <KeyValue label="Entity">
              <Ident>{event.entity_key}</Ident>
            </KeyValue>
          )}
          <KeyValue label="Observed">
            <Ago at={event.observed_at} />
          </KeyValue>
        </dl>

        {scripted && (
          <p className="mt-5 border-t border-[rgb(var(--edge))] pt-4 text-xs text-[rgb(var(--warn))]">
            <span aria-hidden="true">◆ </span>
            This observation is part of a written scenario. It did not come off a
            real network, and nothing on this deployment did.
          </p>
        )}
      </Panel>

      <Panel title="Detail" aside="as recorded">
        <pre className="mono overflow-x-auto text-xs text-[rgb(var(--muted))]">
          {JSON.stringify(event.payload, null, 2)}
        </pre>
      </Panel>
    </Page>
  );
}
