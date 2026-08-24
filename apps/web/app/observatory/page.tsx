import type { Metadata } from "next";
import Link from "next/link";

import { Fresh } from "@/components/fresh";
import { IntelGroupRow, sourceAbout, sourceName } from "@/components/intel";
import { Ago, Empty, Offline, Page, Panel } from "@/components/ui";
import {
  getIntel,
  getIntelStatus,
  type FeedStatus,
  type IntelGroup,
} from "@/lib/api";

export const metadata: Metadata = {
  title: "Observatory",
  description:
    "Real threat intelligence — vulnerabilities CISA has seen exploited, and URLs reported as distributing malware — stored with the link back to the original advisory.",
};

export const dynamic = "force-dynamic";

const LIMIT = 200;
/* The API's ceiling, and it has to be the ceiling rather than a comfortable
   page length.

   URLhaus publishes far more than the other five feeds combined — at 60 it was
   107 of the newest reports, which buried every ransomware claim and every
   disclosed breach below the fold of the fetch itself. The rarer feeds are the
   ones worth reading, and a limit tuned to page length silently decided they
   were not there. Grouping already collapses 200 reports to ~126 rows. */

export default async function ObservatoryPage({
  searchParams,
}: {
  searchParams: Promise<{ source?: string }>;
}) {
  const { source } = await searchParams;

  const [intel, status] = await Promise.all([
    getIntel(LIMIT, source),
    getIntelStatus(),
  ]);

  // `null` from an unreachable API and `null` from an unknown source parameter
  // are the same value, so the pair is disambiguated by asking a second, cheap
  // question rather than telling a visitor the system is down when they mistyped.
  if (intel === null) {
    if (status === null) return <Offline />;
    return (
      <Page title="Observatory" description="Recent threat intelligence, as stored.">
        <Panel title="Unknown source">
          <Empty art="ledger" title={`No feed named "${source}".`}>
            Known feeds: {Object.keys(status.feeds).join(", ")}.{" "}
            <Link href="/observatory" className="underline decoration-dotted">
              Show everything
            </Link>
            .
          </Empty>
        </Panel>
      </Page>
    );
  }

  // Split by whether the thing is still up, because that is the difference
  // between "block this" and "note that this happened". The status came back
  // from abuse.ch on every report and was spent on nothing but a severity
  // colour.
  //
  // The timeline stays on the live half. A day-by-day reading of infrastructure
  // that has already gone offline is a chronology of things that no longer
  // matter; one collapsed section says the same and takes a line.
  // `active === false` only. `null` means the publisher does not report
  // liveness — a ransomware claim is neither up nor gone — and treating absent
  // as offline swept four of the six feeds into the collapsed panel.
  const offline = intel.groups.filter((entry) => entry.active === false);
  const active = intel.groups.filter((entry) => entry.active !== false);
  const days = groupByDay(active);

  // The newest thing on the page, as the watermark for "since you last looked".
  // Taken from the entries actually rendered rather than from the sync time: a
  // poll that found nothing is still a poll, and it must not mark everything
  // already on screen as new.
  const newest = intel.groups.reduce<string | null>(
    (latest, entry) => (latest === null || entry.last_at > latest ? entry.last_at : latest),
    null,
  );

  return (
    <Page
      title="Observatory"
      description="What the wider world is reporting — polled hourly, stored here, and always linked back to whoever said it."
    >
      <Panel
        title="Feeds"
        aside={
          status?.durable === false ? (
            <span className="text-[rgb(var(--warn))]">not stored durably</span>
          ) : (
            <span className="flex flex-wrap items-center gap-x-3 gap-y-1">
              <span>
                {intel.count} indicators · {intel.reports} reports
              </span>
              <SyncedAt at={status?.synced_at ?? null} />
            </span>
          )
        }
      >
        <div className="flex flex-wrap gap-2">
          <Filter href="/observatory" label="Everything" active={!source} />
          {intel.sources.map((name) => (
            <Filter
              key={name}
              href={`/observatory?source=${encodeURIComponent(name)}`}
              label={sourceName(name)}
              active={source === name}
            />
          ))}
        </div>

        {/* Per feed: when it last answered, and whether that was too long ago.
            A feed that has quietly stopped looks exactly like a quiet one, and
            on a page whose whole claim is freshness that is the failure worth
            surfacing.

            "Answered" and "had something new" are printed as separate facts.
            Collapsing them is what made a healthy feed with nothing to report
            read as broken. */}
        {status && (
          <dl className="mt-4 grid gap-x-6 gap-y-2 border-t border-[rgb(var(--edge))] pt-4 text-xs sm:grid-cols-2">
            {Object.entries(status.feeds).map(([name, feed]) => (
              <div key={name} className="flex min-w-0 flex-wrap items-baseline gap-x-2">
                <dt className="text-[rgb(var(--muted))]">{sourceName(name)}</dt>
                <dd className="min-w-0 flex-1">
                  <FeedAge feed={feed} hours={status.stale_after_hours} />
                </dd>
                <dd className="w-full text-[rgb(var(--faint))] sm:w-auto">
                  {sourceAbout(name)}
                </dd>
              </div>
            ))}
          </dl>
        )}
      </Panel>

      <Fresh newest={newest} />

      {days.length === 0 && offline.length === 0 ? (
        <Panel title="Nothing yet">
          <Empty art="ledger" title="No intelligence has been ingested.">
            The feeds are polled hourly. Nothing here is generated — if this is
            empty, the poll has not run or every entry was already stored.
          </Empty>
        </Panel>
      ) : (
        days.map(([day, entries]) => (
          <Panel
            key={day}
            title={dayLabel(day)}
            aside={`${entries.length} ${entries.length === 1 ? "entry" : "entries"}`}
          >
            <ol className="divide-y divide-[rgb(var(--edge))]">
              {entries.map((entry) => (
                <IntelGroupRow key={entry.entity_key} group={entry} />
              ))}
            </ol>
          </Panel>
        ))
      )}

      {offline.length > 0 && (
        <Panel
          title="Gone offline"
          aside={`${offline.length} ${offline.length === 1 ? "indicator" : "indicators"}`}
        >
          <p className="mb-3 text-sm text-[rgb(var(--muted))]">
            Last reported as no longer serving. Kept because an address that
            went quiet is not an address that was never used — it is worth
            recognising if it comes back.
          </p>
          <details>
            <summary className="focusable inline-block cursor-pointer rounded text-xs text-[rgb(var(--faint))] hover:text-[rgb(var(--ink))]">
              show them
            </summary>
            <ol className="mt-2 divide-y divide-[rgb(var(--edge))]">
              {offline.map((entry) => (
                <IntelGroupRow key={entry.entity_key} group={entry} />
              ))}
            </ol>
          </details>
        </Panel>
      )}

      <p className="text-xs text-[rgb(var(--faint))]">
        Newest {LIMIT} reports, collapsed to one row per indicator, oldest last. Nothing on this page is a finding
        about this estate — it is what other people are publishing, kept so a
        claim can be checked against its source rather than believed.
      </p>
    </Page>
  );
}

function Filter({
  href,
  label,
  active,
}: {
  href: string;
  label: string;
  active: boolean;
}) {
  return (
    <Link
      href={href}
      aria-current={active ? "page" : undefined}
      className={`focusable rounded-full border px-3 py-1.5 text-xs transition ${
        active
          ? "border-[rgb(var(--edge-strong))] bg-[rgb(var(--raised))] text-[rgb(var(--ink))]"
          : "border-[rgb(var(--edge))] text-[rgb(var(--muted))] hover:bg-[rgb(var(--raised))] hover:text-[rgb(var(--ink))]"
      }`}
    >
      {label}
    </Link>
  );
}

/**
 * A timeline needs days, not a flat list of sixty rows.
 *
 * Grouped on the calendar day the source published, not the day this system
 * noticed — those differ by up to an hour of polling, and a reader comparing
 * this against a vendor bulletin is looking at the publisher's date.
 */
function groupByDay(entries: IntelGroup[]): [string, IntelGroup[]][] {
  const days = new Map<string, IntelGroup[]>();
  for (const entry of entries) {
    // The day of the most recent report. A group whose activity spans midnight
    // belongs to the day it was last seen, which is the day a reader is asking
    // about.
    const day = entry.last_at.slice(0, 10);
    const bucket = days.get(day);
    if (bucket) bucket.push(entry);
    else days.set(day, [entry]);
  }
  return [...days.entries()].sort(([a], [b]) => (a < b ? 1 : -1));
}

function dayLabel(day: string): string {
  const today = new Date().toISOString().slice(0, 10);
  if (day === today) return "Today";
  const yesterday = new Date(Date.now() - 86_400_000).toISOString().slice(0, 10);
  if (day === yesterday) return "Yesterday";
  return day;
}


/**
 * `last synced 14m ago`, from the poll's own timestamp.
 *
 * R61's requirement, and the reason it is stated that way: a page that derives
 * freshness from its own load time says "synced just now" on every render,
 * including the renders that happen while the feed is broken. The anchor has to
 * be the record, so `Ago` is given the stored ISO stamp and computes elapsed
 * from it.
 */
function SyncedAt({ at }: { at: string | null }) {
  if (!at) {
    return (
      <span className="text-[rgb(var(--faint))]">no successful poll recorded</span>
    );
  }
  return (
    <span className="text-[rgb(var(--faint))]">
      last synced <Ago at={at} />
    </span>
  );
}

/**
 * One feed's freshness, in the three states it can actually be in.
 *
 * Never polled is not stale. A deployment that has not run its first ingest is
 * not broken, and colouring it as a fault would cry wolf on every fresh start —
 * which is the sort of always-on warning that trains a reader to ignore the
 * one that matters.
 */
function FeedAge({
  feed,
  hours,
}: {
  feed: FeedStatus;
  hours: number;
}) {
  if (!feed.synced_at) {
    return <span className="text-[rgb(var(--faint))]">has not polled yet</span>;
  }
  if (feed.stale || feed.ok === false) {
    return (
      <span className="text-[rgb(var(--warn))]">
        <span aria-hidden="true">◆</span> last answered <Ago at={feed.synced_at} />
        {feed.error ? ` — ${feed.error.slice(0, 80)}` : ` — over ${hours}h ago`}
      </span>
    );
  }
  return (
    <span className="text-[rgb(var(--faint))]">
      answered <Ago at={feed.synced_at} />
      {feed.cursor ? "" : ", nothing new yet"}
    </span>
  );
}
