import type { Metadata } from "next";
import { Suspense } from "react";

import { AuthShell, VerifyForm } from "@/components/authpages";

export const metadata: Metadata = { title: "Confirm your email", description: "Confirm the address on your account." };

/** Where an emailed verification link lands (POST /auth/verify). */
export default function VerifyPage() {
  return (
    <AuthShell>
      <Suspense fallback={null}>
        <VerifyForm />
      </Suspense>
    </AuthShell>
  );
}
