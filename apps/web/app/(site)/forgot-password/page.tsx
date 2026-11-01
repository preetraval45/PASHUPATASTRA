import type { Metadata } from "next";

import { AuthShell, ForgotForm } from "@/components/authpages";

export const metadata: Metadata = { title: "Reset password", description: "Get a link to set a new password." };

export default function ForgotPage() {
  return (
    <AuthShell>
      <ForgotForm />
    </AuthShell>
  );
}
