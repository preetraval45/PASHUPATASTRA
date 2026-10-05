import type { Metadata } from "next";
import Link from "next/link";

import { Cite } from "@/components/cite";
import { Offline, Page, Panel, Stat } from "@/components/ui";
import { getImpact, type Figure } from "@/lib/api";

export const metadata: Metadata = {
  title: "Impact",
  description:
    "What this project has done, counted from the things that did it — feeds ingested, incidents, agent turns, page renders, uptime, and a timeline generated from git.",
};

export const dynamic = "force-dynamic";

/**
 * The numbers, and where each came from (R107).
 *
 * The rule the page is built on: every figure is a recount of something that
 * exists for another reason — the feed store, the audit ledger, the warm
 * task's heartbeat, git — and nothing is incremented by this page and kept on
 * its own. `scripts/verifyimpact.py` reads the same sources and compares,
 * which is the only thing that makes a page of numbers about a project worth
 * reading: it is meant for people whose job is to doubt it.
 *
 * A figure that could not be measured renders as **absent, with the reason**,
 * never as zero. Zero is a measurement — "no one has starred it" and "GitHub
 * did not answer" are different facts, and a page that showed both as 0 would
 * be the invented metric this whole project is arranged against.
 */
export default async function ImpactPage() {
  const impact = await getImpact();
  if (impact === null) return <Offline />;

  const intel = impact.intelligence.value;
  const ledger = impact.ledger.value;
  const views = impact.views.value;
  const repo = impact.repository.value;
  const uptime = impact.uptime.value;
  const milestones = impact.milestones.value ?? [];

  return (
    <Page
      title="Impact"
      description="What this has done, counted from the things that did it."
      actions={
        <p className="text-xs text-[rgb(var(--faint))]">
          as of {new Date(impact.as_of).toISOString().slice(0, 16).replace("T", " ")} UTC
        </p>
      }
    >
      <section className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Stat
          label="Indicators ingested"
          value={intel ? intel.indicators.toLocaleString() : "—"}
          hint={intel ? `${intel.reports.toLocaleString()} reports, ${intel.feeds} feeds` : impact.intelligence.absent}
        />
        <Stat
          label="Incidents"
          value={String(impact.incidents.value ?? "—")}
          hint={impact.incidents.from}
        />
        <Stat
          label="Audit records"
          value={ledger ? ledger.records.toLocaleString() : "—"}
          hint={ledger ? `${ledger.agent_turns} agent turns` : impact.ledger.absent}
        />
        <Stat
          label="Page renders"
          value={views ? views.total.toLocaleString() : "—"}
          hint={views ? `over ${views.days} day${views.days === 1 ? "" : "s"}` : impact.views.absent}
        />
      </section>

      <Panel title="Where each number comes from" aside="and what it is not">
        <dl className="space-y-3 text-sm">
          <Figures
            rows={[
              ["Indicators and reports", impact.intelligence],
              ["Audit ledger", impact.ledger],
              ["Page renders", impact.views],
              ["Uptime", impact.uptime],
              ["Repository", impact.repository],
              ["Milestones", impact.milestones],
            ]}
          />
        </dl>
        <p className="mt-4 text-xs leading-relaxed text-[rgb(var(--faint))]">{impact.note}</p>
      </Panel>

      {repo && (
        <Panel title="Repository" aside="from the GitHub API, cached hourly">
          <dl className="grid grid-cols-2 gap-4 sm:grid-cols-4">
            {(
              [
                ["stars", repo.stars],
                ["forks", repo.forks],
                ["watchers", repo.watchers],
                ["open issues", repo.open_issues],
              ] as const
            ).map(([label, value]) => (
              <div key={label}>
                <dt className="label">{label}</dt>
                <dd className="tnum mt-1 text-2xl">{value}</dd>
              </div>
            ))}
          </dl>
        </Panel>
      )}

      {uptime && (
        <Panel title="Uptime" aside={`${uptime.beats} of ${uptime.expected} expected beats`}>
          <p className="text-sm leading-relaxed text-[rgb(var(--muted))]">
            The warm task answers every five minutes and leaves a count for the day. A day with
            every beat is a day the API answered all day; fewer is time it did not.{" "}
            <span className="tnum text-[rgb(var(--ink))]">
              {uptime.share === null ? "—" : `${Math.round(uptime.share * 100)}%`}
            </span>{" "}
            across {uptime.days} day{uptime.days === 1 ? "" : "s"}.
          </p>
        </Panel>
      )}

      <Panel
        title="Milestones"
        aside={`${milestones.length} generated from git`}
      >
        {milestones.length === 0 ? (
          <p className="text-sm text-[rgb(var(--faint))]">{impact.milestones.absent}</p>
        ) : (
          <ol className="space-y-1.5 text-sm">
            {[...milestones].reverse().slice(0, 25).map((milestone) => (
              <li key={milestone.sha} className="flex flex-wrap items-baseline gap-x-3">
                <span className="mono shrink-0 text-xs text-[rgb(var(--faint))]">
                  {milestone.at.slice(0, 10)}
                </span>
                <span className="mono shrink-0 text-xs text-[rgb(var(--astra))]">
                  {milestone.tasks.join(", ")}
                </span>
                <span className="min-w-0 break-words">{milestone.title}</span>
              </li>
            ))}
          </ol>
        )}
        <p className="mt-3 text-xs text-[rgb(var(--faint))]">
          Each entry is a commit that exists, dated by the commit. Generated rather than written,
          so this cannot list a milestone that did not land.
        </p>
      </Panel>

      <Panel title="Cite this work" aside="from CITATION.cff">
        <Cite />
      </Panel>

      <p className="text-xs leading-relaxed text-[rgb(var(--faint))]">
        Page renders are counted on the server that rendered them — no cookie, no beacon in your
        browser, and no identifier per person. Unique visitors would need one, and this site
        deliberately does not mint one (see{" "}
        <Link href="/how-it-works" className="focusable rounded underline decoration-dotted">
          how it works
        </Link>
        ). Nothing authenticates the count either: somebody determined could inflate it, which is
        worth saying rather than presenting the number as audited.
      </p>
    </Page>
  );
}

/** Each figure's provenance, or the reason it could not be measured. */
function Figures({ rows }: { rows: [string, Figure<unknown>][] }) {
  return (
    <>
      {rows.map(([label, figure]) => (
        <div key={label} className="flex min-w-0 flex-wrap gap-x-3">
          <dt className="shrink-0 text-[rgb(var(--ink))]">{label}</dt>
          <dd className="min-w-0 break-words text-[rgb(var(--muted))]">
            {figure.absent ? (
              <span className="text-[rgb(var(--warn))]">absent — {figure.absent}</span>
            ) : (
              figure.from
            )}
          </dd>
        </div>
      ))}
    </>
  );
}
