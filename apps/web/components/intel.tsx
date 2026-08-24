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
  type IntelEntry,
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

export function IntelEntryRow({ entry }: { entry: IntelEntry }) {
  const labels = entry.labels ?? {};
  const advisory = entry.provenance?.url ?? null;
  const title = labels.title || entry.entity_key;
  const identifier = entry.entity_key.split(":").slice(1).join(":");

  return (
    <li className="flex flex-col gap-2 py-4 first:pt-0 last:pb-0">
      <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
        <span className="w-16 shrink-0 text-xs text-[rgb(var(--faint))]">
          <Ago at={entry.occurred_at} />
        </span>
        <VerificationBadge value={labels.verification} />
        <Badge status={statusForSeverity(entry.severity)}>
          {entry.severity ?? "unrated"}
        </Badge>
        <span
          className="text-xs text-[rgb(var(--muted))]"
          title={sourceAbout(entry.source) ?? undefined}
        >
          {sourceName(entry.source)}
        </span>
        {/* Wraps, because the identifier comes from a feed and feeds bring
            whatever the internet contains. This row was laid out against IP
            addresses and held until URLhaus ingested a 56-character random
            subdomain, which pushed the page 100px wide at 375px. `min-w-0` as
            well as `break-all`: a flex item refuses to shrink below its
            content's minimum without it, so breaking alone would not have
            been enough. */}
        {identifier && (
          <span className="mono min-w-0 break-all text-[rgb(var(--astra))]">
            {identifier}
          </span>
        )}
      </div>

      <p className="text-sm font-medium leading-snug">{title}</p>

      {labels.summary && (
        <p className="max-w-3xl text-sm leading-relaxed text-[rgb(var(--muted))]">
          {labels.summary}
        </p>
      )}

      <Facts entry={entry} />

      {advisory ? (
        <a
          href={advisory}
          target="_blank"
          // `noreferrer` as well as `noopener`: this is a link to a security
          // advisory about an attack, and the referrer would tell that site
          // which console is reading about it.
          rel="noopener noreferrer"
          className="focusable mono w-fit rounded text-[11px] text-[rgb(var(--faint))] underline decoration-dotted underline-offset-2 hover:text-[rgb(var(--astra))]"
        >
          read the advisory ↗
        </a>
      ) : (
        <span className="mono text-[11px] text-[rgb(var(--faint))]">
          no advisory link recorded
        </span>
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
function Facts({ entry }: { entry: IntelEntry }) {
  const labels = entry.labels ?? {};
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
