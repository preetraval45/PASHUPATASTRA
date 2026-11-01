import type { Metadata } from "next";
import { Suspense } from "react";

import { AccountPage } from "@/components/accountpage";

export const metadata: Metadata = {
  title: "Account",
  description: "Your account, your training record and your company workspaces.",
};

export default function Account() {
  return (
    <Suspense fallback={null}>
      <AccountPage />
    </Suspense>
  );
}
