/**
 * Threat intelligence, rendered in the same language as incidents.
 *
 * The one rule this file exists to keep: **a report is never labelled
 * confirmed.** By the time a community submission and a CISA advisory are both
 * cards on a page they look identical, and the difference between "somebody
 * uploaded this an hour ago" and "an authority has observed this being
 * exploited" is the entire value of having the second one.
 *
 * So the vocabulary is a closed union with a `Record` over it. A fourth state
 * added to the API without a decision about how it should look stops the build
 * rather than rendering as a blank badge that a reader fills in optimistically.
 */

import {
  isVerification,
  type IntelGroup,
  type Verification,
} from "@/lib/api";
import { Ago, Badge, statusForSeverity, type Status } from "@/components/ui";

/**
 * What each state looks like and, more importantly, what it means.
 *
 * `reported` is deliberately not `ok`. Green on an unverified malware report
 * would read as "checked and fine", which is the opposite of what it says.
 * Neutral is the honest colour for a claim nobody has stood behind.
 */
const VERIFICATION: Record<
  Verification,
  { label: string; status: Status; means: string }
> = {
  reported: {
    label: "reported",
    status: "neutral",
    means:
      "Submitted by someone. Neither the publisher nor this system has verified it.",
  },
  corroborated: {
    label: "corroborated",
    status: "warning",
    means: "More than one independent source, or the publisher reviews before listing.",
  },
  confirmed: {
    label: "confirmed",
    status: "critical",
    means: "An authority states it as fact — CISA lists it as exploited in the wild.",
  },
};

/** Where each feed's entries come from, in words a reader can weigh. */
const SOURCE: Record<string, { name: string; about: string }> = {
  "cisa-kev": {
    name: "CISA KEV",
    about: "Vulnerabilities CISA has observed being exploited in the wild",
  },
  urlhaus: {
    name: "URLhaus",
    about: "URLs submitted to abuse.ch as distributing malware",
  },
};

export function sourceName(source: string): string {
  return SOURCE[source]?.name ?? source;
}

export function sourceAbout(source: string): string | null {
  return SOURCE[source]?.about ?? null;
}

export function VerificationBadge({ value }: { value: unknown }) {
  // An unknown value is shown as unknown rather than guessed at. Falling back
  // to the friendliest state is how "unverified" quietly becomes "fine".
  if (!isVerification(value)) {
    return <Badge status="neutral">unverified</Badge>;
  }
  const state = VERIFICATION[value];
  return (
    <span title={state.means}>
      <Badge status={state.status}>{state.label}</Badge>
    </span>
  );
}

export function IntelGroupRow({ group }: { group: IntelGroup }) {
  const advisory = group.provenance?.url ?? null;
  const identifier = group.entity_key.split(":").slice(1).join(":");
  const repeated = group.reports > 1;

  return (
    <li className="flex flex-col gap-2 py-4 first:pt-0 last:pb-0">
      <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
        <span className="w-16 shrink-0 text-xs text-[rgb(var(--faint))]">
          <Ago at={group.last_at} />
        </span>
        <VerificationBadge value={group.verification} />
        <Badge status={statusForSeverity(group.severity)}>
          {group.severity ?? "unrated"}
        </Badge>
        <span
          className="text-xs text-[rgb(var(--muted))]"
          title={sourceAbout(group.source) ?? undefined}
        >
          {sourceName(group.source)}
        </span>
        {/* Wraps, because the identifier comes from a feed and feeds bring
            whatever the internet contains — a 56-character random subdomain
            took this page 100px wide at 375px. `min-w-0` as well as
            `break-all`: a flex item refuses to shrink below its content's
            minimum contribution without it. */}
        {identifier && (
          <span className="mono min-w-0 break-all text-[rgb(var(--astra))]">
            {identifier}
          </span>
        )}
      </div>

      <p className="text-sm font-medium leading-snug">{group.title}</p>

      {group.summary && (
        <p className="max-w-3xl text-sm leading-relaxed text-[rgb(var(--muted))]">
          {group.summary}
        </p>
      )}

      <Facts labels={group.labels} />

      <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-[11px]">
        {/* The count is the thing the page could not say before. Forty-three
            near-identical cards stated it by taking up the screen; one line
            states it and leaves room for the other hundred and seven
            indicators. */}
        {repeated && (
          <span className="text-[rgb(var(--muted))]">
            reported{" "}
            <span className="text-[rgb(var(--ink))]">
              {group.reports_in_window}×
            </span>{" "}
            {group.reports_in_window === group.reports
              ? `in the last ${group.window_hours}h`
              : `in ${group.window_hours}h, ${group.reports} in total`}
          </span>
        )}
        {advisory ? (
          <a
            href={advisory}
            target="_blank"
            rel="noopener noreferrer"
            className="focusable mono rounded text-[rgb(var(--faint))] underline decoration-dotted underline-offset-2 hover:text-[rgb(var(--astra))]"
          >
            read the advisory ↗
          </a>
        ) : (
          <span className="mono text-[rgb(var(--faint))]">
            no advisory link recorded
          </span>
        )}
      </div>

      {/* Every individual report, one click away. Collapsing the display is
          only defensible if nothing is lost by it. */}
      {repeated && (
        <details className="mt-1">
          <summary className="focusable inline-block cursor-pointer rounded text-[11px] text-[rgb(var(--faint))] hover:text-[rgb(var(--ink))]">
            all {group.reports} reports
          </summary>
          <ol className="mt-2 space-y-1 border-l border-[rgb(var(--edge))] pl-3">
            {group.history.map((report) => (
              <li
                key={report.id}
                className="flex flex-wrap items-baseline gap-x-3 text-[11px]"
              >
                <span className="mono text-[rgb(var(--faint))]">
                  {report.at.slice(0, 16).replace("T", " ")}
                </span>
                {report.status && (
                  <span
                    className={
                      report.status === "online"
                        ? "text-[rgb(var(--warn))]"
                        : "text-[rgb(var(--faint))]"
                    }
                  >
                    {report.status}
                  </span>
                )}
                {report.tags && (
                  <span className="min-w-0 break-all text-[rgb(var(--muted))]">
                    {report.tags}
                  </span>
                )}
                {report.url && (
                  <a
                    href={report.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="focusable mono rounded text-[rgb(var(--faint))] underline decoration-dotted underline-offset-2 hover:text-[rgb(var(--astra))]"
                  >
                    ↗
                  </a>
                )}
              </li>
            ))}
          </ol>
        </details>
      )}
    </li>
  );
}


/**
 * The two or three facts that change what a reader does about an entry.
 *
 * Different per source, because they are: a KEV entry has a remediation
 * deadline and may be tied to ransomware, and a URLhaus entry has neither and
 * has a liveness instead. Rendering one shape for both would mean either empty
 * columns or facts left out of whichever source lost the argument.
 */
function Facts({ labels }: { labels: Record<string, string> }) {
  const facts: { key: string; value: string; warn?: boolean }[] = [];

  if (labels.ransomware === "known") {
    facts.push({ key: "ransomware", value: "known campaign use", warn: true });
  }
  if (labels.due_date) {
    facts.push({ key: "federal due date", value: labels.due_date });
  }
  if (labels.status) {
    facts.push({ key: "url", value: labels.status, warn: labels.status === "online" });
  }
  if (labels.tags) {
    facts.push({ key: "tags", value: labels.tags });
  }
  if (labels.required_action) {
    facts.push({ key: "required action", value: labels.required_action });
  }

  if (!facts.length) return null;

  return (
    <dl className="flex flex-wrap gap-x-5 gap-y-1 text-[11px]">
      {facts.map((fact) => (
        <div key={fact.key} className="flex gap-1.5">
          <dt className="text-[rgb(var(--faint))]">{fact.key}</dt>
          <dd
            className={
              fact.warn ? "text-[rgb(var(--warn))]" : "text-[rgb(var(--muted))]"
            }
          >
            {fact.value}
          </dd>
        </div>
      ))}
    </dl>
  );
}
