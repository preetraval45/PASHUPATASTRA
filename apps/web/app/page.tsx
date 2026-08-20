import Link from "next/link";

import {
  Ago,
  Badge,
  Empty,
  Ident,
  Offline,
  Page,
  Panel,
  Stat,
  statusForSeverity,
} from "@/components/ui";
import { getAudit, getHealth, getIncidents, getTopologyCounts, type Incident } from "@/lib/api";

export const dynamic = "force-dynamic";

export default async function OverviewPage() {
  const [health, incidents, topology, audit] = await Promise.all([
    getHealth(),
    getIncidents(),
    getTopologyCounts(),
    getAudit(8),
  ]);

  if (!health) return <Offline />;

  const open = (incidents ?? []).filter((i) => i.state !== "resolved");
  const awaiting = open.filter((i) => i.state === "awaiting_approval");
  const users = open.reduce((n, i) => n + i.impact.estimated_users_affected, 0);
  const worst = open.reduce<Incident | null>(
    (acc, i) => (acc === null || rank(i) > rank(acc) ? i : acc),
    null,
  );

  return (
    <Page
      title="Overview"
      description="System state, open incidents, and the autonomy posture currently in force."
    >
      {/* The headline is a sentence, not a number. An operator arriving cold
          needs the verdict first and the metrics second. */}
      <section
        className={`panel p-5 ${
          worst ? "border-[rgb(var(--crit))]/30 bg-[rgb(var(--crit))]/5" : ""
        }`}
      >
        <p className="text-lg">
          {worst ? (
            <>
              <span className="text-[rgb(var(--crit))]">
                {open.length} open incident{open.length === 1 ? "" : "s"}
              </span>
              {awaiting.length > 0 && (
                <>
                  {" · "}
                  <span className="text-[rgb(var(--warn))]">
                    {awaiting.length} awaiting approval
                  </span>
                </>
              )}
            </>
          ) : (
            <span className="text-[rgb(var(--ok))]">No open incidents</span>
          )}
        </p>
        <p className="mt-1 text-sm text-[rgb(var(--muted))]">
          {worst
            ? worst.hypotheses[0]?.statement ?? "Diagnosis in progress."
            : `Watching ${topology?.nodes ?? 0} entities and ${topology?.edges ?? 0} observed access paths.`}
        </p>
      </section>

      <section className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Stat
          label="Open incidents"
          value={open.length}
          status={open.length ? "critical" : "ok"}
          hint={awaiting.length ? `${awaiting.length} need a decision` : "none awaiting approval"}
        />
        <Stat
          label="Accounts affected"
          value={users}
          status={users ? "warning" : undefined}
          hint="estimated, from blast radius"
        />
        <Stat
          label="Entities watched"
          value={topology?.nodes ?? 0}
          hint={`${topology?.edges ?? 0} observed access paths`}
        />
        <Stat
          label="Execution mode"
          value={health.dry_run ? "Dry run" : "Live"}
          status={health.dry_run ? undefined : "critical"}
          hint={health.dry_run ? "nothing is executed" : "actions change real systems"}
        />
      </section>

      {/* `[&>*]:min-w-0` because a grid item defaults to `min-width: auto`,
          which refuses to shrink below its content's minimum contribution. One
          long line in an incident summary therefore widened the panel to 834px
          inside a 343px column and took the whole page sideways with it. */}
      <div className="grid gap-6 lg:grid-cols-[1.6fr_1fr] [&>*]:min-w-0">
        <Panel
          title="Open incidents"
          aside={open.length > 0 && <Link href="/incidents" className="focusable rounded hover:text-[rgb(var(--ink))]">all incidents →</Link>}
        >
          {open.length === 0 ? (
            <Empty art="quiet" title="Quiet." action={{ href: "/incidents", label: "Open a scenario →" }}>
              Incidents appear here when Drishti correlates related detections. Quiet
              means nothing was detected, which is not the same as nothing happening.
            </Empty>
          ) : (
            <ul className="divide-y divide-[rgb(var(--edge))]">
              {open.map((incident) => (
                <li key={incident.id} className="py-4 first:pt-0 last:pb-0">
                  <Link href="/incidents" className="focusable block rounded">
                    <div className="flex flex-wrap items-center gap-3">
                      <Ident>{incident.id}</Ident>
                      <Badge status={statusForSeverity(incident.severity)}>
                        {incident.severity}
                      </Badge>
                      <span className="text-[11px] uppercase tracking-wide text-[rgb(var(--muted))]">
                        {incident.state.replace(/_/g, " ")}
                      </span>
                      <span className="ml-auto text-xs text-[rgb(var(--faint))]">
                        <Ago at={incident.opened_at} />
                      </span>
                    </div>
                    <p className="mt-2 text-sm">
                      {incident.hypotheses[0]?.statement ?? "Diagnosis in progress."}
                    </p>
                    <div className="mt-2 flex flex-wrap gap-x-6 gap-y-1 text-xs text-[rgb(var(--muted))]">
                      <span>
                        confidence{" "}
                        <span className="tnum text-[rgb(var(--ink))]">
                          {Math.round((incident.hypotheses[0]?.confidence ?? 0) * 100)}%
                        </span>
                      </span>
                      <span>
                        users{" "}
                        <span className="tnum text-[rgb(var(--ink))]">
                          {incident.impact.estimated_users_affected.toLocaleString()}
                        </span>
                      </span>
                      <span>
                        blast radius{" "}
                        <span className="tnum text-[rgb(var(--ink))]">
                          {incident.impact.blast_radius_entities}
                        </span>
                      </span>
                    </div>
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </Panel>

        <div className="space-y-6">
          <Panel title="Perception" aside={<Ago at={audit?.[0]?.at} />}>
            <dl className="space-y-3 text-sm">
              <Row label="Entities" value={topology?.nodes ?? 0} />
              <Row label="Observed access paths" value={topology?.edges ?? 0} />
              <Row label="Audit records" value={health.audit_records} />
              <Row
                label="Storage"
                value={health.audit_storage === "postgres" ? "durable" : "in memory"}
                warn={health.audit_storage !== "postgres"}
              />
            </dl>
          </Panel>

          <Panel
            title="Recent activity"
            aside={<Link href="/audit" className="focusable rounded hover:text-[rgb(var(--ink))]">audit →</Link>}
          >
            {!audit?.length ? (
              <Empty art="ledger" title="No activity recorded yet." action={{ href: "/incidents", label: "Open a scenario →" }}>
                Records are written before an action runs, never after, so an empty log
                means nothing has been attempted — not that something was attempted and
                lost.
              </Empty>
            ) : (
              <ul className="space-y-3 text-xs">
                {audit.slice(0, 6).map((record, index) => (
                  <li key={index} className="flex gap-3">
                    <span className="shrink-0 text-[rgb(var(--faint))]">
                      <Ago at={record.at} />
                    </span>
                    {/* `min-w-0` is what lets `truncate` truncate. A flex item
                        will not shrink below its content width, so `nowrap`
                        pushed the row out instead of clipping it — 239px past
                        the edge of a 375px screen. */}
                    <span className="min-w-0 truncate" title={record.summary}>
                      {record.summary}
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </Panel>
        </div>
      </div>

      <Panel title="The loop">
        <ol className="mono flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-[rgb(var(--faint))]">
          {["Observe", "Understand", "Predict", "Decide", "Act", "Verify", "Learn"].map(
            (stage, index, all) => (
              <li key={stage}>
                <span className="text-[rgb(var(--muted))]">{stage}</span>
                {index < all.length - 1 && <span className="px-1">→</span>}
              </li>
            ),
          )}
        </ol>
        <p className="mt-3 text-xs text-[rgb(var(--muted))]">
          Observe and Understand are live. Decide and Act run behind policy in dry-run.
          Verify compares observed state to what an action promised.
        </p>
      </Panel>
    </Page>
  );
}

function Row({ label, value, warn }: { label: string; value: string | number; warn?: boolean }) {
  return (
    <div className="flex items-baseline justify-between gap-4">
      <dt className="text-[rgb(var(--muted))]">{label}</dt>
      <dd className={`tnum ${warn ? "text-[rgb(var(--warn))]" : ""}`}>
        {typeof value === "number" ? value.toLocaleString() : value}
      </dd>
    </div>
  );
}

/** Order incidents by how loudly they are asking for attention. */
function rank(incident: Incident): number {
  const severity = { critical: 4, high: 3, medium: 2, low: 1 }[incident.severity] ?? 0;
  return severity * 10 + (incident.state === "awaiting_approval" ? 5 : 0);
}
