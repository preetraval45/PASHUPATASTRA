import Link from "next/link";

import { ChainReveal } from "@/components/chainreveal";

import {
  Ago,
  Badge,
  Evidence,
  Ident,
  KeyValue,
  Panel,
  statusForRisk,
  statusForSeverity,
  Technique,
} from "@/components/ui";
import type { Hypothesis, Incident } from "@/lib/api";

/**
 * The incident view, shared between the list and the detail route so the two
 * can never drift. A summary that renders differently from the page it links to
 * is how an operator ends up reading two versions of the same incident.
 */
export function IncidentView({
  incident,
  risk,
  linkToDetail = false,
}: {
  incident: Incident;
  risk: Map<string, number>;
  linkToDetail?: boolean;
}) {
  const [top, ...alternatives] = incident.hypotheses;

  return (
    <article className="space-y-6">
      <Panel>
        <div className="flex flex-wrap items-center gap-3">
          <h2 className="text-lg">
            {linkToDetail ? (
              <Link href={`/incidents/${incident.id}`} className="focusable rounded">
                <Ident>{incident.id}</Ident>
              </Link>
            ) : (
              <Ident>{incident.id}</Ident>
            )}
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
          <KeyValue label="Affected assets">
            {incident.impact.affected_services.join(", ") || "—"}
          </KeyValue>
          <KeyValue label="Accounts affected">
            <span className="tnum">
              {incident.impact.estimated_users_affected.toLocaleString()}
            </span>
          </KeyValue>
          <KeyValue label="Root cause probability">
            <span className="tnum">{Math.round((top?.confidence ?? 0) * 100)}%</span>
          </KeyValue>
        </dl>
      </Panel>

      {/* The chain as a chain.
          
          It was a numbered list, which is an accurate description of a sequence
          and not a picture of one. A rail with a node per step and the line
          continuing between them says "this led to that" before any word is
          read — which is the claim the panel is making.
          
          Still an <ol> of entity, transition, evidence and technique underneath
          the styling, so a screen reader gets the sequence and loses nothing. */}
      <Panel title="Causal chain">
        <ChainReveal incidentId={incident.id} />
        <ol data-chain className="relative space-y-0">
          {incident.causal_chain.map((link, index) => {
            const last = index === incident.causal_chain.length - 1;
            return (
              // The id is what a chat citation lands on. Without it a linked
              // ref could only reach the page, leaving the reader to find the
              // step themselves — which is most of the way back to an id you
              // cannot follow.
              <li
                key={`${link.entity.id}-${index}`}
                id={`chain-${index}`}
                // `--step` staggers the reveal in CSS rather than with a timer
                // per row. The index is already here; a JS timeline would be a
                // second source of truth for the order the list already has.
                style={{ "--step": index } as React.CSSProperties}
                className="relative flex scroll-mt-24 gap-4 pb-6 target:bg-[rgb(var(--raised))] last:pb-0"
              >
                {/* The rail. Drawn behind the node and stopped at the final
                    step, because a line continuing past the end would promise
                    another one. */}
                {!last && (
                  <span
                    aria-hidden="true"
                    data-rail
                    className="absolute left-[11px] top-7 h-[calc(100%-1.25rem)] w-px bg-gradient-to-b from-[rgb(var(--edge-strong))] to-[rgb(var(--edge))]"
                  />
                )}
                {/* `data-rail` and `data-node` rather than letting CSS find
                    these by position. The last step renders no rail, so on that
                    one row the marker *was* the first child — and the reveal
                    handed it the rail's `scaleY(0)`, which made the final
                    marker invisible for the length of its own delay. A
                    positional selector describes where an element sits; these
                    describe what it is, and only one of those survives a
                    conditional sibling. */}
                <span
                  aria-hidden="true"
                  data-node
                  className="relative z-10 mt-1 flex h-6 w-6 shrink-0 items-center justify-center rounded-full border border-[rgb(var(--edge-strong))] bg-[rgb(var(--raised))]"
                >
                  <span className="mono text-[10px] text-[rgb(var(--muted))]">{index + 1}</span>
                </span>

                <div className="min-w-0 flex-1">
                  <Link
                    href={`/entity/${link.entity.kind}:${link.entity.id}`}
                    className="focusable lift inline-flex max-w-full items-center gap-2 rounded-md border border-[rgb(var(--edge))] bg-[rgb(var(--raised))]/60 px-2.5 py-1 hover:border-[rgb(var(--astra))]/40"
                  >
                    <Ident>{link.entity.name}</Ident>
                  </Link>
                  <p className="mt-2 text-sm">{link.transition}</p>
                  {/* A chain without citations is a story, not a diagnosis. */}
                  <Evidence refs={link.evidence} incidentId={incident.id} />
                  <Technique technique={link.attack_technique} />
                </div>
              </li>
            );
          })}
        </ol>
      </Panel>

      {top && (
        <Panel title="Diagnosis" id="diagnosis">
          <p className="text-sm">{top.statement}</p>
          <Evidence refs={top.evidence} incidentId={incident.id} />

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
              <li
                key={step.order}
                id={`plan-${step.order}`}
                className="flex scroll-mt-24 flex-wrap items-baseline gap-x-4 gap-y-2 py-3 target:bg-[rgb(var(--raised))] first:pt-0 last:pb-0"
              >
                <span className="mono w-6 shrink-0 text-xs text-[rgb(var(--faint))]">
                  {String(step.order).padStart(2, "0")}
                </span>
                <Ident>{step.action_id}</Ident>
                {base !== undefined && <Badge status={statusForRisk(base)}>risk {base}</Badge>}
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
