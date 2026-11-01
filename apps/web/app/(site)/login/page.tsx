import type { Metadata } from "next";
import { Suspense } from "react";

import { AuthShell, LoginForm } from "@/components/authpages";

export const metadata: Metadata = { title: "Sign in", description: "Sign in to your Pashupatastra workspace." };

export default function LoginPage() {
  return (
    <AuthShell>
      <Suspense fallback={null}>
        <LoginForm />
      </Suspense>
    </AuthShell>
  );
}
