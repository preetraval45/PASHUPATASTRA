import type { Metadata } from "next";
import { Suspense } from "react";

import { AuthShell, SignupForm } from "@/components/authpages";

export const metadata: Metadata = { title: "Create account", description: "Create a free Pashupatastra account." };

export default function SignupPage() {
  return (
    <AuthShell>
      <Suspense fallback={null}>
        <SignupForm />
      </Suspense>
    </AuthShell>
  );
}
