import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";

import { Badge, Ident, Offline, Page, Panel } from "@/components/ui";
import { apiIsReachable, getDetection } from "@/lib/api";

export const dynamic = "force-dynamic";

export async function generateMetadata({
  params,
}: {
  params: Promise<{ id: string }>;
}): Promise<Metadata> {
  const rule = await getDetection(decodeURIComponent((await params).id));
  return { title: rule?.title ?? "Detection", description: rule ? `Written by ${rule.author.name}.` : undefined };
}

/**
 * One hand-written rule, in full (R77). Drafted rules have no page of their
 * own — they are served under the incident they were assembled from, with the
 * mapping table that makes them checkable. A written rule has no such table,
 * and this page does not pretend to one: it shows the author, the incidents it
 * was written against, the reviewer's notes, and the document.
 */
export default async function DetectionPage({ params }: { params: Promise<{ id: string }> }) {
  const id = decodeURIComponent((await params).id);
  const rule = await getDetection(id);
  if (rule === null) {
    if (!(await apiIsReachable())) return <Offline />;
    notFound();
  }

  return (
    <Page
      title={rule.title}
      description={`Written by ${rule.author.name} — not drafted from telemetry, and not checked against any record here.`}
      actions={
        <Link href="/detections" className="focusable rounded text-xs underline decoration-dotted underline-offset-2">
          ← all detections
        </Link>
      }
    >
      <Panel title="About this rule" aside={<Badge status="warning">written</Badge>}>
        <dl className="grid gap-x-6 gap-y-2 text-sm sm:grid-cols-[auto_1fr]">
          <dt className="label">author</dt>
          <dd data-author className="mono text-[rgb(var(--gold))]">{rule.author.name}</dd>
          <dt className="label">written against</dt>
          <dd>
            {rule.incidents.map((incident, index) => (
              <span key={incident}>
                {index > 0 && ", "}
                <Link href={`/incidents/${encodeURIComponent(incident)}`} className="focusable rounded underline decoration-dotted">
                  <Ident>{incident}</Ident>
                </Link>
              </span>
            ))}
          </dd>
          {rule.technique && (
            <>
              <dt className="label">technique</dt>
              <dd className="mono text-xs">
                <a
                  href={`https://attack.mitre.org/techniques/${rule.technique.id.replace(".", "/")}/`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="focusable rounded underline decoration-dotted"
                >
                  {rule.technique.id}
                </a>{" "}
                {rule.technique.name}
              </dd>
            </>
          )}
          <dt className="label">status</dt>
          <dd className="mono text-xs">
            {rule.status} · {rule.level} · {rule.valid ? "parses as sigma" : "does not parse"}
          </dd>
        </dl>
        {rule.notes && (
          <p className="mt-4 text-sm leading-relaxed text-[rgb(var(--muted))]">
            <span className="label">reviewer's note</span> {rule.notes}
          </p>
        )}
      </Panel>

      <Panel title="The rule" aside={<span className="mono text-xs">{rule.path}</span>}>
        <pre className="min-w-0 max-w-full overflow-x-auto rounded border border-[rgb(var(--edge))] bg-[rgb(var(--sunk))] p-3 text-xs leading-relaxed">
          <code className="mono">{rule.yaml}</code>
        </pre>
        {rule.problems.length > 0 && (
          <ul className="mt-3 space-y-1 text-sm text-[rgb(var(--crit))]">
            {rule.problems.map((problem) => (
              <li key={problem}>{problem}</li>
            ))}
          </ul>
        )}
      </Panel>
    </Page>
  );
}
