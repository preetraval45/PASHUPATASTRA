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
  /** Declared on the action, never inferred from its risk. `changes_nothing` is
   *  true of paging an analyst, which is not a read — see R19. */
  read_only: boolean;
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
  /** Worst severity in the last 15 minutes, not the latest — an entity that
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
  /** Which model is wired up and what it has spent. `configured: false` means
   *  the deterministic stub is answering — the correct default for a fresh
   *  checkout, and something a reader should be told rather than have to infer
   *  from suspiciously tidy reasoning. The API has always returned this; the
   *  type simply never described it. */
  model: {
    provider: string;
    model: string;
    configured: boolean;
    calls: number;
    total_tokens: number;
  };
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

/** One answer from Sati, plus everything needed to judge how far to trust it. */
export type ChatAnswer = {
  answer: string;
  evidence_refs: string[];
  dropped_refs: string[];
  answerable: boolean;
  grounded: boolean;
  proposed_action_id: string | null;
  verdict: Verdict | null;
  approval_id: string | null;
  trace: { hop: number; kind: string; name?: string }[];
  tokens: number;
  model: string;
  provider: string;
  truncated: boolean;
  cached: boolean;
};

/**
 * Ask Sati about one incident.
 *
 * Unlike every other call here, this one reports *why* it failed. The shared
 * helpers collapse any non-2xx to `null`, which is right for a panel that can
 * fall back to "unavailable" — but a visitor who hit the per-minute allowance
 * needs to be told to wait rather than shown a dead assistant, and those two
 * are the same `null`.
 */
export async function askAgent(
  incidentId: string,
  message: string,
): Promise<{ answer: ChatAnswer } | { error: string; retryable: boolean }> {
  try {
    const response = await fetch(`${API_BASE}/agent/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ incident_id: incidentId, message }),
      cache: "no-store",
    });
    if (response.ok) return { answer: (await response.json()) as ChatAnswer };

    const detail = await response
      .json()
      .then((body: { detail?: string }) => body.detail)
      .catch(() => null);
    return {
      error: detail ?? "The assistant is unavailable right now.",
      retryable: response.status === 429 || response.status >= 500,
    };
  } catch {
    return { error: "Could not reach the API.", retryable: true };
  }
}

/**
 * How much weight an intelligence entry has earned.
 *
 * A closed union, mirroring `app/feeds/Verification`. R25 asks for the badge
 * vocabulary to be enforced by a type rather than by convention, and this is
 * where that is cashed: `VERIFICATION` below is a `Record` over exactly these
 * three, so adding a fourth to the API without deciding how it should look is a
 * compile error rather than an entry that renders with no badge at all.
 */
export type Verification = "reported" | "corroborated" | "confirmed";

export const VERIFICATIONS: readonly Verification[] = [
  "reported",
  "corroborated",
  "confirmed",
] as const;

export function isVerification(value: unknown): value is Verification {
  return typeof value === "string" && (VERIFICATIONS as readonly string[]).includes(value);
}

/** One stored intelligence entry. The shape `/intel` returns, which is the
 *  event shape every other read returns — feeds are telemetry, not a
 *  parallel kind of record with its own schema. */
export interface IntelEntry {
  id: string;
  source: string;
  entity_key: string;
  occurred_at: string;
  observed_at: string;
  severity: string | null;
  payload: { detection_type?: string; confidence?: number; asset?: string | null };
  provenance: { source_system: string; url: string | null; offset?: string | null };
  labels: Record<string, string>;
}

/** One report of an indicator. Several of these make a group. */
export interface IntelReport {
  id: string;
  at: string;
  status: string | null;
  tags: string | null;
  summary: string;
  url: string | null;
}

/** One indicator, with every report of it. Grouped server-side: the page should
 *  not receive two hundred rows to render a hundred and eight. */
export interface IntelGroup {
  entity_key: string;
  source: string;
  severity: string | null;
  verification: string | null;
  title: string;
  summary: string;
  provenance: { source_system?: string; url?: string | null };
  labels: Record<string, string>;
  reports: number;
  reports_in_window: number;
  window_hours: number;
  first_at: string;
  last_at: string;
  /** `null` when the publisher does not report liveness at all — a ransomware
   *  claim is neither still up nor gone. Only `false` means gone offline. */
  active: boolean | null;
  history: IntelReport[];
}

export const getIntel = (limit = 200, source?: string) =>
  get<{
    sources: string[];
    count: number;
    reports: number;
    window_hours: number;
    groups: IntelGroup[];
  }>(`/intel?limit=${limit}${source ? `&source=${encodeURIComponent(source)}` : ""}`);

/** Per-feed cursors. A feed that has quietly stopped looks exactly like a quiet
 *  feed, and this is the difference. */
export const getIntelStatus = () =>
  get<{ feeds: Record<string, string | null>; durable: boolean }>("/intel/status");

/* ------------------------------------------------------------- blue team */

export interface Briefing {
  incident_id: string;
  opened_at: string;
  alert: {
    id: string;
    at: string;
    entity_key: string;
    severity: string | null;
    detection: string;
    summary: string;
  } | null;
  entities: string[];
  candidates: { id: string; statement: string }[];
  actions: { id: string; description: string; base_risk: number; read_only: boolean }[];
  scoring: { diagnosis: number; response: number; investigation: number };
}

export interface Investigation {
  ok: boolean;
  entity: Record<string, unknown> | null;
  events: {
    id: string;
    at: string;
    severity: string | null;
    detection: string | null;
    summary: string;
  }[];
}

export interface Verdict2 {
  total: number;
  grade: "clean" | "sound" | "shaky" | "missed";
  breakdown: { name: string; points: number; of: number; note: string }[];
  chose: string | null;
  /** Filled in when an attempt carried a player token. The score is computed
   *  server-side from the choices — the client sends no number. */
  progress?: PlayerProgress;
  answer: {
    diagnosis: string | null;
    confidence: number | null;
    chain: {
      entity_key: string;
      transition: string;
      technique: { id: string; name: string; tactic: string; url: string } | null;
      evidence: string[];
    }[];
    plan: { order: number; action_id: string }[];
    decoy: {
      statement: string;
      ruled_out_by: { id: string; summary: string; entity_key: string }[];
    } | null;
  };
}

export const getScenarios = () =>
  get<
    {
      incident_id: string;
      severity: string;
      opened_at: string;
      opening: string;
      steps: number;
    }[]
  >("/game/scenarios");

export const getBriefing = (id: string) =>
  get<Briefing>(`/game/${encodeURIComponent(id)}/briefing`);

export const investigateEntity = (id: string, entity_key: string) =>
  post<Investigation>(`/game/${encodeURIComponent(id)}/investigate`, { entity_key });

/** Submit an attempt. This is the only call that returns the answer, and it
 *  returns it *after* an attempt — which is what keeps the briefing honest. */
export const submitAttempt = (
  id: string,
  body: {
    diagnosis_id: string;
    action_id: string;
    investigated: string[];
    player_id?: string | null;
  },
) => post<Verdict2>(`/game/${encodeURIComponent(id)}/answer`, body);

export interface PlayerProgress {
  attempts: number;
  streak: number;
  best_streak: number;
  cleared: string[];
  best: Record<string, number>;
}

export const getProgress = (playerId: string) =>
  get<{ player: PlayerProgress; durable: boolean }>(
    `/game/progress/${encodeURIComponent(playerId)}`,
  );

/** The sub-graph one incident's own evidence names, plus what those entities
 *  can reach beyond it. Filtered server-side — the incident page is the screen
 *  that has to load while somebody is waiting. */
export const getIncidentGraph = (id: string) =>
  get<{
    incident_id: string;
    nodes: GraphNode[];
    edges: GraphEdge[];
    beyond: string[];
  }>(`/incidents/${encodeURIComponent(id)}/graph`);

export interface PolicyModel {
  tiers: { tier: Tier; min_risk: number; max_risk: number; approvers: string[] }[];
  escalation: { blast_radius_entities: number; blast_radius_users: number };
  gates: {
    dry_run: boolean;
    environment: string;
    live_environments: string[];
    live_execution_enabled: boolean;
  };
}

/** The policy this deployment enforces, generated from the engine.
 *
 *  Fetched rather than written down. A table of risk tiers typed into a page is
 *  a second answer to "who may approve this", and on the day the two disagree
 *  the wrong one is the one on the marketing site. */
export const getPolicyModel = () => get<PolicyModel>("/policy/model");
