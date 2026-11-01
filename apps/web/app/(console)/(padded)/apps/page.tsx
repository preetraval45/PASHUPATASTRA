import type { Metadata } from "next";

import { AppLauncher } from "@/components/applauncher";

export const metadata: Metadata = { title: "Apps", description: "Every part of Pashupatastra, as apps." };

export default function AppsPage() {
  return <AppLauncher />;
}
