import type { Metadata } from "next";

import { AdminConsole } from "@/components/adminconsole";

export const metadata: Metadata = { title: "Settings", description: "Users and companies, for platform administrators." };

export default function AdminPage() {
  return <AdminConsole />;
}
