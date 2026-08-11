import { getIncidents, type Hypothesis, type Incident } from "@/lib/api";

export const dynamic = "force-dynamic";

export default async function IncidentsPage() {
  const incidents = await getIncidents();

  if (!incidents?.length) {
    return (
      <div className="panel p-6 text-sm text-[rgb(var(--muted))]">
        No incidents. Start the API to see the seeded demo incident.
      </div>
    );
  }

  return (
    <div className="space-y-10">
      <h1 className="text-2xl font-semibold">Incidents</h1>
      {incidents.map((incident) => (
        <IncidentDetail key={incident.id} incident={incident} />
      ))}
    </div>
  );
}

function IncidentDetail({ incident }: { incident: Incident }) {
  const top = incident.hypotheses[0];
  const alternatives = incident.hypotheses.slice(1);

  return (
    <article className="space-y-6">
      <header className="panel p-5">
        <div className="flex flex-wrap items-center gap-3">
          <h2 className="mono text-lg">{incident.id}</h2>
          <span className="rounded border border-rose-500/30 bg-rose-500/10 px-2 py-0.5 text-[11px] uppercase tracking-wide text-rose-300">
            {incident.severity}
          </span>
          <span className="text-[11px] uppercase tracking-wide text-[rgb(var(--muted))]">
            {incident.state.replace(/_/g, " ")}
          </span>
        </div>
        <dl className="mt-4 grid gap-4 sm:grid-cols-3">
          <Field label="Affected services" value={incident.impact.affected_services.join(", ")} />
          <Field
            label="Estimated users affected"
            value={incident.impact.estimated_users_affected.toLocaleString()}
          />
          <Field
            label="Root cause probability"
            value={`${Math.round((top?.confidence ?? 0) * 100)}%`}
          />
        </dl>
      </header>

      <section className="panel p-5">
        <h3 className="label">Causal chain</h3>
        <ol className="mt-4 space-y-3">
          {incident.causal_chain.map((link, index) => (
            <li key={`${link.entity.id}-${index}`} className="flex gap-3">
              <span className="mono mt-0.5 text-xs text-[rgb(var(--muted))]">
                {String(index + 1).padStart(2, "0")}
              </span>
              <div>
                <div className="mono text-sm text-[rgb(var(--astra))]">{link.entity.name}</div>
                <div className="text-sm">{link.transition}</div>
                {/* Every link cites its evidence — a chain without citations is a
                    story, not a diagnosis. */}
                <div className="mono mt-1 text-[11px] text-[rgb(var(--muted))]">
                  evidence: {link.evidence.join(", ")}
                </div>
              </div>
            </li>
          ))}
        </ol>
      </section>

      {top && (
        <section className="panel p-5">
          <h3 className="label">Diagnosis</h3>
          <p className="mt-3 text-sm">{top.statement}</p>
          <div className="mono mt-2 text-[11px] text-[rgb(var(--muted))]">
            evidence: {top.evidence.join(", ")}
          </div>
          {alternatives.length > 0 && (
            <div className="mt-5 border-t border-[rgb(var(--edge))] pt-4">
              <h4 className="label">Alternatives considered</h4>
              <ul className="mt-3 space-y-3">
                {alternatives.map((h) => (
                  <AlternativeHypothesis key={h.statement} hypothesis={h} />
                ))}
              </ul>
            </div>
          )}
        </section>
      )}

      <section className="panel p-5">
        <h3 className="label">Remediation plan</h3>
        <ol className="mt-4 space-y-3">
          {incident.plan.map((step) => (
            <li
              key={step.order}
              className="flex flex-wrap items-baseline gap-3 border-b border-[rgb(var(--edge))] pb-3 last:border-0 last:pb-0"
            >
              <span className="mono text-xs text-[rgb(var(--muted))]">
                {String(step.order).padStart(2, "0")}
              </span>
              <span className="mono text-sm">{step.action_id}</span>
              <span className="text-xs text-[rgb(var(--muted))]">
                expects{" "}
                {Object.entries(step.expected_post_state)
                  .map(([k, v]) => `${k} ${v}`)
                  .join(", ") || "no state change"}
              </span>
              <span className="text-xs text-[rgb(var(--muted))]">
                rollback: <span className="mono">{step.rollback_action_id ?? "none"}</span>
              </span>
            </li>
          ))}
        </ol>
        <p className="mt-4 text-xs text-[rgb(var(--muted))]">
          Execution requires a policy verdict. Approval is issued through the API, and the
          dashboard never computes risk or tier itself.
        </p>
      </section>

      <section className="panel p-5">
        <h3 className="label">Audit timeline</h3>
        <ol className="mt-4 space-y-2 text-sm">
          {incident.transitions.map((t, index) => (
            <li key={index} className="flex flex-wrap gap-3">
              <span className="mono text-xs text-[rgb(var(--muted))]">
                {new Date(t.at).toLocaleTimeString()}
              </span>
              <span className="mono text-xs text-[rgb(var(--astra))]">{t.actor}</span>
              <span>{t.to_state.replace(/_/g, " ")}</span>
              <span className="text-xs text-[rgb(var(--muted))]">{t.justification}</span>
            </li>
          ))}
        </ol>
      </section>
    </article>
  );
}

function AlternativeHypothesis({ hypothesis }: { hypothesis: Hypothesis }) {
  return (
    <li className="text-sm text-[rgb(var(--muted))]">
      <span>{hypothesis.statement}</span>
      <span className="mono ml-2 text-[11px]">
        {Math.round(hypothesis.confidence * 100)}%
      </span>
      {hypothesis.contradicted_by.length > 0 && (
        <div className="mono mt-1 text-[11px] text-rose-400/80">
          contradicted by: {hypothesis.contradicted_by.join(", ")}
        </div>
      )}
    </li>
  );
}

function Field({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="label">{label}</dt>
      <dd className="mt-1 text-sm">{value || "—"}</dd>
    </div>
  );
}
