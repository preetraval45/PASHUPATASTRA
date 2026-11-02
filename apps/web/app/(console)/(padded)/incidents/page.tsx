import { Filter, FilterRow } from "@/components/filter";
import { HappeningNow } from "@/components/happeningnow";
import { IncidentView } from "@/components/incident";
import { IncidentRows } from "@/components/incidentlist";
import { Scenarios } from "@/components/scenarios";
import { TriageItem, TriageList } from "@/components/triage";
import { Empty, Offline, Page } from "@/components/ui";
import { getActions, getIncidents, getPastIncidents } from "@/lib/api";
import { SEVERITIES, applyQuery, hrefFor, parseQuery } from "@/lib/incidentfilter";
import { KINDS, type Kind, isReal, kindOf, parseKind } from "@/lib/incidentkinds";

import type { Metadata } from "next";
import Link from "next/link";

export const metadata: Metadata = {
  title: "Incidents",
  description:
    "Security incidents happening in the world now, built from public threat feeds, and thousands from the public record — each citing the records behind it.",
};

export const dynamic = "force-dynamic";

type Params = Record<string, string | string[] | undefined>;

const PAGE = 25;
const PAST_KINDS: Kind[] = ["KEV", "NVD", "PKG", "RW", "BREACH", "CAMPAIGN"];

function one(params: Params, key: string): string | undefined {
  const v = params[key];
  return Array.isArray(v) ? v[0] : v;
}

/** The current URL with some parameters changed; empty values are dropped. */
function link(params: Params, change: Record<string, string | null>, hash = ""): string {
  const next = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    const value = Array.isArray(v) ? v[0] : v;
    if (value) next.set(k, value);
  }
  for (const [k, v] of Object.entries(change)) {
    if (v) next.set(k, v);
    else next.delete(k);
  }
  const s = next.toString();
  return `/incidents${s ? `?${s}` : ""}${hash}`;
}

export default async function IncidentsPage({ searchParams }: { searchParams: Promise<Params> }) {
  const params = await searchParams;
  const q = parseQuery(params);
  const kind = parseKind(params.kind);
  const pastKind = parseKind(params.pkind);
  const pastQuery = (one(params, "pq") ?? "").trim().slice(0, 80);
  const pastPage = Math.max(1, Number.parseInt(one(params, "ppage") ?? "1", 10) || 1);

  const [all, actions, past] = await Promise.all([
    getIncidents(),
    getActions(),
    getPastIncidents({ offset: (pastPage - 1) * PAGE, limit: PAGE, kind: pastKind, q: pastQuery || null }),
  ]);
  if (!all) return <Offline />;

  // A deployment without the live feeds serves the written scenarios; they keep their own layout.
  if (!all.some((i) => isReal(i.id))) return <Scripted all={all} actions={actions} q={q} />;

  const live = applyQuery(all, q).filter((i) => !kind || kindOf(i.id) === kind);
  const counts = new Map<Kind, number>();
  for (const i of all) {
    const k = kindOf(i.id);
    if (k) counts.set(k, (counts.get(k) ?? 0) + 1);
  }
  const pages = past ? Math.max(1, Math.ceil(past.total / PAGE)) : 1;

  return (
    <Page
      title="Incidents"
      description="What is happening in the world now, from public threat feeds, and the record of what has happened. Every incident cites the records behind it."
    >
      <p className="panel px-5 py-4 text-sm text-[rgb(var(--muted))]">
        <span className="text-2xl font-semibold text-[rgb(var(--ink))] tnum">
          {(all.length + (past?.total ?? 0)).toLocaleString()}
        </span>{" "}
        real incidents: <span className="tnum text-[rgb(var(--ink))]">{all.length.toLocaleString()}</span> live from
        the feeds,{" "}
        <a className="underline underline-offset-4" href="#record-section">
          <span className="tnum">{(past?.total ?? 0).toLocaleString()}</span> from the record
        </a>
        . No scenario or sample data is listed here.
      </p>

      <HappeningNow />

      <section aria-labelledby="live" className="space-y-4">
        <div className="flex flex-wrap items-baseline justify-between gap-2">
          <h2 id="live" className="text-xl font-semibold tracking-tight">
            Live incidents
          </h2>
          <p className="text-xs text-[rgb(var(--faint))]" aria-live="polite">
            {live.length} of {all.length}, rebuilt from the feeds every few minutes
          </p>
        </div>
        <FilterRow label="Kind">
          <Filter href={link(params, { kind: null })} label={`All ${all.length}`} active={!kind} />
          {(Object.keys(KINDS) as Kind[])
            .filter((k) => counts.get(k))
            .map((k) => (
              <Filter
                key={k}
                href={link(params, { kind: k.toLowerCase() })}
                label={`${KINDS[k].label} ${counts.get(k)}`}
                active={kind === k}
              />
            ))}
        </FilterRow>
        <FilterRow label="Severity">
          <Filter href={link(params, { severity: null })} label="Any" active={!q.severity} />
          {SEVERITIES.map((s) => (
            <Filter key={s} href={link(params, { severity: s })} label={s} active={q.severity === s} />
          ))}
        </FilterRow>
        {live.length === 0 ? (
          <Empty art="quiet" title="Nothing matches these filters.">
            <Link className="underline underline-offset-4" href="/incidents">
              Show every live incident
            </Link>
            .
          </Empty>
        ) : (
          <IncidentRows incidents={live} />
        )}
      </section>

      <section aria-labelledby="record" className="mt-10 space-y-4" id="record-section">
        <div>
          <h2 id="record" className="text-xl font-semibold tracking-tight">
            From the record
          </h2>
          <p className="mt-1 max-w-3xl text-sm text-[rgb(var(--muted))]">
            Every vulnerability CISA has confirmed exploited since 2021; three years of NVD&apos;s critical
            CVEs and a year of its high ones; ransomware groups&apos; monthly claims from the ransomwatch
            archive (2020–2025, never naming victims); MITRE ATT&amp;CK&apos;s documented intrusion
            campaigns, step by technique; a year of malicious packages OpenSSF reported on npm, PyPI and six
            other ecosystems; and every breach Have I Been {past?.total ? `: ${past.total.toLocaleString()} incidents` : ""}. Breach data is HIBP&apos;s,
            under CC BY 4.0, and campaigns are © The MITRE Corporation; each incident links its source.
          </p>
        </div>
        <form action="/incidents#record-section" className="flex flex-wrap gap-2" role="search">
          {Object.entries(params)
            .filter(([k]) => !["pq", "ppage"].includes(k))
            .map(([k, v]) => (
              <input key={k} type="hidden" name={k} value={Array.isArray(v) ? v[0] : (v ?? "")} />
            ))}
          <label className="sr-only" htmlFor="pq">
            Search the record
          </label>
          <input
            id="pq"
            name="pq"
            defaultValue={pastQuery}
            placeholder="Search: log4j, ivanti, adobe…"
            className="focusable min-w-0 flex-1 rounded-xl border border-[rgb(var(--edge))] bg-[rgb(var(--panel))] px-3 py-2 text-sm"
          />
          <button
            type="submit"
            className="focusable rounded-xl border border-[rgb(var(--edge-strong))] px-4 py-2 text-sm hover:bg-[rgb(var(--raised))]"
          >
            Search
          </button>
        </form>
        <FilterRow label="Kind">
          <Filter href={link(params, { pkind: null, ppage: null }, "#record-section")} label="All" active={!pastKind} />
          {PAST_KINDS.map((k) => (
            <Filter
              key={k}
              href={link(params, { pkind: k.toLowerCase(), ppage: null }, "#record-section")}
              label={KINDS[k].label}
              active={pastKind === k}
            />
          ))}
        </FilterRow>
        {!past ? (
          <Empty art="quiet" title="The record is not available right now." />
        ) : past.items.length === 0 ? (
          <Empty art="quiet" title={pastQuery ? `Nothing in the record matches “${pastQuery}”.` : "No past incidents."} />
        ) : (
          <>
            <IncidentRows incidents={past.items} />
            <nav aria-label="Pages of the record" className="flex items-center justify-between text-sm">
              {pastPage > 1 ? (
                <Link className="focusable underline underline-offset-4" href={link(params, { ppage: String(pastPage - 1) }, "#record-section")}>
                  ← Newer
                </Link>
              ) : (
                <span />
              )}
              <span className="text-xs text-[rgb(var(--faint))]">
                Page {pastPage} of {pages.toLocaleString()}
              </span>
              {pastPage < pages ? (
                <Link className="focusable underline underline-offset-4" href={link(params, { ppage: String(pastPage + 1) }, "#record-section")}>
                  Older →
                </Link>
              ) : (
                <span />
              )}
            </nav>
          </>
        )}
      </section>
    </Page>
  );
}

/** The written scenarios, as cards — what a deployment without live feeds shows. */
function Scripted({
  all,
  actions,
  q,
}: {
  all: NonNullable<Awaited<ReturnType<typeof getIncidents>>>;
  actions: Awaited<ReturnType<typeof getActions>>;
  q: ReturnType<typeof parseQuery>;
}) {
  const incidents = applyQuery(all, q);
  const filtered = q.severity !== null || q.status !== null;
  const risk = new Map((actions ?? []).map((a) => [a.id, a.base_risk]));
  return (
    <Page
      title="Incidents"
      description="One incident per failure, not one per alert. Every diagnosis cites the telemetry that supports it."
    >
      <HappeningNow />
      <h2 className="text-xl font-semibold tracking-tight">Investigations</h2>
      {all.length > 0 && (
        <div className="mb-6 space-y-3">
          <FilterRow label="Status">
            <Filter href={hrefFor(q, { status: null })} label="All" active={!q.status} />
            <Filter href={hrefFor(q, { status: "open" })} label="Open" active={q.status === "open"} />
            <Filter href={hrefFor(q, { status: "closed" })} label="Closed" active={q.status === "closed"} />
          </FilterRow>
          <FilterRow label="Severity">
            <Filter href={hrefFor(q, { severity: null })} label="Any" active={!q.severity} />
            {SEVERITIES.map((s) => (
              <Filter key={s} href={hrefFor(q, { severity: s })} label={s} active={q.severity === s} />
            ))}
          </FilterRow>
          <p className="text-xs text-[rgb(var(--faint))]" aria-live="polite">
            Showing {incidents.length} of {all.length}
          </p>
        </div>
      )}
      {all.length > 0 && incidents.length === 0 && filtered ? (
        <Empty art="quiet" title="Nothing matches these filters.">
          <Link className="underline underline-offset-4" href="/incidents">
            Show all
          </Link>
          .
        </Empty>
      ) : incidents.length === 0 ? (
        <Empty art="quiet" title="No incidents." />
      ) : (
        <>
          <Scenarios incidents={all} />
          <TriageList>
            {incidents.map((incident, index) => (
              <TriageItem key={incident.id} index={index} href={`/incidents/${encodeURIComponent(incident.id)}`}>
                <IncidentView incident={incident} risk={risk} linkToDetail />
              </TriageItem>
            ))}
          </TriageList>
        </>
      )}
    </Page>
  );
}
