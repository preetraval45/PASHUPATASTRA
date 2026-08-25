import { AgentTurn } from "@/components/agentturn";
import { Ago, Badge, Empty, Ident, Offline, Page, Panel, type Status } from "@/components/ui";
import { getAudit, type AuditRecord } from "@/lib/api";

import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Audit",
  description:
    "Append-only record of what was observed, reasoned, authorised and executed — written before an action runs, never after.",
};

export const dynamic = "force-dynamic";

/**
 * Each record kind gets a status treatment matching what it means, not how
 * dramatic it sounds. A denial is not a failure — it is the policy engine
 * working — so it reads as information, while a verification failure reads as
 * the problem it is.
 */
const KIND: Record<string, { label: string; status: Status }> = {
  observation: { label: "observed", status: "neutral" },
  hypothesis: { label: "reasoned", status: "neutral" },
  policy_evaluation: { label: "policy", status: "neutral" },
  approval: { label: "approved", status: "warning" },
  execution_attempt: { label: "executing", status: "warning" },
  execution_result: { label: "executed", status: "ok" },
  verification: { label: "verified", status: "ok" },
  escalation: { label: "escalated", status: "high" },
  // Its own kind because it is its own thing: not something the platform saw,
  // but something it said.
  agent_turn: { label: "answered", status: "neutral" },
};

export default async function AuditPage() {
  // Bounded, and the bound is stated rather than silent. An audit view that
  // quietly shows "the last 100" reads as "everything that happened".
  const LIMIT = 100;
  const records = await getAudit(LIMIT);
  if (!records) return <Offline />;

  return (
    <Page
      title="Audit"
      description="Append-only record of everything observed, reasoned, authorized, executed, and verified. Written before execution, never after — so a crash mid-action still leaves evidence the attempt happened."
    >
      <Panel
        title="Records"
        aside={`newest ${records.length}${records.length === LIMIT ? ` of more` : ""}, most recent first`}
      >
        {records.length === 0 ? (
          <Empty
          art="ledger"
          title="Nothing recorded yet."
          action={{ href: "/incidents", label: "Open a scenario →" }}
        >
            Records appear as Drishti polls, Dharma evaluates, and Astra executes.
          </Empty>
        ) : (
          <ol className="divide-y divide-[rgb(var(--edge))]">
            {records.map((record, index) => (
              <Row key={index} record={record} />
            ))}
          </ol>
        )}
      </Panel>

      <Panel title="Why this exists">
        <p className="text-sm text-[rgb(var(--muted))]">
          Every claim the system makes is traceable to a record here, and every action is
          traceable to the policy verdict that authorized it. Denials are recorded alongside
          approvals — they document where autonomy stopped and why, which is the more
          interesting half.
        </p>
      </Panel>
    </Page>
  );
}

function Row({ record }: { record: AuditRecord }) {
  const kind = KIND[record.kind] ?? { label: record.kind, status: "neutral" as Status };
  const human = record.actor.startsWith("human:");

  return (
    <li className="flex flex-wrap items-baseline gap-x-3 gap-y-1 py-3 first:pt-0 last:pb-0">
      <span className="w-16 shrink-0 text-xs text-[rgb(var(--faint))]">
        <Ago at={record.at} />
      </span>
      <Badge status={kind.status}>{kind.label}</Badge>
      <span
        className={`mono text-xs ${
          human ? "text-[rgb(var(--gold))]" : "text-[rgb(var(--astra))]"
        }`}
        title={human ? "a person decided this" : "an agent decided this"}
      >
        {record.actor}
      </span>
      {/* `div`, for the same reason as the incident page: `AgentTurn` renders
          a `<details>`, which is flow content and cannot legally sit inside a
          `span`. The parser moves it during hydration and React reports #418. */}
      <div className="min-w-0 basis-full break-words text-sm sm:flex-1 sm:basis-0">
        {record.summary}
        <AgentTurn record={record} />
      </div>
      {record.incident_ref && (
        <span className="text-xs">
          <Ident>{record.incident_ref}</Ident>
        </span>
      )}
    </li>
  );
}
