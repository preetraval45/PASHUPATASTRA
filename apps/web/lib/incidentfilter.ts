/**
 * Which incidents the list shows, and in what order — from the URL alone.
 *
 * Server-side and link-driven, like the observatory's feed filter: a filtered
 * view is a URL someone can send, and it works with scripts off. Unknown
 * values fall back to "everything" rather than to an empty list, because an
 * empty list from a mistyped link reads as "no incidents", which is a claim.
 */

import type { Incident, IncidentState } from "./api.ts";

export const SEVERITIES = ["critical", "high", "medium", "low"] as const;
export type Severity = (typeof SEVERITIES)[number];

/** Closed means nothing more will happen without a new incident. Escalated is
 *  open: a human owns it now, and it is not done. */
const CLOSED: ReadonlySet<IncidentState> = new Set(["resolved", "rolled_back"]);

export type IncidentQuery = {
  severity: Severity | null;
  status: "open" | "closed" | null;
  sort: "newest" | "severity";
};

export function parseQuery(params: Record<string, string | string[] | undefined>): IncidentQuery {
  const one = (k: string) => {
    const v = params[k];
    return Array.isArray(v) ? v[0] : v;
  };
  const severity = one("severity");
  const status = one("status");
  return {
    severity: (SEVERITIES as readonly string[]).includes(severity ?? "") ? (severity as Severity) : null,
    status: status === "open" || status === "closed" ? status : null,
    sort: one("sort") === "severity" ? "severity" : "newest",
  };
}

export function applyQuery<T extends Pick<Incident, "severity" | "state" | "opened_at">>(
  incidents: T[],
  q: IncidentQuery,
): T[] {
  const rank = (s: string) => SEVERITIES.indexOf(s as Severity);
  return incidents
    .filter((i) => !q.severity || i.severity === q.severity)
    .filter((i) => !q.status || (q.status === "closed") === CLOSED.has(i.state))
    .sort((a, b) =>
      q.sort === "severity" && rank(a.severity) !== rank(b.severity)
        ? rank(a.severity) - rank(b.severity)
        : b.opened_at.localeCompare(a.opened_at),
    );
}

/** The URL for `q` with one field changed; defaults are left out, so the
 *  unfiltered list is plain `/incidents`. */
export function hrefFor(q: IncidentQuery, change: Partial<IncidentQuery>): string {
  const next = { ...q, ...change };
  const params = new URLSearchParams();
  if (next.severity) params.set("severity", next.severity);
  if (next.status) params.set("status", next.status);
  if (next.sort !== "newest") params.set("sort", next.sort);
  const s = params.toString();
  return s ? `/incidents?${s}` : "/incidents";
}
