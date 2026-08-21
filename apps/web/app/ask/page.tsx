import type { Metadata } from "next";
import { Suspense } from "react";

import { ChatConsole } from "@/components/chatconsole";
import { Offline, Page, Skeleton } from "@/components/ui";
import { getIncidents } from "@/lib/api";

export const metadata: Metadata = {
  title: "Ask",
  description:
    "Ask about an open incident and get an answer grounded in the stored evidence, with every claim cited and checkable.",
};

export const dynamic = "force-dynamic";

export default async function AskPage() {
  const incidents = await getIncidents();
  if (incidents === null) return <Offline />;

  return (
    <Page
      title="Ask"
      description="Questions about an open incident, answered from the evidence on file."
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
