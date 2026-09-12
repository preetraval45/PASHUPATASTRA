import type { Metadata } from "next";
import { Suspense } from "react";

import { ChatConsole } from "@/components/chatconsole";
import { Offline, Page, Skeleton } from "@/components/ui";
import { getIncidents, getUsage, type Usage } from "@/lib/api";

export const metadata: Metadata = {
  title: "Ask",
  description:
    "Ask about an open incident and get an answer grounded in the stored evidence, with every claim cited and checkable.",
};

export const dynamic = "force-dynamic";

export default async function AskPage() {
  const [incidents, usage] = await Promise.all([getIncidents(), getUsage()]);
  if (incidents === null) return <Offline />;

  return (
    <Page
      title="Ask"
      description="Questions about an open incident, answered from the evidence on file."
      actions={<Allowance usage={usage} />}
    >
      {/* `useSearchParams` in the console needs a boundary, and the fallback is
          a skeleton rather than nothing: this page is mostly one tall panel, so
          an empty frame reads as a failed load. */}
      <Suspense fallback={<Skeleton rows={6} />}>
        <ChatConsole incidents={incidents} />
      </Suspense>
    </Page>
  );
}

/**
 * `today 48k of 200k tokens · 61% from cache` — R61's shape, applied to spend.
 *
 * Every answer already prints its own token count; this is the same number
 * rolled up to the day and set against the provider's allowance, so a reader
 * can tell whether the console is close to refusing. Read from `/usage`, which
 * computes it from the audit ledger rather than from a counter that could drift
 * from it. Spend is not shown as `$0.00` — a zero with no reason reads as an
 * unwired panel — the reason is in the tooltip.
 */
function Allowance({ usage }: { usage: Usage | null }) {
  if (!usage) return null;
  const { today, allowance } = usage;
  const compact = (n: number) => (n >= 1000 ? `${Math.round(n / 1000)}k` : String(n));
  const cache =
    today.cache_hit_rate === null ? null : `${Math.round(today.cache_hit_rate * 100)}% from cache`;
  return (
    <p
      data-allowance
      className="mono text-[11px] text-[rgb(var(--faint))]"
      title={`${usage.spend_reason} Computed from ${usage.computed_from}.`}
    >
      today {compact(today.tokens)} of {compact(allowance.tokens_per_day)} tokens
      {cache && ` · ${cache}`}
      {today.turns === 0 && " · no questions yet"}
    </p>
  );
}
