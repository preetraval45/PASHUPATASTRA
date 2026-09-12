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

export type StageKey =
  | "detection"
  | "hypothesis"
  | "plan"
  | "approval"
  | "execution"
  | "verification";

/** Reached and held / reached and failed / not yet / never happened at all. */
type StageState = "done" | "failed" | "active" | "pending" | "skipped";

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

/** How far the loop got. Terminal states are handled separately — they say the
 *  loop stopped, not how far along it stopped. */
const REACHED: Record<IncidentState, number> = {
  detected: 0,
  correlated: 0,
  diagnosed: 1,
  planned: 2,
  awaiting_approval: 3,
  executing: 4,
  verifying: 5,
  resolved: 6,
  verification_failed: 6,
  rolled_back: 6,
  escalated: 6,
};

const TERMINAL = new Set<IncidentState>([
  "resolved",
  "verification_failed",
  "rolled_back",
  "escalated",
]);

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

function failed(records: AuditRecord[]): boolean {
  return records.some(
    (r) =>
      r.kind === "escalation" ||
      r.detail?.succeeded === false ||
      r.detail?.passed === false ||
      /\bfailed\b|\bdenied\b|rolled_back|rollback_failed/i.test(r.summary),
  );
}

/** The incident states that evidence each stage actually happened. */
const STAGE_STATES: Record<StageKey, IncidentState[]> = {
  detection: ["detected", "correlated"],
  hypothesis: ["diagnosed"],
  plan: ["planned"],
  approval: ["awaiting_approval"],
  execution: ["executing"],
  // Deliberately excludes `resolved`. Reaching resolved is the *claim* that the
  // fix worked, and verification is what justifies that claim — accepting it as
  // evidence that verification ran is circular, and it would hide the exact
  // anomaly this component exists to surface: a loop that closed an incident
  // without ever checking. `rolled_back` and `verification_failed` do count,
  // since both are consequences of verification having run and returned an
  // answer.
  verification: ["verifying", "verification_failed", "rolled_back"],
};

/**
 * A stage counts as having happened on any of three kinds of evidence: an audit
 * record, a state transition through it, or the artefact it produces.
 *
 * Audit records alone are not enough. The trail is a separate store and can be
 * empty for reasons that have nothing to do with the incident — it was durable
 * from R18, and before that it was per-process — while the incident's own
 * transition history still shows the stage ran. Judging on records alone marked Detection
 * "never ran" on an incident that had plainly been detected, which is worse than
 * useless here: a component whose job is flagging skipped stages loses all its
 * signal the moment it cries wolf.
 */
function evidenceFor(
  key: StageKey,
  records: AuditRecord[],
  incident: Incident,
): boolean {
  if (records.length > 0) return true;
  if (incident.transitions.some((t) => STAGE_STATES[key].includes(t.to_state))) return true;

  if (key === "plan") return incident.plan.length > 0;
  if (key === "hypothesis") return incident.hypotheses.length > 0;
  return false;
}

function stageState(
  key: StageKey,
  index: number,
  records: AuditRecord[],
  incident: Incident,
): StageState {
  const reached = REACHED[incident.state] ?? 0;
  const terminal = TERMINAL.has(incident.state);

  if (records.length > 0 && failed(records)) return "failed";

  // The stage the loop is sitting in now. Checked before the evidence test, or
  // an incident waiting on approval would report approval as already done.
  if (index === reached && !terminal) return "active";

  if (evidenceFor(key, records, incident)) return "done";

  // Past it, or the loop stopped, with nothing showing it ever ran.
  if (index < reached || terminal) return "skipped";
  return "pending";
}

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
                  {matched.map(({ record, index: row }) => (
                    <li key={row} className="text-xs">
                      <Link
                        href={`#audit-${row}`}
                        className="focusable text-[rgb(var(--astra))] hover:underline"
                      >
                        {record.summary}
                      </Link>
                      <span className="mono ml-2 text-[rgb(var(--faint))]">{record.actor}</span>
                    </li>
                  ))}
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
