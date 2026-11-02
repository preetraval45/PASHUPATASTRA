"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useEffect, useState, type FormEvent, type ReactNode } from "react";

import { useAccount } from "@/components/account";
import { Sigil } from "@/components/chrome";
import {
  AccountFailure,
  authConfig,
  forgotPassword,
  register,
  resetPassword,
  signIn,
  signInAsGuest,
  verifyEmail,
} from "@/lib/account";

/**
 * The account pages, one layout: the product on the left, the form on the
 * right. Login, sign-up, forgot password and reset password, as separate pages
 * a visitor can bookmark and a reset email can link to.
 */

const FEATURES = [
  ["Sati, the investigation agent", "Answers security questions from MITRE ATT&CK, CAPEC and CISA, with sources"],
  ["Training your team will finish", "Nine levels, games and labs, with every person's progress on one dashboard"],
  ["Live threat picture", "Real attacks reported by public feeds, refreshed every minute"],
  ["Incidents, explained", "Every diagnosis cites the evidence behind it"],
] as const;

export function AuthShell({ children }: { children: ReactNode }) {
  return (
    <div className="-mx-4 -my-6 grid min-h-[calc(100dvh-3.5rem)] sm:-mx-6 sm:-my-8 lg:grid-cols-[1.05fr_1fr]">
      <aside className="relative isolate hidden overflow-hidden border-r border-[rgb(var(--edge))] bg-[rgb(var(--panel))] p-10 lg:flex lg:flex-col lg:justify-between xl:p-14">
        <div aria-hidden="true" className="hero-glow pointer-events-none absolute -inset-20 -z-10 opacity-90" />
        <Link href="/" className="focusable w-fit rounded">
          <Sigil className="h-10 w-auto" />
        </Link>
        <div>
          <p className="label text-[rgb(var(--astra))]">AI security platform</p>
          <h2 className="mt-3 max-w-lg text-4xl font-semibold leading-[1.1] tracking-tight xl:text-5xl">
            Know what's attacking you. Train the people it targets.
          </h2>
          <ul className="mt-8 space-y-4">
            {FEATURES.map(([title, body]) => (
              <li key={title} className="flex gap-3">
                <span aria-hidden="true" className="mt-0.5 inline-flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-[rgb(var(--astra))]/15 text-xs text-[rgb(var(--astra))]">
                  ✓
                </span>
                <span>
                  <span className="block font-semibold">{title}</span>
                  <span className="block text-sm text-[rgb(var(--muted))]">{body}</span>
                </span>
              </li>
            ))}
          </ul>
        </div>
        <dl className="grid grid-cols-3 gap-4 border-t border-[rgb(var(--edge))] pt-6">
          {[
            ["9", "own AI models"],
            ["9", "training levels"],
            ["7", "live threat feeds"],
          ].map(([n, label]) => (
            <div key={label}>
              <dt className="sr-only">{label}</dt>
              <dd className="tnum text-3xl font-semibold">{n}</dd>
              <dd className="text-xs text-[rgb(var(--muted))]">{label}</dd>
            </div>
          ))}
        </dl>
      </aside>
      <main className="flex items-start justify-center px-4 pb-10 pt-8 sm:px-8 lg:items-center lg:py-10">
        <div className="w-full max-w-sm">
          <Link href="/" className="focusable mb-8 block w-fit rounded lg:hidden">
            <Sigil className="h-9 w-auto" />
          </Link>
          {children}
        </div>
      </main>
    </div>
  );
}

const FIELD =
  "w-full rounded-xl border border-[rgb(var(--edge-strong))] bg-[rgb(var(--ground))] px-3.5 py-2.5 text-[0.9375rem] outline-none transition placeholder:text-[rgb(var(--faint))] focus:border-[rgb(var(--astra))] focus:ring-4 focus:ring-[rgb(var(--astra))]/15";
const PRIMARY =
  "focusable w-full rounded-xl bg-[rgb(var(--astra))] py-2.5 text-sm font-semibold text-white shadow-lg shadow-[rgb(var(--astra))]/20 transition hover:brightness-110 disabled:opacity-60";

function Field({ label, aside, children }: { label: string; aside?: ReactNode; children: ReactNode }) {
  return (
    <label className="block text-sm">
      <span className="mb-1.5 flex items-center justify-between font-medium">
        {label}
        {aside}
      </span>
      {children}
    </label>
  );
}

/** A password box with show/hide. */
function Password({ value, onChange, autoComplete, minLength }: { value: string; onChange: (v: string) => void; autoComplete: string; minLength?: number }) {
  const [shown, setShown] = useState(false);
  return (
    <span className="relative block">
      <input
        className={`${FIELD} pr-16`}
        type={shown ? "text" : "password"}
        required
        minLength={minLength}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        autoComplete={autoComplete}
      />
      <button
        type="button"
        onClick={() => setShown((s) => !s)}
        className="focusable absolute right-2 top-1/2 -translate-y-1/2 rounded-md px-2 py-1 text-xs text-[rgb(var(--muted))] hover:text-[rgb(var(--ink))]"
      >
        {shown ? "Hide" : "Show"}
      </button>
    </span>
  );
}

/** How strong a new password looks: length first, then variety. A guide, not a rule. */
export function strength(password: string): { score: 0 | 1 | 2 | 3 | 4; label: string } {
  if (!password) return { score: 0, label: "" };
  let score = password.length >= 16 ? 3 : password.length >= 12 ? 2 : password.length >= 10 ? 1 : 0;
  const kinds = [/[a-z]/, /[A-Z]/, /\d/, /[^\w]/, /\s/].filter((r) => r.test(password)).length;
  if (kinds >= 3 && score > 0) score += 1;
  const s = Math.min(4, score) as 0 | 1 | 2 | 3 | 4;
  return { score: s, label: ["Too short", "Okay", "Good", "Strong", "Very strong"][s] };
}

function Meter({ password }: { password: string }) {
  const { score, label } = strength(password);
  if (!password) return <span className="mt-1.5 block text-xs text-[rgb(var(--faint))]">At least 10 characters. A few random words work well.</span>;
  const tone = score <= 1 ? "--crit" : score === 2 ? "--warn" : "--ok";
  return (
    <span className="mt-2 flex items-center gap-2">
      <span className="flex flex-1 gap-1" aria-hidden="true">
        {[1, 2, 3, 4].map((i) => (
          <span key={i} className="h-1.5 flex-1 rounded-full" style={{ background: i <= score ? `rgb(var(${tone}))` : "rgb(var(--raised))" }} />
        ))}
      </span>
      <span className="w-20 text-right text-xs" style={{ color: `rgb(var(${tone}))` }}>
        {label}
      </span>
    </span>
  );
}

function Problem({ text }: { text: string | null }) {
  if (!text) return null;
  return (
    <p role="alert" className="rise rounded-xl border border-[rgb(var(--crit))]/40 bg-[rgb(var(--crit))]/10 px-3.5 py-2.5 text-sm">
      {text}
    </p>
  );
}

function Divider({ children }: { children: ReactNode }) {
  return (
    <p className="my-5 flex items-center gap-3 text-xs uppercase tracking-wider text-[rgb(var(--faint))]">
      <span className="h-px flex-1 bg-[rgb(var(--edge))]" />
      {children}
      <span className="h-px flex-1 bg-[rgb(var(--edge))]" />
    </p>
  );
}

function message(e: unknown): string {
  return e instanceof AccountFailure ? e.message : "Something went wrong. Try again.";
}

/** Where to go after signing in: ?next= when it is a path on this site, else the account. */
function useAfter() {
  const params = useSearchParams();
  const router = useRouter();
  const invite = params.get("invite");
  const next = params.get("next")?.startsWith("/") && !params.get("next")?.startsWith("//") ? (params.get("next") as string) : "/account";
  const query = invite ? `?invite=${encodeURIComponent(invite)}` : "";
  return { invite, query, go: () => router.push(invite ? `/account${query}` : next) };
}

function Guest({ onError }: { onError: (text: string) => void }) {
  const after = useAfter();
  const [busy, setBusy] = useState(false);
  return (
    <button
      type="button"
      disabled={busy}
      onClick={async () => {
        setBusy(true);
        try {
          await signInAsGuest();
          after.go();
        } catch (e) {
          onError(message(e));
          setBusy(false);
        }
      }}
      className="focusable w-full rounded-xl border border-[rgb(var(--edge-strong))] py-2.5 text-sm font-medium transition hover:bg-[rgb(var(--raised))] disabled:opacity-60"
    >
      Try it as a guest — no signup
    </button>
  );
}

export function LoginForm() {
  const after = useAfter();
  const { me, ready } = useAccount();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (ready && me && me.user.provider !== "guest") after.go();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ready, me]);

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await signIn(email, password);
      after.go();
    } catch (e) {
      setError(message(e));
      setBusy(false);
    }
  };

  return (
    <div className="rise">
      <h1 className="text-3xl font-semibold tracking-tight">Welcome back</h1>
      <p className="mt-1.5 text-[rgb(var(--muted))]">Sign in to your Pashupatastra workspace</p>
      <form onSubmit={submit} className="mt-8 space-y-4">
        <Field label="Email">
          <input className={FIELD} type="email" required value={email} onChange={(e) => setEmail(e.target.value)} autoComplete="email" autoFocus />
        </Field>
        <Field
          label="Password"
          aside={
            <Link href="/forgot-password" className="text-xs font-medium text-[rgb(var(--astra))] hover:underline">
              Forgot password?
            </Link>
          }
        >
          <Password value={password} onChange={setPassword} autoComplete="current-password" />
        </Field>
        <Problem text={error} />
        <button type="submit" disabled={busy} className={PRIMARY}>
          {busy ? "Signing in…" : "Sign in"}
        </button>
      </form>
      <Divider>or</Divider>
      <Guest onError={setError} />
      <p className="mt-8 text-center text-sm text-[rgb(var(--muted))]">
        Don't have an account yet?{" "}
        <Link href={`/signup${after.query}`} className="font-semibold text-[rgb(var(--astra))] hover:underline">
          Create one
        </Link>
      </p>
    </div>
  );
}

export function SignupForm() {
  const after = useAfter();
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await register(email, password, name);
      after.go();
    } catch (e) {
      setError(message(e));
      setBusy(false);
    }
  };

  return (
    <div className="rise">
      <h1 className="text-3xl font-semibold tracking-tight">Create your account</h1>
      <p className="mt-1.5 text-[rgb(var(--muted))]">
        {after.invite ? "Your company invited you. Create an account to join it." : "Free. Your training is saved to it."}
      </p>
      <form onSubmit={submit} className="mt-8 space-y-4">
        <Field label="Full name">
          <input className={FIELD} required value={name} onChange={(e) => setName(e.target.value)} autoComplete="name" maxLength={60} autoFocus />
        </Field>
        <Field label="Work email">
          <input className={FIELD} type="email" required value={email} onChange={(e) => setEmail(e.target.value)} autoComplete="email" />
        </Field>
        <Field label="Password">
          <Password value={password} onChange={setPassword} autoComplete="new-password" minLength={10} />
          <Meter password={password} />
        </Field>
        <Problem text={error} />
        <button type="submit" disabled={busy} className={PRIMARY}>
          {busy ? "Creating your account…" : "Create account"}
        </button>
        <p className="text-center text-xs text-[rgb(var(--faint))]">
          By creating an account you agree to the{" "}
          <Link href="/privacy" className="underline">
            privacy notice
          </Link>
          .
        </p>
      </form>
      <Divider>or</Divider>
      <Guest onError={setError} />
      <p className="mt-8 text-center text-sm text-[rgb(var(--muted))]">
        Already have an account?{" "}
        <Link href={`/login${after.query}`} className="font-semibold text-[rgb(var(--astra))] hover:underline">
          Sign in
        </Link>
      </p>
    </div>
  );
}

export function ForgotForm() {
  const [email, setEmail] = useState("");
  const [busy, setBusy] = useState(false);
  const [sent, setSent] = useState<boolean | null>(null);
  const [emailing, setEmailing] = useState<boolean | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    authConfig()
      .then((c) => setEmailing(c.email_reset))
      .catch(() => setEmailing(null));
  }, []);

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const { email_reset } = await forgotPassword(email);
      setSent(email_reset);
    } catch (e) {
      setError(message(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="rise">
      <h1 className="text-3xl font-semibold tracking-tight">Reset your password</h1>
      {sent === null ? (
        <>
          <p className="mt-1.5 text-[rgb(var(--muted))]">
            {emailing === false
              ? "Password reset links come from your company's admin for now: ask them to send you one from the team dashboard."
              : "Enter your email and we'll send you a link to set a new password."}
          </p>
          {emailing !== false && (
            <form onSubmit={submit} className="mt-8 space-y-4">
              <Field label="Email">
                <input className={FIELD} type="email" required value={email} onChange={(e) => setEmail(e.target.value)} autoComplete="email" autoFocus />
              </Field>
              <Problem text={error} />
              <button type="submit" disabled={busy} className={PRIMARY}>
                {busy ? "Sending…" : "Send reset link"}
              </button>
            </form>
          )}
        </>
      ) : (
        <div className="mt-6 rounded-2xl border border-[rgb(var(--ok))]/40 bg-[rgb(var(--ok))]/10 p-4 text-sm">
          {sent
            ? "If an account uses that email, a reset link is on its way. It works for one hour."
            : "Email isn't set up on this deployment yet, so no link was sent. Your company admin can give you a reset link from the team dashboard."}
        </div>
      )}
      <p className="mt-8 text-center text-sm text-[rgb(var(--muted))]">
        Remembered it?{" "}
        <Link href="/login" className="font-semibold text-[rgb(var(--astra))] hover:underline">
          Back to sign in
        </Link>
      </p>
    </div>
  );
}

/** The page an emailed verification link opens: proves the address, then says so. */
export function VerifyForm() {
  const params = useSearchParams();
  const token = params.get("token") ?? "";
  const [state, setState] = useState<"checking" | "done" | "failed">(token ? "checking" : "failed");
  const [error, setError] = useState<string | null>(token ? null : "This link is incomplete. Open it again from the email.");

  useEffect(() => {
    if (!token) return;
    verifyEmail(token)
      .then(() => setState("done"))
      .catch((e) => {
        setError(message(e));
        setState("failed");
      });
  }, [token]);

  return (
    <div className="rise">
      <h1 className="text-3xl font-semibold tracking-tight">
        {state === "checking" ? "Confirming your email…" : state === "done" ? "Email confirmed" : "That link didn't work"}
      </h1>
      <p className="mt-1.5 text-[rgb(var(--muted))]">
        {state === "done"
          ? "Your address is verified. Your company can now rely on it."
          : state === "checking"
            ? "One moment."
            : "Ask for a new one from your account."}
      </p>
      <Problem text={error} />
      {state !== "checking" && (
        <Link href="/account" className={`${PRIMARY} mt-8 block text-center`}>
          Go to your account
        </Link>
      )}
    </div>
  );
}

export function ResetForm() {
  const params = useSearchParams();
  const router = useRouter();
  const token = params.get("token") ?? "";
  const [password, setPassword] = useState("");
  const [again, setAgain] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    if (password !== again) return setError("The two passwords don't match.");
    setBusy(true);
    setError(null);
    try {
      await resetPassword(token, password);
      router.push("/account");
    } catch (e) {
      setError(message(e));
      setBusy(false);
    }
  };

  if (!token) {
    return (
      <div className="rise">
        <h1 className="text-3xl font-semibold tracking-tight">This link is incomplete</h1>
        <p className="mt-1.5 text-[rgb(var(--muted))]">Open the reset link again, or ask for a new one.</p>
        <Link href="/forgot-password" className={`${PRIMARY} mt-8 block text-center`}>
          Get a new link
        </Link>
      </div>
    );
  }
  return (
    <div className="rise">
      <h1 className="text-3xl font-semibold tracking-tight">Choose a new password</h1>
      <p className="mt-1.5 text-[rgb(var(--muted))]">Every other device will be signed out.</p>
      <form onSubmit={submit} className="mt-8 space-y-4">
        <Field label="New password">
          <Password value={password} onChange={setPassword} autoComplete="new-password" minLength={10} />
          <Meter password={password} />
        </Field>
        <Field label="Type it again">
          <Password value={again} onChange={setAgain} autoComplete="new-password" minLength={10} />
        </Field>
        <Problem text={error} />
        <button type="submit" disabled={busy} className={PRIMARY}>
          {busy ? "Saving…" : "Set new password and sign in"}
        </button>
      </form>
    </div>
  );
}
