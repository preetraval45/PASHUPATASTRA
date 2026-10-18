import type { Metadata } from "next";
import { Suspense } from "react";

import { Sparkline } from "@/components/charts";
import { ChatConsole } from "@/components/chatconsole";
import { Offline, Skeleton } from "@/components/ui";
import { getIncidents, getModels, getUsage, type Usage } from "@/lib/api";

export const metadata: Metadata = {
  title: "Ask",
  description:
    "Ask about an open incident and get an answer grounded in the stored evidence, with every claim cited and checkable.",
};

export const dynamic = "force-dynamic";

/**
 * Full screen since RP-49: no page header, no centred column. The console's
 * frame supplies the chrome; this fills the rest of the window.
 */
export default async function AskPage() {
  const [incidents, usage, models] = await Promise.all([getIncidents(), getUsage(), getModels()]);
  if (incidents === null) {
    return (
      <main id="main" className="min-h-0 flex-1 overflow-y-auto p-6">
        <Offline />
      </main>
    );
  }

  return (
    <main id="main" className="flex min-h-0 flex-1">
      {/* `useSearchParams` in the console needs a boundary. */}
      <Suspense
        fallback={
          <div className="w-full p-6">
            <Skeleton rows={6} />
          </div>
        }
      >
        <ChatConsole incidents={incidents} models={models ?? []} allowance={<Allowance usage={usage} />} />
      </Suspense>
    </main>
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

  // The window has been in this response since R104 and was being dropped.
  // Drawn only once some day in it is non-zero: fourteen zeroes plot as a
  // flat line along the axis, which looks like a chart of something and is a
  // picture of nothing. `charts.tsx` will not invent a value and this will
  // not ask it to.
  const window = [...usage.days].sort((a, b) => a.day.localeCompare(b.day));
  const series = window.map((day) => day.turns);
  const worthDrawing = series.length > 1 && series.some((turns) => turns > 0);

  return (
    <div className="flex items-center justify-between gap-3">
      <p
        data-allowance
        className="mono text-[11px] text-[rgb(var(--faint))]"
        title={`${usage.spend_reason} Computed from ${usage.computed_from}.`}
      >
        today {compact(today.tokens)} of {compact(allowance.tokens_per_day)} tokens
        {cache && ` · ${cache}`}
        {today.turns === 0 && " · no questions yet"}
      </p>
      {worthDrawing && (
        <span className="hidden w-24 sm:block" data-usage-chart>
          <Sparkline
            values={series}
            label={`questions a day over the last ${series.length} days`}
          />
        </span>
      )}
    </div>
  );
}
