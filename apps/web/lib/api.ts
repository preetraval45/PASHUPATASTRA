/**
 * Client for the Pashupatastra API.
 *
 * The dashboard renders what the API reports and never derives risk, tier, or
 * verification outcome on its own — those are the policy engine's answers, and
 * a second implementation here would be a second source of truth (the Grounding ADR).
 */

export const API_BASE =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1";

export type Tier = "autonomous" | "approval" | "senior" | "denied";

export type IncidentState =
  | "detected"
  | "correlated"
  | "diagnosed"
  | "planned"
  | "awaiting_approval"
  | "executing"
  | "verifying"
  | "resolved"
  | "verification_failed"
  | "rolled_back"
  | "escalated";

export interface EntityRef {
  kind: string;
  id: string;
  name: string;
}

export interface Hypothesis {
  statement: string;
  confidence: number;
  evidence: string[];
  contradicted_by: string[];
  mechanism: string[];
}

/** A MITRE ATT&CK mapping. `url` is derived from `id` by the API's model, not
 *  stored, so nothing here recomputes it. */
export interface AttackTechnique {
  id: string;
  name: string;
  tactic: string;
}

export interface CausalLink {
  entity: EntityRef;
  transition: string;
  evidence: string[];
  /** Absent where a step is not adversary behaviour — an infrastructure
   *  incident has no ATT&CK mapping and must not be given an invented one. */
  attack_technique: AttackTechnique | null;
}

export interface PlanStep {
  order: number;
  action_id: string;
  expected_post_state: Record<string, string>;
  rollback_action_id: string | null;
}

export interface Incident {
  id: string;
  state: IncidentState;
  severity: "critical" | "high" | "medium" | "low";
  opened_at: string;
  affected_entities: EntityRef[];
  impact: {
    estimated_users_affected: number;
    affected_services: string[];
    blast_radius_entities: number;
  };
  hypotheses: Hypothesis[];
  causal_chain: CausalLink[];
  plan: PlanStep[];
  transitions: {
    at: string;
    from_state: IncidentState | null;
    to_state: IncidentState;
    actor: string;
    justification: string;
  }[];
}

export interface ActionSpec {
  id: string;
  description: string;
  base_risk: number;
  expected_post_state: Record<string, string>;
  rollback_action_id: string | null;
  irreversible: boolean;
}

export interface Verdict {
  action_id: string;
  incident_ref: string | null;
  base_risk: number;
  adjustments: RiskAdjustment[];
  effective_risk: number;
  tier: Tier;
  required_approvers: string[];
  granted_by: string | null;
  expires_at: string | null;
  denial_reason: string | null;
}

export interface GraphNode {
  key: string;
  kind: string;
  name: string;
  namespace: string | null;
  estimated_users: number;
  /** Worst severity in the last 15 minutes, not the latest — a service that
   *  went critical then reported info seconds later is flapping, not healthy. */
  severity: "critical" | "warning" | "info" | null;
  last_seen: string | null;
}

export interface GraphEdge {
  source: string;
  target: string;
  kind: string;
}

export interface TopologySnapshot {
  nodes: GraphNode[];
  edges: GraphEdge[];
}

export interface AuditRecord {
  at: string;
  kind: string;
  actor: string;
  incident_ref: string | null;
  summary: string;
  detail: Record<string, unknown>;
}

export interface EntityEvent {
  id: string;
  event_class: string;
  source: string;
  occurred_at: string;
  observed_at: string;
  severity: "critical" | "warning" | "info" | null;
  payload: Record<string, unknown>;
  provenance: { source_system: string; query?: string | null; url?: string | null };
  labels: Record<string, string>;
}

export interface EntityDetail {
  entity: {
    key: string;
    kind: string;
    name: string;
    namespace: string | null;
    cluster: string | null;
    owner: string | null;
    estimated_users: number;
    first_seen: string;
    last_seen: string;
  };
  blast_radius: { affected: string[]; entity_count: number; estimated_users: number };
  events: EntityEvent[];
}

export interface RiskAdjustment {
  reason: string;
  delta: number;
}

export interface Health {
  status: string;
  audit_storage: string;
  environment: string;
  dry_run: boolean;
  incidents: number;
  audit_records: number;
}

async function post<T>(path: string, body: unknown): Promise<T | null> {
  try {
    const response = await fetch(`${API_BASE}${path}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
      cache: "no-store",
    });
    if (!response.ok) return null;
    return (await response.json()) as T;
  } catch {
    return null;
  }
}

async function get<T>(path: string): Promise<T | null> {
  try {
    const response = await fetch(`${API_BASE}${path}`, { cache: "no-store" });
    if (!response.ok) return null;
    return (await response.json()) as T;
  } catch {
    // The dashboard degrades to an offline state rather than erroring — an
    // operator who cannot reach the API still needs the page to tell them so.
    return null;
  }
}

export const getHealth = () => get<Health>("/health");
export const getIncidents = () => get<Incident[]>("/incidents");
export const getActions = () => get<ActionSpec[]>("/actions");
export const getTopology = () => get<TopologySnapshot>("/topology/graph");
export const getTopologyCounts = () => get<{ nodes: number; edges: number }>("/topology");
export const getAudit = (limit = 50) => get<AuditRecord[]>(`/audit?limit=${limit}`);
export const getIncident = (id: string) => get<Incident>(`/incidents/${encodeURIComponent(id)}`);
export const getIncidentAudit = (id: string) =>
  get<AuditRecord[]>(`/audit?incident_ref=${encodeURIComponent(id)}&limit=100`);
/** Evaluate policy for an action. This is the only way to obtain authorization,
 *  and the dashboard never computes risk itself — a second implementation would
 *  be a second, contradictory answer. */
export async function evaluatePolicy(body: {
  action_id: string;
  incident_ref?: string | null;
  blast_radius_entities?: number;
  blast_radius_users?: number;
  diagnostic_confidence?: number;
}): Promise<Verdict | null> {
  return post<Verdict>("/policy/evaluate", body);
}

export const getEntity = (key: string) =>
  get<EntityDetail>(`/entities/${encodeURIComponent(key)}`);

/** One event by id. This is what makes an evidence citation checkable rather
 *  than decorative — without it the id is a string a reader takes on trust. */
export const getEvent = (id: string) =>
  get<EntityEvent & { entity_key: string }>(`/events/${encodeURIComponent(id)}`);

/** Whether the API is reachable at all.
 *
 *  `get` returns null for a 404 and for an unreachable API alike, so a detail
 *  page cannot tell "this does not exist" from "nothing is answering" — and it
 *  told visitors the whole system was down when they clicked a link to an
 *  entity that simply was not in the graph. Asking a second, cheap question
 *  separates them. */
export async function apiIsReachable(): Promise<boolean> {
  return (await getHealth()) !== null;
}

/** Namespaces belonging to the platform rather than the customer's workload. */
const SYSTEM_NAMESPACES = new Set([
  "kube-system",
  "kube-public",
  "kube-node-lease",
  "local-path-storage",
]);

export function isInfrastructure(node: GraphNode): boolean {
  return node.namespace !== null && SYSTEM_NAMESPACES.has(node.namespace);
}

export function tierLabel(tier: Tier): string {
  return {
    autonomous: "Autonomous",
    approval: "Approval required",
    senior: "Senior approval",
    denied: "Never autonomous",
  }[tier];
}

export function riskBand(risk: number): {
  label: string;
  className: string;
} {
  if (risk <= 30)
    return { label: "low", className: "text-emerald-400 border-emerald-500/30 bg-emerald-500/10" };
  if (risk <= 60)
    return { label: "medium", className: "text-amber-400 border-amber-500/30 bg-amber-500/10" };
  if (risk <= 80)
    return { label: "high", className: "text-orange-400 border-orange-500/30 bg-orange-500/10" };
  return { label: "prohibited", className: "text-rose-400 border-rose-500/30 bg-rose-500/10" };
}
