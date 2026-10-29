import type { Metadata } from "next";
import type { ReactNode } from "react";

import { Breakdown, DayColumns, type Slice } from "@/components/analytics";
import { Badge, Page, Panel } from "@/components/ui";
import world from "@/lib/world.generated.json";

export const metadata: Metadata = {
  title: "World threat landscape",
  description:
    "Exploited vulnerabilities, ransomware activity, botnet command-and-control and data breaches worldwide — a daily snapshot from public sources.",
};

type Bucket = { label: string; value: number };
type Source<T> = ({ ok: true; source: string } & T) | { ok: false; absent: string };

type World = {
  as_of: string | null;
  kev: Source<{
    total: number;
    added_last_30_days: number;
    known_ransomware_use: number;
    catalog_version?: string;
    by_month: Bucket[];
    top_vendors: Bucket[];
    latest: { cve: string; vendor: string; product: string; name: string; added: string; ransomware: boolean }[];
  }>;
  ransomware: Source<{ victims: number; by_day: Bucket[]; by_group: Bucket[]; by_country: Bucket[]; by_sector: Bucket[] }>;
  c2: Source<{ c2_servers: number; online: number; by_malware: Bucket[]; by_country: Bucket[] }>;
  breaches: Source<{
    breaches: number;
    accounts: number;
    top_data_classes: Bucket[];
    latest: { title: string; domain: string; breach_date: string; added: string; accounts: number; verified: boolean }[];
  }>;
};

const W = world as unknown as World;

const slices = (rows: Bucket[]): Slice[] => rows.map((r) => ({ label: r.label, value: r.value }));
const compact = (n: number) =>
  n >= 1e9 ? `${(n / 1e9).toFixed(1)}B` : n >= 1e6 ? `${(n / 1e6).toFixed(1)}M` : n >= 1e3 ? `${(n / 1e3).toFixed(1)}k` : String(n);

/**
 * The world's threat landscape, from public sources, refreshed daily by a
 * GitHub Action (`scripts/worldsnapshot.py`). A source that failed on the last
 * run says so in place of its chart. Victim names are not shown — only counts
 * by group, country and sector.
 */
export default function WorldPage() {
  const { kev, ransomware, c2, breaches } = W;
  return (
    <Page
      title="World threat landscape"
      description="What attackers are doing worldwide right now: vulnerabilities being exploited, ransomware groups' activity, live botnet command-and-control, and data breaches. A daily snapshot from public sources — hover any chart for exact values."
    >
      <p className="-mt-4 text-xs text-[rgb(var(--faint))]">
        {W.as_of ? `Snapshot taken ${new Date(W.as_of).toUTCString()}` : "The first daily snapshot has not run yet."}
      </p>

      <section className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <Kpi label="Exploited vulnerabilities (CISA KEV)" value={kev.ok ? compact(kev.total) : "—"} hint={kev.ok ? `${kev.added_last_30_days} added in the last 30 days` : "source unavailable"} />
        <Kpi label="Ransomware victims posted, recent" value={ransomware.ok ? compact(ransomware.victims) : "—"} hint={ransomware.ok ? "from leak-site monitoring" : "source unavailable"} />
        <Kpi label="Botnet C2 servers tracked" value={c2.ok ? compact(c2.c2_servers) : "—"} hint={c2.ok ? `${c2.online} online now` : "source unavailable"} />
        <Kpi label="Breached accounts on record" value={breaches.ok ? compact(breaches.accounts) : "—"} hint={breaches.ok ? `across ${breaches.breaches} breaches` : "source unavailable"} />
      </section>

      <div className="grid gap-6 lg:grid-cols-2">
        <Panel title="New exploited vulnerabilities per month" aside="CISA KEV · last 12 months">
          {kev.ok ? <DayColumns days={kev.by_month.map((b) => ({ day: b.label, value: b.value }))} unit="added to KEV" bucket="month" height={300} /> : <Missing absent={kev.absent} />}
        </Panel>
        <Panel title="Most-exploited vendors" aside="all of KEV">
          {kev.ok ? <Breakdown slices={slices(kev.top_vendors)} /> : <Missing absent={kev.absent} />}
        </Panel>
        <Panel title="Ransomware posts per day" aside="ransomware.live">
          {ransomware.ok ? <DayColumns days={ransomware.by_day.map((b) => ({ day: b.label, value: b.value }))} unit="victims posted" height={260} /> : <Missing absent={ransomware.absent} />}
        </Panel>
        <Panel title="Most active ransomware groups" aside="recent posts">
          {ransomware.ok ? <Breakdown slices={slices(ransomware.by_group)} /> : <Missing absent={ransomware.absent} />}
        </Panel>
        <Panel title="Ransomware victims by country">
          {ransomware.ok ? <Breakdown slices={slices(ransomware.by_country)} /> : <Missing absent={ransomware.absent} />}
        </Panel>
        <Panel title="Ransomware victims by sector">
          {ransomware.ok ? <Breakdown slices={slices(ransomware.by_sector)} /> : <Missing absent={ransomware.absent} />}
        </Panel>
        <Panel title="Botnet C2 by malware family" aside="abuse.ch Feodo Tracker">
          {c2.ok ? <Breakdown slices={slices(c2.by_malware)} /> : <Missing absent={c2.absent} />}
        </Panel>
        <Panel title="Botnet C2 by hosting country">
          {c2.ok ? <Breakdown slices={slices(c2.by_country)} /> : <Missing absent={c2.absent} />}
        </Panel>
      </div>

      <Panel title="Latest vulnerabilities added to KEV" aside="patch these first">
        {kev.ok ? (
          <Table
            head={["CVE", "Vendor · product", "Vulnerability", "Added", ""]}
            rows={kev.latest.map((v) => [
              <a key="c" href={`https://nvd.nist.gov/vuln/detail/${v.cve}`} target="_blank" rel="noopener noreferrer" className="mono text-xs text-[rgb(var(--astra))] hover:underline">{v.cve}</a>,
              <span key="v" className="text-xs">{v.vendor} · {v.product}</span>,
              <span key="n" className="text-xs text-[rgb(var(--muted))]">{v.name}</span>,
              <span key="a" className="tnum text-xs">{v.added}</span>,
              v.ransomware ? <Badge key="r" status="high">used by ransomware</Badge> : <span key="r" />,
            ])}
          />
        ) : (
          <Missing absent={kev.absent} />
        )}
      </Panel>

      <div className="grid gap-6 lg:grid-cols-2">
        <Panel title="Latest data breaches" aside="Have I Been Pwned">
          {breaches.ok ? (
            <Table
              head={["Breach", "Accounts", "Breached", ""]}
              rows={breaches.latest.map((b) => [
                <span key="t" className="text-xs">{b.title}</span>,
                <span key="n" className="tnum text-xs">{b.accounts.toLocaleString()}</span>,
                <span key="d" className="tnum text-xs">{b.breach_date}</span>,
                b.verified ? <Badge key="v" status="ok">verified</Badge> : <Badge key="v" status="neutral">unverified</Badge>,
              ])}
            />
          ) : (
            <Missing absent={breaches.absent} />
          )}
        </Panel>
        <Panel title="What breaches expose" aside="data types, across all breaches">
          {breaches.ok ? <Breakdown slices={slices(breaches.top_data_classes)} /> : <Missing absent={breaches.absent} />}
        </Panel>
      </div>

      <p className="text-xs leading-relaxed text-[rgb(var(--faint))]">
        Sources: CISA Known Exploited Vulnerabilities, ransomware.live, abuse.ch Feodo Tracker, Have I Been
        Pwned. Refreshed daily on GitHub&rsquo;s runners. Victim names and raw indicators are deliberately not
        shown — this page is for seeing the landscape, not for repeating what criminals publish.
      </p>
    </Page>
  );
}

function Kpi({ label, value, hint }: { label: string; value: string; hint: string }) {
  return (
    <div className="rounded-xl border border-[rgb(var(--edge))] bg-[rgb(var(--panel))] p-4">
      <p className="label">{label}</p>
      <p className="tnum mt-1 text-3xl font-semibold tracking-tight">{value}</p>
      <p className="mt-0.5 text-xs text-[rgb(var(--faint))]">{hint}</p>
    </div>
  );
}

function Missing({ absent }: { absent: string }) {
  return (
    <p className="rounded-lg border border-dashed border-[rgb(var(--edge))] px-4 py-6 text-center text-sm text-[rgb(var(--faint))]">
      Not available: {absent}.
    </p>
  );
}

function Table({ head, rows }: { head: string[]; rows: ReactNode[][] }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="text-left text-xs text-[rgb(var(--faint))]">
            {head.map((h, i) => (
              <th key={i} className="py-2 pr-3 font-normal">{h}</th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-[rgb(var(--edge))]">
          {rows.map((row, i) => (
            <tr key={i}>
              {row.map((cell, j) => (
                <td key={j} className="py-2 pr-3 align-top">{cell}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
