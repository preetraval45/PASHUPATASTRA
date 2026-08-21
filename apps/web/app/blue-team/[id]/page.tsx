import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";

import { BlueTeam } from "@/components/blueteam";
import { Offline, Page } from "@/components/ui";
import { getBriefing, getScenarios } from "@/lib/api";

export const metadata: Metadata = {
  title: "Blue team",
  description: "Work this incident forwards from a single alert.",
};

export const dynamic = "force-dynamic";

export default async function PlayPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const id = decodeURIComponent((await params).id);
  const briefing = await getBriefing(id);

  // `null` covers both an unreachable API and an unknown id, so they are
  // separated by asking a second, cheap question rather than telling a visitor
  // the system is down when they mistyped a scenario.
  if (briefing === null) {
    const reachable = await getScenarios();
    if (reachable === null) return <Offline />;
    notFound();
  }

  return (
    <Page
      title={id}
      description="One alert. Investigate what you would look at, commit to an explanation and a response, then see what you missed."
      actions={
        <Link
          href="/blue-team"
          className="focusable rounded border border-[rgb(var(--edge-strong))] px-3 py-1.5 text-sm hover:bg-[rgb(var(--raised))]"
        >
          ← Scenarios
        </Link>
      }
    >
      <BlueTeam briefing={briefing} />
    </Page>
  );
}
