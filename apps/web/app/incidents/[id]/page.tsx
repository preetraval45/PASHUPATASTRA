import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";

import { VerdictPanel } from "@/components/approval";
import { ChatPanel } from "@/components/chat";
import { IncidentView } from "@/components/incident";
import { Scenarios } from "@/components/scenarios";
import { Timeline } from "@/components/timeline";
import { Ago, Badge, Empty, Ident, Offline, Page, Panel, type Status } from "@/components/ui";
import {
  evaluatePolicy,
  getActions,
  getIncident,
  getIncidentAudit,
  getIncidents,
  type AuditRecord,
} from "@/lib/api";

export const dynamic = "force-dynamic";

/** The tab title carries the incident id, so a browser full of tabs during a
 *  multi-incident night is still navigable. */
export async function generateMetadata({
  params,
}: {
  params: Promise<{ id: string }>;
}): Promise<Metadata> {
  const id = decodeURIComponent((await params).id);
  const incident = await getIncident(id);
  // No suffix here — the root layout's title template appends the site name,
  // and adding it again produced "INC-2026-0901 · Pashupatastra · Pashupatastra".
  return {
    title: id,
    // The diagnosis, so a search result or a shared link says what happened
    // rather than repeating the site's own pitch.
    description: incident?.hypotheses[0]?.statement ?? `Incident ${id}.`,
  };
}

const KIND: Record<string, { label: string; status: Status }> = {
  observation: { label: "observed", status: "neutral" },
  hypothesis: { label: "reasoned", status: "neutral" },
  policy_evaluation: { label: "policy", status: "neutral" },
  approval: { label: "approved", status: "warning" },
  execution_attempt: { label: "executing", status: "warning" },
  execution_result: { label: "executed", status: "ok" },
  verification: { label: "verified", status: "ok" },
  escalation: { label: "escalated", status: "high" },
};

export default async function IncidentDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id: raw } = await params;
  const id = decodeURIComponent(raw);

  const [incident, actions, audit, all] = await Promise.all([
    getIncident(id),
    getActions(),
    getIncidentAudit(id),
    getIncidents(),
  ]);

  // `null` means the API could not be reached; a 404 is handled by the client
  // returning null too, so the pair is disambiguated by asking for the list.
  if (incident === null) {
    const stillUp = await getActions();
    if (stillUp === null) return <Offline />;
    notFound();
  }

  const risk = new Map((actions ?? []).map((a) => [a.id, a.base_risk]));

  // Authorization is shown for the plan's riskiest step, evaluated against this
  // incident's real blast radius and confidence. The dashboard asks the policy
  // engine rather than scoring anything itself.
  const riskiest = [...incident.plan].sort(
    (a, b) => (risk.get(b.action_id) ?? 0) - (risk.get(a.action_id) ?? 0),
  )[0];
  const spec = (actions ?? []).find((a) => a.id === riskiest?.action_id);
  const verdict = riskiest
    ? await evaluatePolicy({
        action_id: riskiest.action_id,
        incident_ref: incident.id,
        blast_radius_entities: incident.impact.blast_radius_entities,
        blast_radius_users: incident.impact.estimated_users_affected,
        diagnostic_confidence: incident.hypotheses[0]?.confidence ?? 1,
      })
    : null;

  return (
    <Page
      title={id}
      description="One incident, its evidence, and everything done about it."
      actions={
        <Link
          href="/incidents"
          className="focusable rounded border border-[rgb(var(--edge-strong))] px-3 py-1.5 text-sm hover:bg-[rgb(var(--raised))]"
        >
          ← All incidents
        </Link>
      }
    >
      <IncidentView incident={incident} risk={risk} />

      {/* Directly under the incident, above the loop. A visitor has just read
          what happened and the next thing they want is to ask about it; at the
          bottom of the page it would be found only by people who had already
          finished reading. */}
      <ChatPanel incident={incident} />

      <Panel
        title="The loop"
        aside="every stage, including the ones that did not run"
      >
        <Timeline incident={incident} audit={audit ?? []} />
      </Panel>

      {verdict && (
        <VerdictPanel
          verdict={verdict}
          blastRadius={incident.impact.blast_radius_entities}
          affectedUsers={incident.impact.estimated_users_affected}
          expectedPostState={riskiest?.expected_post_state}
          rollback={riskiest?.rollback_action_id ?? spec?.rollback_action_id ?? null}
        />
      )}

      <Panel title="Audit trail" aside={`${audit?.length ?? 0} records`}>
        {!audit?.length ? (
          <Empty art="ledger" title="No audit records for this incident yet.">
            Records appear as policy evaluates, actions execute, and verification runs.
          </Empty>
        ) : (
          <ol className="divide-y divide-[rgb(var(--edge))]">
            {audit.map((record, index) => (
              <AuditRow key={index} record={record} index={index} />
            ))}
          </ol>
        )}
      </Panel>

      {/* Switching without going back to the list. The alternative is a visitor
          reading one incident and leaving, which is what happened before this
          existed. */}
      <Scenarios incidents={all ?? []} currentId={incident.id} />
    </Page>
  );
}

function AuditRow({ record, index }: { record: AuditRecord; index: number }) {
  const kind = KIND[record.kind] ?? { label: record.kind, status: "neutral" as Status };
  const human = record.actor.startsWith("human:");
  return (
    // The anchor is what the timeline links to, so a stage can point at the
    // exact record it claims as evidence rather than at the trail in general.
    <li
      id={`audit-${index}`}
      className="relative flex scroll-mt-24 flex-wrap items-baseline gap-x-3 gap-y-1 py-3 target:bg-[rgb(var(--raised))] first:pt-0 last:pb-0"
    >
      {/* A second anchor, keyed by timestamp rather than position. The
          timeline points at rows by index; a chat citation cannot, because
          answering a question appends a record and shifts every index below
          it. Two ids for two questions, rather than one that is wrong for one
          of them. */}
      <span id={`audit:${record.at}`} aria-hidden="true" className="absolute -top-24" />
      <span className="w-16 shrink-0 text-xs text-[rgb(var(--faint))]">
        <Ago at={record.at} />
      </span>
      <Badge status={kind.status}>{kind.label}</Badge>
      <span
        className={`mono text-xs ${
          human ? "text-[rgb(var(--gold))]" : "text-[rgb(var(--astra))]"
        }`}
      >
        {record.actor}
      </span>
      <span className="min-w-0 flex-1 text-sm">{record.summary}</span>
    </li>
  );
}
