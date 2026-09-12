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
  /** How the tier was arrived at, emitted by the engine branches that arrived
   *  at it. Optional because a verdict stored before R65 does not carry it —
   *  the panel falls back to the arithmetic rather than inventing the steps. */
  tier_reasons?: TierStep[];
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
  factor?: RiskFactor;
}

/** The named inputs risk is priced from. The strings are the engine's own — a
 *  label the dashboard invented would be a second name for one term. */
export type RiskFactor =
  | "blast_radius"
  | "confidence"
  | "novelty"
  | "reversibility"
  | "environment"
  | "agent_limit";

export const FACTOR_LABEL: Record<RiskFactor, string> = {
  blast_radius: "blast radius",
  confidence: "confidence",
  novelty: "novelty",
  reversibility: "reversibility",
  environment: "environment",
  agent_limit: "agent limit",
};

/** One rule that fired while the tier was being decided. `from_tier` equal to
 *  `to_tier` means the rule fired and the tier was already there — an
 *  independent reason for the outcome, not a step that did nothing. */
export interface TierStep {
  rule: string;
  factor: RiskFactor | null;
  detail: string;
  from_tier: Tier;
  to_tier: Tier;
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

/** Tokens against the provider's daily allowance, rolled up from the ledger
 *  (R104). Every figure is recomputable from `/audit`; `scripts/verifyusage.py`
 *  does so and compares. */
export interface Usage {
  as_of: string;
  timezone: string;
  window_days: number;
  allowance: { tokens_per_day: number; source: string };
  today: {
    day: string;
    turns: number;
    from_cache: number;
    answered_by_model: number;
    tokens: number;
    cache_hit_rate: number | null;
    allowance_used: number | null;
  };
  days: { day: string; turns: number; from_cache: number; tokens: number }[];
  spend_usd: number;
  spend_reason: string;
  computed_from: string;
}
export const getUsage = () => get<Usage>("/usage");
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
export async function evaluatePolicy(body: PolicyQuestion): Promise<Verdict | null> {
  return post<Verdict>("/policy/evaluate", body);
}

export interface PolicyQuestion {
  action_id: string;
  incident_ref?: string | null;
  blast_radius_entities?: number;
  blast_radius_users?: number;
  diagnostic_confidence?: number;
}

/** The same verdict, computed to be shown. Writes nothing to the audit ledger.
 *
 *  A page render is not a decision. `evaluatePolicy` appends a record every
 *  time it is called, which is right for an operator asking for authorisation
 *  and wrong for a page asking what authorisation would need — that was three
 *  records per view of an incident, and one incident accumulated 144 identical
 *  lines from being read (R93). Anything that renders a verdict uses this; the
 *  recording call is for the moment somebody actually asks. */
export async function previewPolicy(body: PolicyQuestion): Promise<Verdict | null> {
  return post<Verdict>("/policy/preview", body);
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

export interface RuledOut {
  reading: string;
  ruled_out_by: string[];
  /** Refs it also claimed that resolved to nothing. Kept beside the ones that
   *  held, rather than deleted, so the record shows what was claimed. */
  dropped_refs?: string[];
}

/** One step the agent took. `refs` on a `tool_result` is what came back — the
 *  records that step read, which is the half of a trace that makes it
 *  checkable rather than merely narrated. */
export interface TraceStep {
  hop: number;
  kind: string;
  name?: string;
  detail?: { refs?: string[]; entity_key?: string; ok?: boolean; reason?: string };
}

/** One answer from Sati, plus everything needed to judge how far to trust it. */
export type ChatAnswer = {
  answer: string;
  evidence_refs: string[];
  dropped_refs: string[];
  answerable: boolean;
  grounded: boolean;
  /** True when the model answered and cited nothing that resolved, so `answer`
   *  is the fixed sentence saying its text was withheld. The text itself is in
   *  the audit trail and deliberately not in this response. */
  withheld: boolean;
  proposed_action_id: string | null;
  verdict: Verdict | null;
  approval_id: string | null;
  /** Readings the evidence also admitted, each with what closed it. Verified
   *  like citations: one whose refs resolve to nothing is dropped, because a
   *  rejection a reader cannot check is worth less than no rejection. */
  considered: RuledOut[];
  dropped_considered: { reading: string; claimed_refs: string[] }[];
  trace: TraceStep[];
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
/** One feed's health. Three separate facts, deliberately not collapsed:
 *  `synced_at` is when it last answered, `cursor` is where it last *moved to*,
 *  and `stale` is the first being too long ago. A quiet feed and a broken one
 *  look identical unless all three are kept apart. */
export interface FeedStatus {
  cursor: string | null;
  synced_at: string | null;
  age_seconds: number | null;
  /** `null` when it has never been polled — a fresh deployment, not a fault. */
  ok: boolean | null;
  error: string | null;
  stale: boolean;
}

export interface IntelStatus {
  feeds: Record<string, FeedStatus>;
  /** The most recent successful poll across all feeds. The page's headline. */
  synced_at: string | null;
  stale_after_hours: number;
  durable: boolean;
}

export const getIntelStatus = () => get<IntelStatus>("/intel/status");

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

export interface DebriefEntity {
  entity_key: string;
  evidence: string[];
  /** Held an observation that rules out the plausible-but-wrong explanation —
   *  the difference between being right and being right by luck. */
  decisive: boolean;
  decisive_evidence: string[];
}

export interface Verdict2 {
  total: number;
  grade: "clean" | "sound" | "shaky" | "missed";
  /** Each line carries what it was judged against — refs for the categories
   *  resting on evidence, action ids for the one resting on a decision. R64's
   *  rule: a point gained or lost traces to a named thing. */
  breakdown: {
    name: string;
    points: number;
    of: number;
    note: string;
    evidence?: string[];
    contradicted_by?: string[];
    on_entities?: string[];
    opened?: string[];
    chose_action?: string;
    plan_actions?: string[];
  }[];
  /** The full board: every entity in the exercise, in exactly one list. */
  debrief?: {
    opened: DebriefEntity[];
    missed: DebriefEntity[];
    decisive_evidence: string[];
  };
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

/** A drafted playbook or post-incident report.
 *
 *  `status` is always "draft" and there is no other value: adopting one is a
 *  registered action that goes through Dharma, and what comes out the far side
 *  is an audit record naming a human — never a different rendering of this. */
export interface Draft {
  kind: "playbook" | "post_incident";
  incident_ref: string;
  title: string;
  status: "draft";
  /** The registered action adopting this would require. Named here so the page
   *  can show what it would cost rather than offering a button that implies
   *  none. */
  adopt_action_id: string;
  sections: { title: string; lines: { text: string; refs: string[] }[] }[];
}

export const getDraft = (incidentId: string, kind: string) =>
  get<Draft>(`/incidents/${encodeURIComponent(incidentId)}/draft/${kind}`);

/** A Sigma rule drafted from one step of an incident (R71).
 *
 *  `mappings` is the part that makes this reviewable rather than impressive:
 *  each entry names the telemetry field the Sigma field was read from and the
 *  events that carried it, so a reader can check the rule against the evidence
 *  instead of against how plausible it looks.
 *
 *  `valid` is the API reading its own output back through a Sigma parser, not a
 *  claim the page makes on its behalf. */
export interface DetectionRule {
  incident_ref: string;
  technique: { id: string; name: string; tactic: string } | null;
  title: string;
  status: "experimental";
  rule_id: string;
  /** False when every field is an instance value from this incident — an
   *  indicator match rather than a detection for the technique. */
  behavioural: boolean;
  yaml: string;
  valid: boolean;
  problems: string[];
  mappings: {
    sigma_field: string;
    source_field: string;
    value: string;
    refs: string[];
    generalises: boolean;
  }[];
  /** Fields this technique's detection usually rests on that the telemetry
   *  could not supply. */
  gaps: { sigma_field: string; reason: string }[];
  /** Fields we hold and deliberately did not map, with the reason. Separate
   *  from `gaps`: one is a collection problem, the other a translation refused. */
  not_mapped: { sigma_field: string; reason: string }[];
  refs: string[];
}

export interface DetectionRuleIndex {
  incident_ref: string;
  techniques: { id: string; name: string; tactic: string }[];
}

export const getDetectionRules = (incidentId: string) =>
  get<DetectionRuleIndex>(`/incidents/${encodeURIComponent(incidentId)}/detection-rule`);

export const getDetectionRule = (incidentId: string, techniqueId: string) =>
  get<DetectionRule>(
    `/incidents/${encodeURIComponent(incidentId)}/detection-rule/${encodeURIComponent(
      techniqueId,
    )}`,
  );

/** One causal step, placed in time by the records that established it. */
export interface TimelineStep {
  index: number;
  entity_key: string;
  transition: string;
  at: string;
  refs: string[];
}

export interface Timeline {
  incident_ref: string;
  steps: TimelineStep[];
  /** The entities an intervention could have been applied to — one per step.
   *  Entities the incident merely mentions are excluded, because what blocking
   *  something it never recorded would have done is not a question its records
   *  can answer. */
  askable: string[];
}

/** What acting on one entity at one moment would have prevented (R72).
 *
 *  `prevented` and `unavoidable` are two different things and the difference is
 *  the whole point: a step later than the intervention that was never
 *  downstream of it would have happened anyway, and counting it would inflate
 *  the one number here anybody would quote.
 *
 *  `basis` carries the assumptions the records cannot settle. It is rendered,
 *  not summarised — it is what makes this an estimate rather than a claim. */
export interface Counterfactual {
  incident_ref: string;
  entity_key: string;
  at: string;
  /** The first record naming this entity. Acting earlier is refused. */
  earliest_defensible: string;
  summary: string;
  prevented: TimelineStep[];
  unavoidable: TimelineStep[];
  already_happened: TimelineStep[];
  untimed: { index: number; entity_key: string; reason: string }[];
  avoided_entities: string[];
  avoided_users: number;
  gap_seconds: number;
  basis: string[];
  reach: string[];
  refs: string[];
}

export const getTimeline = (incidentId: string) =>
  get<Timeline>(`/incidents/${encodeURIComponent(incidentId)}/timeline`);

/** The case for the leading alternative, and what answers it (R73).
 *
 *  `verdict` turns on one thing: whether something stored and resolvable
 *  contradicts the rival. "unrefuted" does not mean the alternative is right —
 *  it means the diagnosis has not earned its place over it, which is an open
 *  question rather than a rival conclusion.
 *
 *  The confidence figures are shown but never decide. A confidence is a number
 *  an author wrote, and the diagnosis asserting its own likelihood is the claim
 *  under examination rather than evidence for it. */
export interface Contest {
  incident_ref: string;
  verdict: "upheld" | "unrefuted";
  leader: ContestCase;
  rival: ContestCase;
  argument: string;
  ruled_out_by: string[];
  /** Contradictions the incident claims that resolve to nothing. */
  unresolved_rejection: string[];
  /** Observations both explain — what makes them answers to one question. */
  shared: string[];
  separators: string[];
  /** Records the rival accounts for and the diagnosis does not cite. */
  unexplained_by_leader: string[];
  refs: string[];
}

export interface ContestCase {
  ref: string;
  statement: string;
  confidence: number;
  supported_by: string[];
  uncited: string[];
}

export const getContest = (incidentId: string) =>
  get<Contest>(`/incidents/${encodeURIComponent(incidentId)}/contest`);

export const getCounterfactual = (incidentId: string, entityKey: string, at: string) =>
  get<Counterfactual>(
    `/incidents/${encodeURIComponent(incidentId)}/counterfactual` +
      `?entity_key=${encodeURIComponent(entityKey)}&at=${encodeURIComponent(at)}`,
  );

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

/** One row in the command palette's index. Deliberately tiny: a label, a hint
 *  and a href. The palette matches text and then navigates, so anything else is
 *  weight sent to every visitor on every page. */
export type SearchItem = {
  kind: string;
  label: string;
  hint?: string;
  href: string;
};

/** The palette's whole index, fetched once on the server so no keystroke ever
 *  waits on a request. Returns an empty list rather than throwing: a palette
 *  that cannot reach the API should still offer the named jumps and the pages,
 *  which are static and always correct. */
export async function getSearchIndex(): Promise<SearchItem[]> {
  const data = await get<{ items: SearchItem[] }>("/search/index");
  return data?.items ?? [];
}

/** Blast radius, in both the forms the page needs.
 *
 *  `affected` is authoritative and is what risk scoring uses. `reached` and
 *  `edges` are the same reach expressed as a walk that refused to cross any
 *  edge without evidence, so they can legitimately cover *fewer* entities —
 *  `uncited` is that difference, kept rather than hidden. */
export interface BlastRadius {
  origin: string;
  affected: string[];
  entity_count: number;
  estimated_users: number;
  reached?: {
    key: string;
    name: string;
    kind: string;
    severity: string | null;
    estimated_users: number;
    depth: number;
  }[];
  edges?: {
    source: string;
    target: string;
    kind: string;
    evidence: string[];
    depth: number;
  }[];
  uncited?: string[];
}

export const getBlastRadius = (entityKey: string) =>
  get<BlastRadius>(`/topology/blast-radius/${encodeURIComponent(entityKey)}`);
