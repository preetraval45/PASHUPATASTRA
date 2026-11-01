"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useEffect, useRef, useState, type FormEvent } from "react";

import { useAccount } from "@/components/account";
import { AccountFailure, authConfig, register, signIn, signInAsGuest, signInWithGoogle } from "@/lib/account";

type Google = {
  accounts: {
    id: {
      initialize: (options: { client_id: string; callback: (response: { credential: string }) => void }) => void;
      renderButton: (element: HTMLElement, options: Record<string, unknown>) => void;
    };
  };
};

/**
 * Sign in: Google when this deployment has a Google client id, email and
 * password, or a guest session to try everything first. After signing in the
 * visitor goes where they were heading (?next=), or to their account.
 */
export function SignIn() {
  const router = useRouter();
  const params = useSearchParams();
  const next = params.get("next")?.startsWith("/") ? (params.get("next") as string) : "/account";
  const invite = params.get("invite");
  const { me, ready } = useAccount();
  const [mode, setMode] = useState<"signin" | "register">(invite ? "register" : "signin");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [name, setName] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [googleId, setGoogleId] = useState<string | null>(null);
  const googleBox = useRef<HTMLDivElement>(null);

  const done = () => router.push(invite ? `/account?invite=${encodeURIComponent(invite)}` : next);

  useEffect(() => {
    if (ready && me && me.user.provider !== "guest") done();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ready, me]);

  useEffect(() => {
    authConfig()
      .then((c) => setGoogleId(c.google_client_id))
      .catch(() => setGoogleId(null));
  }, []);

  useEffect(() => {
    if (!googleId || !googleBox.current) return;
    const render = () => {
      const google = (window as unknown as { google?: Google }).google;
      if (!google || !googleBox.current) return;
      google.accounts.id.initialize({
        client_id: googleId,
        callback: async ({ credential }) => {
          setBusy(true);
          setError(null);
          try {
            await signInWithGoogle(credential);
            done();
          } catch (e) {
            setError(e instanceof AccountFailure ? e.message : "Google sign-in failed. Try again.");
          } finally {
            setBusy(false);
          }
        },
      });
      google.accounts.id.renderButton(googleBox.current, { theme: "filled_black", size: "large", shape: "pill", width: 320, text: "continue_with" });
    };
    const existing = document.getElementById("google-gsi");
    if (existing) return render();
    const script = document.createElement("script");
    script.id = "google-gsi";
    script.src = "https://accounts.google.com/gsi/client";
    script.async = true;
    script.onload = render;
    document.head.appendChild(script);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [googleId]);

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      if (mode === "signin") await signIn(email, password);
      else await register(email, password, name);
      done();
    } catch (e) {
      setError(e instanceof AccountFailure ? e.message : "Something went wrong. Try again.");
    } finally {
      setBusy(false);
    }
  };

  const guest = async () => {
    setBusy(true);
    setError(null);
    try {
      await signInAsGuest();
      done();
    } catch (e) {
      setError(e instanceof AccountFailure ? e.message : "Something went wrong. Try again.");
    } finally {
      setBusy(false);
    }
  };

  const field =
    "w-full rounded-xl border border-[rgb(var(--edge-strong))] bg-[rgb(var(--ground))] px-3.5 py-2.5 text-[0.9375rem] outline-none transition placeholder:text-[rgb(var(--faint))] focus:border-[rgb(var(--astra))]";

  return (
    <div className="mx-auto grid max-w-5xl items-center gap-10 py-4 lg:grid-cols-[1fr_26rem]">
      <div className="hidden lg:block">
        <p className="label text-[rgb(var(--astra))]">Pashupatastra for teams</p>
        <h1 className="mt-2 text-4xl font-semibold leading-tight tracking-tight">
          Train your people, see who is ready, and ask Sati when something looks wrong.
        </h1>
        <ul className="mt-6 space-y-3 text-[0.9375rem] text-[rgb(var(--muted))]">
          {[
            "Your training progress follows you to any device",
            "Create a company workspace and invite your team with a code",
            "See every employee's levels passed and scores in one place",
            "Guest access to try everything, no email needed",
          ].map((t) => (
            <li key={t} className="flex gap-3">
              <span aria-hidden="true" className="mt-1 inline-flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-[rgb(var(--ok))]/15 text-xs text-[rgb(var(--ok))]">
                ✓
              </span>
              {t}
            </li>
          ))}
        </ul>
      </div>

      <div className="rounded-3xl border border-[rgb(var(--edge))] bg-[rgb(var(--panel))] p-6 shadow-[0_20px_60px_-30px_rgb(0_0_0/0.6)] sm:p-8">
        <h2 className="text-2xl font-semibold tracking-tight">{mode === "signin" ? "Welcome back" : "Create your account"}</h2>
        <p className="mt-1 text-sm text-[rgb(var(--muted))]">
          {invite ? "Your company invited you. Create an account to join." : mode === "signin" ? "Sign in to pick up where you left off." : "Free. Your training is saved to it."}
        </p>

        {googleId && (
          <div className="mt-6 flex justify-center">
            <div ref={googleBox} />
          </div>
        )}
        {googleId && (
          <p className="my-5 flex items-center gap-3 text-xs text-[rgb(var(--faint))]">
            <span className="h-px flex-1 bg-[rgb(var(--edge))]" /> or with email <span className="h-px flex-1 bg-[rgb(var(--edge))]" />
          </p>
        )}

        <form onSubmit={submit} className={`space-y-3 ${googleId ? "" : "mt-6"}`}>
          {mode === "register" && (
            <label className="block text-sm">
              <span className="mb-1 block text-[rgb(var(--muted))]">Your name</span>
              <input className={field} value={name} onChange={(e) => setName(e.target.value)} autoComplete="name" maxLength={60} />
            </label>
          )}
          <label className="block text-sm">
            <span className="mb-1 block text-[rgb(var(--muted))]">Email</span>
            <input className={field} type="email" required value={email} onChange={(e) => setEmail(e.target.value)} autoComplete="email" />
          </label>
          <label className="block text-sm">
            <span className="mb-1 block text-[rgb(var(--muted))]">Password</span>
            <input
              className={field}
              type="password"
              required
              minLength={mode === "register" ? 10 : undefined}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoComplete={mode === "signin" ? "current-password" : "new-password"}
            />
            {mode === "register" && <span className="mt-1 block text-xs text-[rgb(var(--faint))]">At least 10 characters. A few random words work well.</span>}
          </label>
          {error && (
            <p role="alert" className="rounded-xl border border-[rgb(var(--crit))]/40 bg-[rgb(var(--crit))]/10 px-3 py-2 text-sm">
              {error}
            </p>
          )}
          <button
            type="submit"
            disabled={busy}
            className="focusable w-full rounded-xl bg-[rgb(var(--astra))] py-2.5 text-sm font-semibold text-white transition hover:brightness-110 disabled:opacity-60"
          >
            {busy ? "One moment…" : mode === "signin" ? "Sign in" : "Create account"}
          </button>
        </form>

        <p className="mt-4 text-center text-sm text-[rgb(var(--muted))]">
          {mode === "signin" ? "New here? " : "Already have an account? "}
          <button
            type="button"
            onClick={() => {
              setMode(mode === "signin" ? "register" : "signin");
              setError(null);
            }}
            className="focusable font-semibold text-[rgb(var(--astra))] hover:underline"
          >
            {mode === "signin" ? "Create an account" : "Sign in"}
          </button>
        </p>

        <div className="mt-6 border-t border-[rgb(var(--edge))] pt-5">
          <button
            type="button"
            onClick={guest}
            disabled={busy}
            className="focusable w-full rounded-xl border border-[rgb(var(--edge-strong))] py-2.5 text-sm font-medium transition hover:bg-[rgb(var(--raised))] disabled:opacity-60"
          >
            Continue as guest
          </button>
          <p className="mt-2 text-center text-xs text-[rgb(var(--faint))]">
            A guest keeps training progress but can't own a company. By signing in you agree to the{" "}
            <Link href="/privacy" className="underline">privacy notice</Link>.
          </p>
        </div>
      </div>
    </div>
  );
}
