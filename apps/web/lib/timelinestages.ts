/**
 * Which of the loop's six stages an incident reached, and how each one went: the
 * logic behind components/timeline.tsx, kept here so it can be tested without
 * rendering (node --test; RESEARCH PLAN 4.4).
 */
import type { AuditRecord, Incident, IncidentState } from "@/lib/api";

export type StageKey =
  | "detection"
  | "hypothesis"
  | "plan"
  | "approval"
  | "execution"
  | "verification";

/** Reached and held / reached and failed / not yet / never happened at all. */
export type StageState = "done" | "failed" | "active" | "pending" | "skipped";

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

export function failed(records: AuditRecord[]): boolean {
  return records.some(
    (r) =>
      r.kind === "escalation" ||
      r.detail?.succeeded === false ||
      r.detail?.passed === false ||
      /\bfailed\b|\bdenied\b|rolled_back|rollback_failed/i.test(r.summary),
  );
}

/** The incident states that evidence each stage actually happened. */
export const STAGE_STATES: Record<StageKey, IncidentState[]> = {
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
export function evidenceFor(
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

export function stageState(
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

