import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";

import { VerdictPanel } from "@/components/approval";
import { AgentTurn } from "@/components/agentturn";
import { ChatPanel } from "@/components/chat";
import { BlastPanel } from "@/components/blastpanel";
import { IncidentGraph } from "@/components/incidentgraph";
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
  // Its own kind because it is its own thing: not something the platform saw,
  // but something it said.
  agent_turn: { label: "answered", status: "neutral" },
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
      {/* First on the page, not after the incident.
          "Under the incident" sounded right and put it 1,500px down a
          10,000px page, below the causal chain, the diagnosis and the plan —
          reachable only by someone who had already read everything and then
          kept scrolling. Nobody found it.

          Collapsed it is a single bar, so it costs the incident almost no
          vertical space, and it is the first thing offered to a reader who
          arrives not knowing what any of this means. */}
      <ChatPanel incident={incident} />

      <IncidentView incident={incident} risk={risk} />

      {/* Directly after the incident's own account of itself, before the loop.
          The map answers the question the chain raises — "and what else could
          it have touched?" — so it belongs where that question occurs, not on a
          separate page a reader has to think to visit. */}
      <IncidentGraph incident={incident} />

      <BlastPanel incident={incident} />

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

      {/* The way out to the whole trail. R52 delisted Audit as a front door on
          the grounds that it is reached from the incident whose actions it
          records — and that was not true until this link existed: the panel
          showed this incident's records and offered no route to the rest.
          `verifyreach.py` found it by clicking, which is the only way it could
          have been found. */}
      <Panel
        title="Audit trail"
        aside={
          <span className="flex flex-wrap items-center gap-3">
            <span>{audit?.length ?? 0} records</span>
            <Link
              href="/audit"
              className="focusable rounded underline decoration-dotted underline-offset-2 hover:text-[rgb(var(--ink))]"
            >
              every record →
            </Link>
          </span>
        }
      >
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
    // `min-w-0` on the row. Every audit record carries an agent turn's details
    // — model ids, prompt digests, entity keys, whatever a visitor typed — and
    // none of those are lengths this layout gets to choose. Without it the row
    // sizes to its longest unbreakable run and takes the document with it: the
    // audit panel alone was 46px of horizontal scroll on every incident page at
    // 375px, and `flex-wrap` cannot help when one child already exceeds the line.
    <li
      id={`audit-${index}`}
      className="relative flex min-w-0 scroll-mt-24 flex-wrap items-baseline gap-x-3 gap-y-1 py-3 target:bg-[rgb(var(--raised))] first:pt-0 last:pb-0"
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
      {/* `basis-full` below `sm`: the summary and the agent turn under it are
          the only parts of this row whose width is decided by data, and on a
          phone there is no useful width left for them after a timestamp, a
          badge and an actor. Given their own line they have the full row and
          nothing has to overflow to fit. `break-words` because a model id or an
          entity key inside the turn is one unbreakable token. */}
      {/* A `div`, not a `span`. `AgentTurn` renders a `<details>`, which is
          flow content and is invalid inside a `span` — the parser relocates it
          during hydration and React reports #418. Seven of them were nested
          this way on every incident page.
          Nobody had seen it because `verifyui` did not check incident detail
          pages until R63 added one, which is the same reason the 46px overflow
          below it survived: the page rendering the most data was the page
          nothing swept. */}
      <div className="min-w-0 basis-full break-words text-sm sm:flex-1 sm:basis-0">
        {record.summary}
        <AgentTurn record={record} />
      </div>
    </li>
  );
}
