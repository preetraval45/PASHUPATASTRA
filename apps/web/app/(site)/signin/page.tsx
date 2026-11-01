import type { Metadata } from "next";
import { Suspense } from "react";

import { SignIn } from "@/components/signin";

export const metadata: Metadata = {
  title: "Sign in",
  description: "Sign in with Google, email or as a guest to keep your training and join your company's workspace.",
};

export default function SignInPage() {
  return (
    <Suspense fallback={null}>
      <SignIn />
    </Suspense>
  );
}
