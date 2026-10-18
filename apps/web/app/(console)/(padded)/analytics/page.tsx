import type { Metadata } from "next";
import Link from "next/link";
import type { ReactNode } from "react";

import { Breakdown, DayColumns, TimeBars, type Slice } from "@/components/analytics";
import { Ago, Badge, Page } from "@/components/ui";
import {
  getActions,
  getAudit,
  getImpact,
  getIncidents,
  getIntelStatus,
  getTopology,
  getUsage,
} from "@/lib/api";

export const metadata: Metadata = {
  title: "Analytics",
  description:
    "Activity, incidents, response risk, the estate, Sati AI usage and feed health — charted from the live API.",
};

export const dynamic = "force-dynamic";

/** Risk bands, the same cut-points as `riskBand` and the autonomy tiers. These
 *  colours are functional (BRAND.md) and every row also carries its word. */
const BANDS = [
  { label: "low · 0–30", max: 30, tone: "52 211 153", hint: "can run unattended" },
  { label: "medium · 31–60", max: 60, tone: "251 191 36", hint: "one approver" },
  { label: "high · 61–80", max: 80, tone: "251 146 60", hint: "senior approver" },
  { label: "prohibited · 81+", max: 100, tone: "251 113 133", hint: "never autonomous" },
];

const SEVERITY_TONE: Record<string, string> = {
  critical: "251 113 133",
  high: "251 146 60",
  medium: "251 191 36",
  low: "52 211 153",
};

/**
 * One page for the numbers (RP-52). Every panel reads a live endpoint; a source
 * the deployed API does not serve yet is named as missing rather than drawn as
 * an empty chart.
 */
export default async function AnalyticsPage() {
  const [audit, incidents, actions, topology, intel, usage, impact] = await Promise.all([
    getAudit(500),
    getIncidents(),
    getActions(),
    getTopology(),
    getIntelStatus(),
    getUsage(),
    getImpact(),
  ]);

  const count = <T,>(items: T[], key: (item: T) => string) => {
    const tally = new Map<string, number>();
    for (const item of items) tally.set(key(item), (tally.get(key(item)) ?? 0) + 1);
    return [...tally.entries()].sort((a, b) => b[1] - a[1]);
  };

  const open = (incidents ?? []).filter((i) => i.state !== "resolved");
  const critical = (incidents ?? []).filter((i) => i.severity === "critical").length;

  const severitySlices: Slice[] = ["critical", "high", "medium", "low"]
    .map((sev) => ({
      label: sev,
      value: (incidents ?? []).filter((i) => i.severity === sev).length,
      tone: SEVERITY_TONE[sev],
      href: "/incidents",
    }))
    .filter((s) => s.value > 0);

  const stateSlices: Slice[] = count(incidents ?? [], (i) => i.state).map(([label, value]) => ({
    label: label.replaceAll("_", " "),
    value,
  }));

  const riskSlices: Slice[] = BANDS.map((band, index) => ({
    label: band.label,
    hint: band.hint,
    tone: band.tone,
    href: "/actions",
    value: (actions ?? []).filter(
      (a) => a.base_risk <= band.max && (index === 0 || a.base_risk > BANDS[index - 1].max),
    ).length,
  }));

  const reversibility: Slice[] = [
    { label: "read-only", value: (actions ?? []).filter((a) => a.read_only).length, tone: "47 163 160", hint: "observes, changes nothing" },
    { label: "reversible", value: (actions ?? []).filter((a) => !a.read_only && !a.irreversible).length, tone: "129 140 248", hint: "has a rollback" },
    { label: "irreversible", value: (actions ?? []).filter((a) => a.irreversible).length, tone: "251 113 133", hint: "cannot be undone" },
  ];

  const estate: Slice[] = count(topology?.nodes ?? [], (n) => n.kind).map(([label, value]) => ({
    label,
    value,
    href: "/infrastructure",
  }));

  const actors: Slice[] = count(audit ?? [], (r) => r.actor).map(([label, value]) => ({ label, value, href: "/audit" }));

  const feeds = Object.entries(intel?.feeds ?? {});
  const healthy = feeds.filter(([, f]) => f.ok && !f.stale).length;

  const usageDays = usage
    ? [...usage.days].sort((a, b) => a.day.localeCompare(b.day)).map((d) => ({
        day: d.day,
        value: d.tokens,
        detail: `${d.turns} question${d.turns === 1 ? "" : "s"}, ${d.from_cache} from cache`,
      }))
    : null;

  const views = impact?.views.value
    ? Object.entries(impact.views.value.by_day)
        .sort(([a], [b]) => a.localeCompare(b))
        .map(([day, value]) => ({ day, value }))
    : null;
  const routes: Slice[] = impact?.views.value
    ? Object.entries(impact.views.value.by_route)
        .sort((a, b) => b[1] - a[1])
        .slice(0, 8)
        .map(([label, value]) => ({ label, value }))
    : [];

  return (
    <Page
      title="Analytics"
      description="What the system has been doing, charted from the live API. Hover for exact values, click a legend entry to hide a series, click a row for the records behind it."
    >
      <section className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
        <Kpi label="Open incidents" value={incidents ? open.length : "—"} hint={incidents ? `${critical} critical` : "API unreachable"} href="/incidents" />
        <Kpi label="Audit records" value={audit ? audit.length : "—"} hint="in the current window" href="/audit" />
        <Kpi
          label="Response actions"
          value={actions ? actions.length : "—"}
          hint={actions ? `${actions.filter((a) => a.base_risk > 60).length} need a senior approver` : undefined}
          href="/actions"
        />
        <Kpi
          label="Estate"
          value={topology ? topology.nodes.length : "—"}
          hint={topology ? `${topology.edges.length} relationships` : undefined}
          href="/infrastructure"
        />
        <Kpi label="Intel feeds healthy" value={intel ? `${healthy}/${feeds.length}` : "—"} hint={intel?.synced_at ? "last sync shown below" : "not synced yet"} href="/observatory" />
      </section>

      <Card title="Activity" aside="audit records over time, by kind" wide>
        {audit ? (
          <TimeBars events={audit.map((r) => ({ at: r.at, group: r.kind }))} />
        ) : (
          <Missing what="the audit trail" />
        )}
      </Card>

      <div className="grid gap-6 lg:grid-cols-2">
        <Card title="Incidents by severity">
          {incidents ? <Breakdown slices={severitySlices} /> : <Missing what="incidents" />}
        </Card>
        <Card title="Incidents by state">
          {incidents ? <Breakdown slices={stateSlices} /> : <Missing what="incidents" />}
        </Card>
        <Card title="Response risk profile" aside="registered actions by base risk">
          {actions ? <Breakdown slices={riskSlices} /> : <Missing what="the action registry" />}
        </Card>
        <Card title="Reversibility" aside="what each action can undo">
          {actions ? <Breakdown slices={reversibility} /> : <Missing what="the action registry" />}
        </Card>
        <Card title="Estate by kind" aside="entities in the topology">
          {topology ? <Breakdown slices={estate} /> : <Missing what="the topology" />}
        </Card>
        <Card title="Who wrote the audit trail" aside="records by actor">
          {audit ? <Breakdown slices={actors} /> : <Missing what="the audit trail" />}
        </Card>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <Card title="Sati AI usage" aside={usage ? `tokens per day · ${usage.window_days} days` : undefined}>
          {usageDays ? (
            <>
              <DayColumns days={usageDays} unit="tokens" />
              <p className="mt-3 text-xs text-[rgb(var(--faint))]">
                Today: {usage!.today.turns} questions, {usage!.today.tokens.toLocaleString()} tokens
                {usage!.today.cache_hit_rate !== null && `, ${Math.round(usage!.today.cache_hit_rate * 100)}% from cache`}.
                Computed from {usage!.computed_from}.
              </p>
            </>
          ) : (
            <Missing what="usage history" endpoint="/usage" />
          )}
        </Card>
        <Card title="Site traffic" aside={views ? "page renders per day" : undefined}>
          {views ? (
            <>
              <DayColumns days={views} unit="page renders" />
              <div className="mt-4">
                <Breakdown slices={routes} />
              </div>
            </>
          ) : (
            <Missing what="traffic history" endpoint="/impact" />
          )}
        </Card>
      </div>

      <Card title="Threat-intel feeds" aside={intel?.synced_at ? <>synced <Ago at={intel.synced_at} /></> : undefined} wide>
        {intel ? (
          feeds.length === 0 ? (
            <p className="text-sm text-[rgb(var(--faint))]">No feeds configured.</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left text-xs text-[rgb(var(--faint))]">
                    <th className="py-2 pr-4 font-normal">Feed</th>
                    <th className="py-2 pr-4 font-normal">State</th>
                    <th className="py-2 pr-4 font-normal">Last synced</th>
                    <th className="py-2 font-normal">Note</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[rgb(var(--edge))]">
                  {feeds.map(([name, feed]) => (
                    <tr key={name}>
                      <td className="mono py-2 pr-4 text-xs">{name}</td>
                      <td className="py-2 pr-4">
                        {feed.ok === null ? (
                          <Badge status="neutral">never polled</Badge>
                        ) : feed.ok && !feed.stale ? (
                          <Badge status="ok">healthy</Badge>
                        ) : feed.stale ? (
                          <Badge status="warning">stale</Badge>
                        ) : (
                          <Badge status="high">failing</Badge>
                        )}
                      </td>
                      <td className="py-2 pr-4 text-xs text-[rgb(var(--muted))]">
                        {feed.synced_at ? <Ago at={feed.synced_at} /> : "—"}
                      </td>
                      <td className="py-2 text-xs text-[rgb(var(--faint))]">{feed.error ?? ""}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )
        ) : (
          <Missing what="feed status" />
        )}
      </Card>
    </Page>
  );
}

function Kpi({ label, value, hint, href }: { label: string; value: ReactNode; hint?: string; href: string }) {
  return (
    <Link
      href={href}
      className="focusable lift group rounded-xl border border-[rgb(var(--edge))] bg-[rgb(var(--panel))] p-4 transition hover:border-[rgb(var(--astra))]/50"
    >
      <p className="label">{label}</p>
      <p className="tnum mt-1 text-3xl font-semibold tracking-tight">{value}</p>
      {hint && <p className="mt-0.5 text-xs text-[rgb(var(--faint))] group-hover:text-[rgb(var(--muted))]">{hint}</p>}
    </Link>
  );
}

function Card({
  title,
  aside,
  children,
}: {
  title: string;
  aside?: ReactNode;
  children: ReactNode;
  wide?: boolean;
}) {
  return (
    <section className="rounded-xl border border-[rgb(var(--edge))] bg-[rgb(var(--panel))] p-5">
      <header className="mb-4 flex flex-wrap items-baseline justify-between gap-2">
        <h2 className="text-base font-semibold tracking-tight">{title}</h2>
        {aside && <span className="text-xs text-[rgb(var(--faint))]">{aside}</span>}
      </header>
      {children}
    </section>
  );
}

/** A source that did not answer, said in words. */
function Missing({ what, endpoint }: { what: string; endpoint?: string }) {
  return (
    <p className="rounded-lg border border-dashed border-[rgb(var(--edge))] px-4 py-6 text-center text-sm text-[rgb(var(--faint))]">
      No data for {what} from the live API
      {endpoint && (
        <>
          {" "}— <span className="mono">{endpoint}</span> arrives with the next API deploy
        </>
      )}
      .
    </p>
  );
}
