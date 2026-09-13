import type { Metadata } from "next";
import Link from "next/link";

import { Badge, Ident, Offline, Page, Panel } from "@/components/ui";
import { getDetections, type DetectionSummary } from "@/lib/api";

export const metadata: Metadata = {
  title: "Detections",
  description:
    "Every detection rule the console holds — drafted by the assistant from an incident's telemetry, or written by a person — each tied to the incidents it came from.",
};

export const dynamic = "force-dynamic";

/**
 * The detections library (R77).
 *
 * Two kinds of rule, and the page's one job is to keep them apart. A drafted
 * rule is a claim about what stored telemetry held — checkable, and usually
 * so narrow it catches one incident. A written rule is a claim about what an
 * analyst believes the technique looks like — general, and not checkable
 * against any record here. Shown in one style, the second borrows the
 * first's standing; so the kind is read from `author.kind`, never inferred
 * from a title, and it decides the border, the marker and the badge.
 *
 * Grouped by incident, because that is what the task asks a rule to name and
 * what a reader arrives wanting: "what would have caught this?"
 */
export default async function DetectionsPage() {
  const library = await getDetections();
  if (library === null) return <Offline />;

  const byIncident = new Map<string, DetectionSummary[]>();
  for (const rule of library.rules) {
    for (const incident of rule.incidents) {
      byIncident.set(incident, [...(byIncident.get(incident) ?? []), rule]);
    }
  }

  return (
    <Page
      title="Detections"
      description="What would have caught each incident — drafted from its telemetry, or written by a person."
      actions={
        <p className="text-xs text-[rgb(var(--faint))]">
          <span className="tnum">{library.drafted}</span> drafted ·{" "}
          <span className="tnum">{library.written}</span> written
        </p>
      }
    >
      <Panel title="How to read this" aside="two kinds, kept apart">
        <ul className="space-y-2 text-sm text-[rgb(var(--muted))]">
          <li className="flex items-start gap-2">
            <Marker kind="agent" />
            <span>
              <strong className="text-[rgb(var(--ink))]">Drafted</strong> — assembled by the
              assistant from the stored events one step of an incident cites. Every field was
              read from a record, which is why most of these catch that incident and nothing
              else; the rule says so in its own header.
            </span>
          </li>
          <li className="flex items-start gap-2">
            <Marker kind="human" />
            <span>
              <strong className="text-[rgb(var(--ink))]">Written</strong> — by a named person,
              for the fields a real sensor would send. General, and not checked against any
              record here: it is what someone believes the technique looks like.
            </span>
          </li>
        </ul>
      </Panel>

      {[...byIncident.entries()].map(([incident, rules]) => (
        <Panel
          key={incident}
          title={incident}
          aside={
            <Link
              href={`/incidents/${encodeURIComponent(incident)}`}
              className="focusable rounded underline decoration-dotted underline-offset-2 hover:text-[rgb(var(--ink))]"
            >
              the incident →
            </Link>
          }
        >
          <ul data-detections={incident} className="space-y-3">
            {rules.map((rule) => (
              <Rule key={`${incident}-${rule.rule_id}`} rule={rule} />
            ))}
          </ul>
        </Panel>
      ))}
    </Page>
  );
}

/** The glyph that tells the two apart without colour: a dashed square for a
 *  draft, a filled one for a person's rule. */
function Marker({ kind }: { kind: "agent" | "human" }) {
  return (
    <span
      aria-hidden="true"
      className={`mt-1 inline-block h-3 w-3 shrink-0 rounded-sm border ${
        kind === "human"
          ? "border-[rgb(var(--gold))] bg-[rgb(var(--gold))]"
          : "border-dashed border-[rgb(var(--astra))]"
      }`}
    />
  );
}

function Rule({ rule }: { rule: DetectionSummary }) {
  const human = rule.author.kind === "human";
  const href = human
    ? `/detections/${encodeURIComponent(rule.rule_id)}`
    : `/incidents/${encodeURIComponent(rule.incidents[0])}`;
  return (
    <li
      data-rule={rule.rule_id}
      data-author-kind={rule.author.kind}
      className={`flex min-w-0 items-start gap-3 rounded-lg border p-3 ${
        human ? "border-[rgb(var(--gold))]/60" : "border-dashed border-[rgb(var(--edge))]"
      }`}
    >
      <Marker kind={rule.author.kind} />
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-baseline gap-x-2 gap-y-1">
          <Link
            href={href}
            className="focusable rounded text-sm font-medium underline decoration-dotted underline-offset-2 hover:text-[rgb(var(--astra))]"
          >
            {rule.title}
          </Link>
          {rule.technique && (
            <span className="mono text-xs text-[rgb(var(--faint))]">
              {rule.technique.id}
              {rule.technique.name && ` ${rule.technique.name}`}
            </span>
          )}
        </div>
        <p className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs">
          {/* The author line is the whole point. `human:` prefix and gold,
              the way the audit trail marks a person's decision; `sati` in the
              agent's colour, the way its turns are marked. */}
          <span
            data-author
            className={`mono ${human ? "text-[rgb(var(--gold))]" : "text-[rgb(var(--astra))]"}`}
          >
            {human ? `written by ${rule.author.name}` : `drafted by ${rule.author.name}`}
          </span>
          <Badge status={human ? "warning" : "neutral"}>{human ? "written" : "drafted"}</Badge>
          {!rule.behavioural && <Badge status="neutral">indicator match</Badge>}
          {!rule.valid && <Badge status="critical">does not parse</Badge>}
          <span className="text-[rgb(var(--faint))]">
            {rule.incidents.map((id, index) => (
              <span key={id}>
                {index > 0 && ", "}
                <Ident>{id}</Ident>
              </span>
            ))}
          </span>
        </p>
      </div>
    </li>
  );
}
