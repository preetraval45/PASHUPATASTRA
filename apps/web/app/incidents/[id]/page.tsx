import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";

import { VerdictPanel } from "@/components/approval";
import { IncidentView } from "@/components/incident";
import { Ago, Badge, Empty, Ident, Offline, Page, Panel, type Status } from "@/components/ui";
import {
  evaluatePolicy,
  getActions,
  getIncident,
  getIncidentAudit,
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
  const { id } = await params;
  return { title: `${decodeURIComponent(id)} · Pashupatastra` };
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

  const [incident, actions, audit] = await Promise.all([
    getIncident(id),
    getActions(),
    getIncidentAudit(id),
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
          <Empty title="No audit records for this incident yet.">
            Records appear as policy evaluates, actions execute, and verification runs.
          </Empty>
        ) : (
          <ol className="divide-y divide-[rgb(var(--edge))]">
            {audit.map((record, index) => (
              <AuditRow key={index} record={record} />
            ))}
          </ol>
        )}
      </Panel>
    </Page>
  );
}

function AuditRow({ record }: { record: AuditRecord }) {
  const kind = KIND[record.kind] ?? { label: record.kind, status: "neutral" as Status };
  const human = record.actor.startsWith("human:");
  return (
    <li className="flex flex-wrap items-baseline gap-x-3 gap-y-1 py-3 first:pt-0 last:pb-0">
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
