/**
 * The signed-in account, in this browser (services/api/app/accounts.py).
 *
 * The session is a signed token from the API, kept in localStorage and sent as
 * `Authorization: Bearer`. A small store with listeners rather than a React
 * context, so any component can read it without a provider around the tree.
 * Signing out forgets the token; deleting the account asks the API to erase it.
 */
import { API_BASE } from "@/lib/api";

const KEY = "pashu.session";

export type Account = { id: string; name: string; provider: "guest" | "email" | "google"; email: string | null };
export type OrgSettings = {
  accent: "default" | "series-1" | "series-2" | "series-5" | "series-6" | "series-7";
  logo: string | null;
  welcome: string;
  required: string[];
  due: string | null;
};
export type Membership = { id: string; name: string; role: "owner" | "admin" | "employee"; invite?: string; settings: OrgSettings };
export type ModuleRecord = {
  best: number;
  last: number;
  attempts: number;
  passed: boolean;
  at: number;
  /** Passed in a test the server marked from the answers given (not a self-reported score). */
  verified_passed?: boolean;
};
export type Me = { user: Account; orgs: Membership[]; training: Record<string, ModuleRecord>; platform_admin: boolean };
export type Member = Account & {
  role: Membership["role"];
  joined: number | null;
  passed: string[];
  /** Levels passed in server-marked tests. */
  verified: string[];
  attempts: number;
  last_active: number | null;
  average: number | null;
  policies_acknowledged: number;
  required_passed: number;
};

type State = { token: string | null; me: Me | null; ready: boolean };
let state: State = { token: null, me: null, ready: false };
const listeners = new Set<() => void>();

function set(next: Partial<State>) {
  state = { ...state, ...next };
  listeners.forEach((l) => l());
}

export function subscribe(listener: () => void): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

export function snapshot(): State {
  return state;
}

export class AccountFailure extends Error {
  constructor(
    message: string,
    readonly status: number,
  ) {
    super(message);
  }
}

async function call<T>(path: string, init: RequestInit = {}): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE}${path}`, {
      ...init,
      headers: {
        "Content-Type": "application/json",
        ...(state.token ? { Authorization: `Bearer ${state.token}` } : {}),
        ...(init.headers ?? {}),
      },
      cache: "no-store",
    });
  } catch {
    throw new AccountFailure("Can't reach the server. Check your connection and try again.", 0);
  }
  const body = (await response.json().catch(() => ({}))) as { detail?: unknown };
  if (!response.ok) {
    const detail = typeof body.detail === "string" ? body.detail : "Something went wrong. Try again.";
    if (response.status === 401 && state.token && path === "/me") signOut();
    throw new AccountFailure(detail, response.status);
  }
  return body as T;
}

function keep(token: string | null) {
  try {
    if (token) localStorage.setItem(KEY, token);
    else localStorage.removeItem(KEY);
  } catch {
    // Not kept: signed in for this page only.
  }
}

/** Reads the kept token and the account behind it. Safe to call more than once. */
export async function load(): Promise<void> {
  if (state.ready) return;
  let token: string | null = null;
  try {
    token = localStorage.getItem(KEY);
  } catch {
    // No storage: signed out.
  }
  if (!token) return set({ ready: true });
  set({ token });
  try {
    set({ me: await call<Me>("/me"), ready: true });
  } catch {
    set({ ready: true });
  }
}

export async function refresh(): Promise<Me | null> {
  if (!state.token) return null;
  const me = await call<Me>("/me");
  set({ me });
  return me;
}

async function begin(session: Promise<{ token: string }>): Promise<Me> {
  const { token } = await session;
  keep(token);
  set({ token });
  const me = await call<Me>("/me");
  set({ me, ready: true });
  return me;
}

export const signInAsGuest = () => begin(call("/auth/guest", { method: "POST" }));
export const signIn = (email: string, password: string) =>
  begin(call("/auth/login", { method: "POST", body: JSON.stringify({ email, password }) }));
export const register = (email: string, password: string, name: string) =>
  begin(call("/auth/register", { method: "POST", body: JSON.stringify({ email, password, name }) }));
export const signInWithGoogle = (credential: string) =>
  begin(call("/auth/google", { method: "POST", body: JSON.stringify({ credential }) }));

export function signOut(): void {
  keep(null);
  set({ token: null, me: null, ready: true });
}

export async function deleteAccount(): Promise<void> {
  await call("/me", { method: "DELETE" });
  signOut();
}

export async function rename(name: string): Promise<void> {
  set({ me: await call<Me>("/me", { method: "PATCH", body: JSON.stringify({ name }) }) });
}

export async function createCompany(name: string): Promise<Me> {
  const me = await call<Me>("/orgs", { method: "POST", body: JSON.stringify({ name }) });
  set({ me });
  return me;
}

export async function joinCompany(code: string): Promise<Me> {
  const me = await call<Me>("/orgs/join", { method: "POST", body: JSON.stringify({ code }) });
  set({ me });
  return me;
}

export const companyMembers = (org: string) =>
  call<{ org: { id: string; name: string; invite: string; settings: OrgSettings }; members: Member[] }>(
    `/orgs/${encodeURIComponent(org)}/members`,
  );
export const newInvite = (org: string) =>
  call<{ invite: string }>(`/orgs/${encodeURIComponent(org)}/invite`, { method: "POST" });
export const setRole = (org: string, member: string, role: "admin" | "employee") =>
  call(`/orgs/${encodeURIComponent(org)}/members/${encodeURIComponent(member)}`, { method: "PUT", body: JSON.stringify({ role }) });
export const removeMember = (org: string, member: string) =>
  call(`/orgs/${encodeURIComponent(org)}/members/${encodeURIComponent(member)}`, { method: "DELETE" });

/** Saves one module result to the account. Quietly does nothing when signed out. */
export async function saveTraining(slug: string, score: number, passed: boolean): Promise<void> {
  if (!state.token) return;
  try {
    const { training } = await call<{ training: Me["training"] }>(`/me/training/${encodeURIComponent(slug)}`, {
      method: "PUT",
      body: JSON.stringify({ score, passed }),
    });
    if (state.me) set({ me: { ...state.me, training } });
  } catch {
    // Kept in this browser; the next result will try again.
  }
}

export const authConfig = () =>
  call<{ google_client_id: string | null; guest: boolean; email: boolean; email_reset: boolean }>("/auth/config");

/** Asks for a reset email. The answer says whether this deployment can send one at all. */
export const forgotPassword = (email: string) =>
  call<{ email_reset: boolean }>("/auth/forgot", { method: "POST", body: JSON.stringify({ email }) });

/** Sets a new password from a reset link's token, and signs in with it. */
export const resetPassword = (token: string, password: string) =>
  begin(call("/auth/reset", { method: "POST", body: JSON.stringify({ token, password }) }));

/** A new password, given the current one. Other devices are signed out; this one gets a fresh session. */
export async function changePassword(current: string, password: string): Promise<void> {
  const { token } = await call<{ token: string }>("/me/password", { method: "PUT", body: JSON.stringify({ current, password }) });
  keep(token);
  set({ token });
}

/** Ends every session on every device, this one included. */
export async function signOutEverywhere(): Promise<void> {
  await call("/me/signout-all", { method: "POST" });
  signOut();
}

/** A one-hour reset link for a member, for an admin to hand over. */
export const adminResetLink = (org: string, member: string) =>
  call<{ link: string; expires_in: number }>(
    `/orgs/${encodeURIComponent(org)}/members/${encodeURIComponent(member)}/reset`,
    { method: "POST" },
  );

export type Policy = { id: string; title: string; body: string; created: number; acknowledged: number | null; acks?: number };

export const companyPolicies = (org: string) =>
  call<{ org: { id: string; name: string; settings: OrgSettings }; role: Membership["role"]; policies: Policy[] }>(
    `/orgs/${encodeURIComponent(org)}/policies`,
  );
export const addPolicy = (org: string, title: string, body: string) =>
  call<Policy>(`/orgs/${encodeURIComponent(org)}/policies`, { method: "POST", body: JSON.stringify({ title, body }) });
export const removePolicy = (org: string, policy: string) =>
  call(`/orgs/${encodeURIComponent(org)}/policies/${encodeURIComponent(policy)}`, { method: "DELETE" });
export const acknowledgePolicy = (org: string, policy: string) =>
  call(`/orgs/${encodeURIComponent(org)}/policies/${encodeURIComponent(policy)}/ack`, { method: "POST" });

/** Saves a company's customization; only the fields given change. Refreshes the account so the new
 *  accent and name show everywhere at once. */
export async function saveCompanySettings(org: string, changes: Partial<OrgSettings> & { name?: string }): Promise<void> {
  await call(`/orgs/${encodeURIComponent(org)}/settings`, { method: "PUT", body: JSON.stringify(changes) });
  await refresh();
}


export type AdminOverview = {
  users: { id: string; name: string; email: string | null; provider: Account["provider"]; created: number | null; admin: boolean }[];
  companies: { id: string; name: string; members: number; created: number | null; accent: OrgSettings["accent"] }[];
};

/** Every account and company: platform administrators only. */
export const adminOverview = () => call<AdminOverview>("/admin/overview");

export type PolicyQuestion = {
  action_id: string;
  incident_ref?: string;
  blast_radius_entities?: number;
  blast_radius_users?: number;
  diagnostic_confidence?: number;
};

/** Approve as the signed-in administrator: Dharma first records a real verdict (the page only showed a
 *  preview), then that verdict is approved. `presented` is when the panel reached the screen, so the
 *  approval-fatigue measure times the decision, not the page load. */
export async function approveAction(question: PolicyQuestion, presented: Date): Promise<{ granted_by: string | null }> {
  const verdict = await call<Record<string, unknown>>("/policy/evaluate", { method: "POST", body: JSON.stringify(question) });
  return call("/policy/approve", {
    method: "POST",
    body: JSON.stringify({ verdict, approver: state.me?.user.name ?? "administrator", presented_at: presented.toISOString() }),
  });
}

export async function denyAction(question: PolicyQuestion, reason: string, presented: Date): Promise<void> {
  const verdict = await call<Record<string, unknown>>("/policy/evaluate", { method: "POST", body: JSON.stringify(question) });
  await call("/policy/deny", {
    method: "POST",
    body: JSON.stringify({ verdict, approver: state.me?.user.name ?? "administrator", reason, presented_at: presented.toISOString() }),
  });
}

/** Sends a test's chosen options to be marked by the server. Null when signed out (the browser marks it). */
export async function submitAttempt(
  slug: string,
  answers: string[],
): Promise<{ score: number; passed: boolean; correct: boolean[] } | null> {
  if (!state.token) return null;
  const result = await call<{ score: number; passed: boolean; correct: boolean[]; training: Me["training"] }>(
    `/me/training/${encodeURIComponent(slug)}/attempt`,
    { method: "POST", body: JSON.stringify({ answers }) },
  );
  if (state.me) set({ me: { ...state.me, training: result.training } });
  return result;
}
