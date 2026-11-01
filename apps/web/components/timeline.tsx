/**
 * The loop, as a timeline: detection → hypothesis → plan → approval →
 * execution → verification.
 *
 * Built from the six stages rather than from the audit records, which is the
 * whole point. A timeline assembled out of records shows what happened and
 * silently omits what did not, so an incident that closed without ever
 * verifying renders identically to one that verified cleanly — the reader has
 * to notice an absence, and absences are exactly what nobody notices at 3am.
 * Here every stage is always drawn, and a stage the loop passed over says so.
 */

import Link from "next/link";

import { Ago, Badge, Evidence, Stated, type Status } from "@/components/ui";
import type { AuditRecord, Incident, IncidentState } from "@/lib/api";
import { foldAudit } from "@/lib/fold";
import { stageState, type StageKey, type StageState } from "@/lib/timelinestages";

export type { StageKey };

const AUDIT_KINDS: Record<StageKey, string[]> = {
  detection: ["observation"],
  hypothesis: ["hypothesis"],
  plan: [],
  approval: ["policy_evaluation", "approval"],
  execution: ["execution_attempt", "execution_result"],
  verification: ["verification"],
};

const STAGES: { key: StageKey; label: string; blurb: string }[] = [
  { key: "detection", label: "Detection", blurb: "Telemetry crossed a baseline" },
  { key: "hypothesis", label: "Hypothesis", blurb: "Explanations, each citing evidence" },
  { key: "plan", label: "Plan", blurb: "Actions, each with a rollback and a post-state" },
  { key: "approval", label: "Approval", blurb: "Dharma scored it; a human may have to agree" },
  { key: "execution", label: "Execution", blurb: "The only path to a write" },
  { key: "verification", label: "Verification", blurb: "Observed state against expected state" },
];

const STATE_STATUS: Record<StageState, Status> = {
  done: "ok",
  failed: "critical",
  active: "warning",
  pending: "neutral",
  skipped: "high",
};

const STATE_LABEL: Record<StageState, string> = {
  done: "done",
  failed: "failed",
  active: "in progress",
  pending: "not yet",
  skipped: "never ran",
};

export function Timeline({
  incident,
  audit,
}: {
  incident: Incident;
  audit: AuditRecord[];
}) {
  // Indices into the rendered audit list, so a stage can link to the exact rows
  // it is claiming as its evidence rather than to the trail in general.
  const rows = audit.map((record, index) => ({ record, index }));

  return (
    <ol className="relative space-y-0">
      {STAGES.map((stage, index) => {
        const matched = rows.filter(({ record }) =>
          AUDIT_KINDS[stage.key].includes(record.kind),
        );
        const state = stageState(stage.key, index, matched.map((m) => m.record), incident);
        const last = index === STAGES.length - 1;

        return (
          <li key={stage.key} className="relative flex gap-4 pb-6 last:pb-0">
            {/* The rail is decorative; the state is carried by the badge. */}
            {!last && (
              <span
                aria-hidden="true"
                className="absolute left-[7px] top-5 h-full w-px bg-[rgb(var(--edge))]"
              />
            )}
            <span
              aria-hidden="true"
              className={`relative z-10 mt-1.5 h-[15px] w-[15px] shrink-0 rounded-full border-2 ${
                state === "pending"
                  ? "border-[rgb(var(--edge-strong))] bg-[rgb(var(--panel))]"
                  : `${STATUS_RING[state]} bg-[rgb(var(--panel))]`
              }`}
            />

            <div className="min-w-0 flex-1">
              <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
                <h3 className="text-sm font-medium">{stage.label}</h3>
                <Badge status={STATE_STATUS[state]}>{STATE_LABEL[state]}</Badge>
                {matched.length > 0 && (
                  <span className="text-xs text-[rgb(var(--faint))]">
                    <Ago at={matched[0].record.at} />
                  </span>
                )}
              </div>

              <p className="mt-0.5 text-xs text-[rgb(var(--faint))]">{stage.blurb}</p>

              {state === "skipped" && (
                <p className="mt-1.5 text-xs text-[rgb(var(--high))]">
                  No record of this stage. The loop reached {incident.state.replace(/_/g, " ")}{" "}
                  without it.
                </p>
              )}

              <StageDetail stageKey={stage.key} incident={incident} />

              {matched.length > 0 && (
                <ul className="mt-2 space-y-1">
                  {/* Folded: a run of identical lines is one line with `×N`
                      (R98). The link lands on the audit panel's row for the
                      run, which lists every member. */}
                  {foldAudit(matched.map((m) => m.record)).map((fold) => {
                    const row = matched[fold.index].index;
                    return (
                      <li key={row} className="text-xs">
                        <Link
                          href={`#audit-${row}`}
                          className="focusable text-[rgb(var(--astra))] hover:underline"
                        >
                          {fold.record.summary}
                        </Link>
                        {fold.count > 1 && (
                          <span
                            className="tnum ml-1.5 text-[rgb(var(--faint))]"
                            title={`${fold.count} identical records, folded`}
                          >
                            ×{fold.count}
                          </span>
                        )}
                        <span className="mono ml-2 text-[rgb(var(--faint))]">
                          {fold.record.actor}
                        </span>
                      </li>
                    );
                  })}
                </ul>
              )}
            </div>
          </li>
        );
      })}
    </ol>
  );
}

const STATUS_RING: Record<StageState, string> = {
  done: "border-[rgb(var(--ok))]",
  failed: "border-[rgb(var(--crit))]",
  active: "border-[rgb(var(--warn))]",
  pending: "border-[rgb(var(--edge-strong))]",
  skipped: "border-[rgb(var(--high))]",
};

/** The content a stage is actually about, so the timeline is readable without
 *  scrolling to the panel that repeats it. */
function StageDetail({ stageKey, incident }: { stageKey: StageKey; incident: Incident }) {
  if (stageKey === "hypothesis" && incident.hypotheses.length > 0) {
    const top = incident.hypotheses[0];
    return (
      <div className="mt-1.5 text-xs">
        <span>{top.statement}</span>
        <Stated value={top.confidence} className="ml-2 text-[rgb(var(--faint))]" />
        <Evidence refs={top.evidence} />
      </div>
    );
  }

  if (stageKey === "plan" && incident.plan.length > 0) {
    return (
      <ol className="mt-1.5 space-y-0.5 text-xs">
        {incident.plan.map((step) => (
          <li key={step.order}>
            <span className="mono">{step.action_id}</span>
            <span className="ml-2 text-[rgb(var(--faint))]">
              {step.rollback_action_id
                ? `undo: ${step.rollback_action_id}`
                : "no rollback declared"}
            </span>
          </li>
        ))}
      </ol>
    );
  }

  return null;
}
