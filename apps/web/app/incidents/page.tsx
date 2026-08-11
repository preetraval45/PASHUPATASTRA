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
  statusForRisk,
  statusForSeverity,
} from "@/components/ui";
import { getActions, getIncidents, type Hypothesis, type Incident } from "@/lib/api";

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
          graph and in time — two unrelated services degrading in the same minute stay two
          incidents.
        </Empty>
      ) : (
        incidents.map((incident) => (
          <IncidentDetail key={incident.id} incident={incident} risk={risk} />
        ))
      )}
    </Page>
  );
}

function IncidentDetail({
  incident,
  risk,
}: {
  incident: Incident;
  risk: Map<string, number>;
}) {
  const [top, ...alternatives] = incident.hypotheses;

  return (
    <article className="space-y-6">
      <Panel>
        <div className="flex flex-wrap items-center gap-3">
          <h2 className="text-lg">
            <Ident>{incident.id}</Ident>
          </h2>
          <Badge status={statusForSeverity(incident.severity)}>{incident.severity}</Badge>
          <span className="text-[11px] uppercase tracking-wide text-[rgb(var(--muted))]">
            {incident.state.replace(/_/g, " ")}
          </span>
          <span className="ml-auto text-xs text-[rgb(var(--faint))]">
            opened <Ago at={incident.opened_at} />
          </span>
        </div>

        <dl className="mt-5 grid gap-5 sm:grid-cols-3">
          <KeyValue label="Affected services">
            {incident.impact.affected_services.join(", ") || "—"}
          </KeyValue>
          <KeyValue label="Estimated users affected">
            <span className="tnum">
              {incident.impact.estimated_users_affected.toLocaleString()}
            </span>
          </KeyValue>
          <KeyValue label="Root cause probability">
            <span className="tnum">{Math.round((top?.confidence ?? 0) * 100)}%</span>
          </KeyValue>
        </dl>
      </Panel>

      <Panel title="Causal chain">
        <ol className="space-y-4">
          {incident.causal_chain.map((link, index) => (
            <li key={`${link.entity.id}-${index}`} className="flex gap-4">
              <span className="mono mt-0.5 w-6 shrink-0 text-xs text-[rgb(var(--faint))]">
                {String(index + 1).padStart(2, "0")}
              </span>
              <div className="min-w-0">
                <Ident>{link.entity.name}</Ident>
                <p className="text-sm">{link.transition}</p>
                {/* A chain without citations is a story, not a diagnosis. */}
                <Evidence refs={link.evidence} />
              </div>
            </li>
          ))}
        </ol>
      </Panel>

      {top && (
        <Panel title="Diagnosis">
          <p className="text-sm">{top.statement}</p>
          <Evidence refs={top.evidence} />

          {alternatives.length > 0 && (
            <div className="mt-5 border-t border-[rgb(var(--edge))] pt-4">
              <h3 className="label">Also considered</h3>
              <ul className="mt-3 space-y-3">
                {alternatives.map((hypothesis) => (
                  <Alternative key={hypothesis.statement} hypothesis={hypothesis} />
                ))}
              </ul>
              <p className="mt-3 text-xs text-[rgb(var(--faint))]">
                Shown because a system that hides its own doubt is harder to trust than one
                that reports it.
              </p>
            </div>
          )}
        </Panel>
      )}

      <Panel title="Remediation plan" aside="execution requires a policy verdict">
        <ol className="divide-y divide-[rgb(var(--edge))]">
          {incident.plan.map((step) => {
            const base = risk.get(step.action_id);
            return (
              <li key={step.order} className="flex flex-wrap items-baseline gap-x-4 gap-y-2 py-3 first:pt-0 last:pb-0">
                <span className="mono w-6 shrink-0 text-xs text-[rgb(var(--faint))]">
                  {String(step.order).padStart(2, "0")}
                </span>
                <Ident>{step.action_id}</Ident>
                {base !== undefined && (
                  <Badge status={statusForRisk(base)}>risk {base}</Badge>
                )}
                <span className="text-xs text-[rgb(var(--muted))]">
                  expects{" "}
                  {Object.entries(step.expected_post_state)
                    .map(([k, v]) => `${k} ${v}`)
                    .join(", ") || "no state change"}
                </span>
                <span className="ml-auto text-xs text-[rgb(var(--faint))]">
                  rollback: <span className="mono">{step.rollback_action_id ?? "none"}</span>
                </span>
              </li>
            );
          })}
        </ol>
        <p className="mt-4 text-xs text-[rgb(var(--muted))]">
          Risk shown is the action&rsquo;s base score. Effective risk rises with blast radius,
          production environment, and low confidence — it never falls, and the dashboard
          never computes it here.
        </p>
      </Panel>

      <Panel title="Timeline">
        <ol className="space-y-2 text-sm">
          {incident.transitions.map((transition, index) => (
            <li key={index} className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
              <span className="w-16 shrink-0 text-xs text-[rgb(var(--faint))]">
                <Ago at={transition.at} />
              </span>
              <span
                className={`mono text-xs ${
                  transition.actor.startsWith("human:")
                    ? "text-[rgb(var(--gold))]"
                    : "text-[rgb(var(--astra))]"
                }`}
              >
                {transition.actor}
              </span>
              <span>{transition.to_state.replace(/_/g, " ")}</span>
              <span className="text-xs text-[rgb(var(--muted))]">
                {transition.justification}
              </span>
            </li>
          ))}
        </ol>
      </Panel>
    </article>
  );
}

function Alternative({ hypothesis }: { hypothesis: Hypothesis }) {
  return (
    <li className="text-sm text-[rgb(var(--muted))]">
      <span>{hypothesis.statement}</span>
      <span className="tnum ml-2 text-[11px]">
        {Math.round(hypothesis.confidence * 100)}%
      </span>
      {hypothesis.contradicted_by.length > 0 && (
        <p className="mono mt-1 text-[11px] text-[rgb(var(--crit))]/80">
          contradicted by: {hypothesis.contradicted_by.join(", ")}
        </p>
      )}
    </li>
  );
}
