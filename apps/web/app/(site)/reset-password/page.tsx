import type { Metadata } from "next";
import { Suspense } from "react";

import { AuthShell, ResetForm } from "@/components/authpages";

export const metadata: Metadata = { title: "New password", description: "Choose a new password." };

export default function ResetPage() {
  return (
    <AuthShell>
      <Suspense fallback={null}>
        <ResetForm />
      </Suspense>
    </AuthShell>
  );
}
