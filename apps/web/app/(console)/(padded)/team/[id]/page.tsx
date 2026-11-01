import type { Metadata } from "next";

import { TeamDashboard } from "@/components/teamdashboard";

export const metadata: Metadata = {
  title: "Team dashboard",
  description: "Your company's security training: who joined, who passed which level, and who has gone quiet.",
};

export default async function TeamPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <TeamDashboard orgId={id} />;
}
