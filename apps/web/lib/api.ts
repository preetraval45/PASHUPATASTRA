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

export interface CausalLink {
  entity: EntityRef;
  transition: string;
  evidence: string[];
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
  adjustments: { reason: string; delta: number }[];
  effective_risk: number;
  tier: Tier;
  required_approvers: string[];
  granted_by: string | null;
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

export interface Health {
  status: string;
  audit_storage: string;
  environment: string;
  dry_run: boolean;
  incidents: number;
  audit_records: number;
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
