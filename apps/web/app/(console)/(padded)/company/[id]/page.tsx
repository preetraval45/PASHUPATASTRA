import type { Metadata } from "next";

import { CompanyPage } from "@/components/companypage";

export const metadata: Metadata = {
  title: "Company",
  description: "Your company's security policies and your training.",
};

export default async function Company({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <CompanyPage orgId={id} />;
}
