"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useEffect, useRef, useState, type FormEvent } from "react";

import { initials, useAccount } from "@/components/account";
import {
  AccountFailure,
  changePassword,
  createCompany,
  deleteAccount,
  joinCompany,
  rename,
  resendVerification,
  signOut,
  signOutEverywhere,
} from "@/lib/account";
import { MODULES } from "@/lib/training";

const ROLE_LABEL = { owner: "Owner", admin: "Admin", employee: "Employee" } as const;

/** Your account: who you are, your training, your companies, and the door out. */
export function AccountPage() {
  const router = useRouter();
  const params = useSearchParams();
  const { me, ready } = useAccount();
  const [company, setCompany] = useState("");
  const [code, setCode] = useState(params.get("invite") ?? "");
  const [name, setName] = useState<string | null>(null);
  const [message, setMessage] = useState<{ ok: boolean; text: string } | null>(null);
  const [busy, setBusy] = useState(false);
  const [confirm, setConfirm] = useState(false);
  const [current, setCurrent] = useState("");
  const [fresh, setFresh] = useState("");
  const joinedFromLink = useRef(false);

  useEffect(() => {
    if (ready && !me) router.replace(`/login?next=/account${params.get("invite") ? `&invite=${params.get("invite")}` : ""}`);
  }, [ready, me, router, params]);

  const run = async (work: () => Promise<unknown>, ok: string) => {
    setBusy(true);
    setMessage(null);
    try {
      await work();
      setMessage({ ok: true, text: ok });
    } catch (e) {
      setMessage({ ok: false, text: e instanceof AccountFailure ? e.message : "Something went wrong. Try again." });
    } finally {
      setBusy(false);
    }
  };

  // Arriving from an invite link joins the company once, without retyping the code.
  useEffect(() => {
    const invite = params.get("invite");
    if (!me || !invite || joinedFromLink.current) return;
    joinedFromLink.current = true;
    run(() => joinCompany(invite), "You joined the company. Your training now counts toward it.");
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [me]);

  if (!ready || !me) {
    return <div className="h-64 animate-pulse rounded-3xl bg-[rgb(var(--raised))]" />;
  }

  const passed = MODULES.filter((m) => me.training[m.slug]?.passed);
  const guest = me.user.provider === "guest";
  const card = "rounded-3xl border border-[rgb(var(--edge))] bg-[rgb(var(--panel))] p-5 sm:p-6";
  const field =
    "min-w-0 flex-1 rounded-xl border border-[rgb(var(--edge-strong))] bg-[rgb(var(--ground))] px-3.5 py-2.5 text-sm outline-none focus:border-[rgb(var(--astra))]";
  const primary =
    "focusable rounded-xl bg-[rgb(var(--astra))] px-4 py-2.5 text-sm font-semibold text-white transition hover:brightness-110 disabled:opacity-60";

  return (
    <div className="mx-auto max-w-4xl space-y-5">
      <section className={`${card} relative isolate overflow-hidden`}>
        <div aria-hidden="true" className="hero-glow pointer-events-none absolute -inset-10 -z-10 opacity-60" />
        <div className="flex flex-wrap items-center gap-4">
          <span className="inline-flex h-16 w-16 items-center justify-center rounded-2xl bg-[linear-gradient(135deg,rgb(var(--astra)),rgb(var(--astra)/0.55))] text-2xl font-bold text-white">
            {initials(me.user.name)}
          </span>
          <div className="min-w-0 flex-1">
            {name === null ? (
              <h1 className="flex items-center gap-2 text-2xl font-semibold tracking-tight">
                {me.user.name}
                {!guest && (
                  <button type="button" onClick={() => setName(me.user.name)} className="focusable text-xs font-normal text-[rgb(var(--faint))] hover:text-[rgb(var(--ink))]">
                    Edit
                  </button>
                )}
              </h1>
            ) : (
              <form
                className="flex gap-2"
                onSubmit={(e: FormEvent) => {
                  e.preventDefault();
                  run(() => rename(name), "Name saved.").then(() => setName(null));
                }}
              >
                <input className={field} value={name} onChange={(e) => setName(e.target.value)} maxLength={60} autoFocus />
                <button className={primary} disabled={busy}>Save</button>
              </form>
            )}
            <p className="mt-0.5 text-sm text-[rgb(var(--muted))]">
              {guest ? "Guest session on this device" : me.user.email}
              {" · "}
              {me.user.provider === "google" ? "Google" : me.user.provider === "email" ? "Email and password" : "Guest"}
              {me.user.provider === "email" && (
                <>
                  {" · "}
                  {me.user.verified ? (
                    <span className="text-[rgb(var(--ok))]">verified</span>
                  ) : (
                    <>
                      <span className="text-[rgb(var(--warn))]">not verified</span>{" "}
                      {/* A link to the address proves it is yours (POST /me/verify). With email sending not
                          yet switched on, the account works the same and says so rather than pretending. */}
                      <button
                        type="button"
                        disabled={busy}
                        onClick={() =>
                          run(async () => {
                            const { sent, email_verify } = await resendVerification();
                            if (!email_verify) throw new AccountFailure("Email isn't switched on for this site yet; your account works without it.", 0);
                            if (!sent) throw new AccountFailure("A link went out less than a minute ago. Check your inbox.", 0);
                          }, "Link sent. Open it within a day to confirm your address.")
                        }
                        className="focusable underline hover:text-[rgb(var(--ink))]"
                      >
                        send link
                      </button>
                    </>
                  )}
                </>
              )}
            </p>
            <p className="mt-1 text-xs text-[rgb(var(--faint))]">
              Account id <code className="mono select-all rounded bg-[rgb(var(--raised))] px-1.5 py-0.5">{me.user.id}</code>
              {me.platform_admin && <span className="ml-2 font-semibold text-[rgb(var(--astra))]">platform administrator</span>}
            </p>
          </div>
          <button
            type="button"
            onClick={() => {
              signOut();
              router.push("/");
            }}
            className="focusable rounded-xl border border-[rgb(var(--edge-strong))] px-4 py-2 text-sm transition hover:bg-[rgb(var(--raised))]"
          >
            Sign out
          </button>
        </div>
        {guest && (
          <p className="mt-4 rounded-xl border border-[rgb(var(--warn))]/40 bg-[rgb(var(--warn))]/10 px-4 py-3 text-sm">
            You're a guest. Your training is saved, but a guest can't own a company or sign in on another device.{" "}
            <Link href="/signup?next=/account" onClick={() => signOut()} className="font-semibold underline">
              Create a full account
            </Link>
            .
          </p>
        )}
      </section>

      {message && (
        <p
          role="status"
          className={`rounded-xl border px-4 py-3 text-sm ${
            message.ok ? "border-[rgb(var(--ok))]/40 bg-[rgb(var(--ok))]/10" : "border-[rgb(var(--crit))]/40 bg-[rgb(var(--crit))]/10"
          }`}
        >
          {message.text}
        </p>
      )}

      <section className={card}>
        <div className="flex items-baseline justify-between gap-3">
          <h2 className="text-lg font-semibold">Your training</h2>
          <Link href="/training" className="text-sm text-[rgb(var(--astra))] hover:underline">
            Continue →
          </Link>
        </div>
        <p className="tnum mt-1 text-sm text-[rgb(var(--muted))]">
          {passed.length} of {MODULES.length} levels passed
        </p>
        <ol className="mt-3 grid grid-cols-9 gap-1.5" aria-label="Levels">
          {MODULES.map((m) => {
            const r = me.training[m.slug];
            return (
              <li
                key={m.slug}
                title={`Level ${m.level}: ${m.title}${r ? ` · best ${Math.round(r.best * 100)}%` : ""}`}
                className={`tnum flex h-10 items-center justify-center rounded-lg text-xs font-semibold ${
                  r?.passed
                    ? "bg-[rgb(var(--ok))] text-white"
                    : r
                      ? "bg-[rgb(var(--warn))]/20 text-[rgb(var(--warn))]"
                      : "bg-[rgb(var(--raised))] text-[rgb(var(--faint))]"
                }`}
              >
                {m.level}
              </li>
            );
          })}
        </ol>
      </section>

      <section className={card}>
        <h2 className="text-lg font-semibold">Companies</h2>
        {me.orgs.length === 0 ? (
          <p className="mt-1 text-sm text-[rgb(var(--muted))]">
            Join your company with the invite code your admin gave you, or create a workspace for your own team.
          </p>
        ) : (
          <ul className="mt-3 space-y-2">
            {me.orgs.map((o) => (
              <li key={o.id} className="flex flex-wrap items-center gap-3 rounded-2xl border border-[rgb(var(--edge))] p-3.5">
                <span className="inline-flex h-10 w-10 items-center justify-center rounded-xl bg-[rgb(var(--raised))] text-sm font-bold">
                  {initials(o.name)}
                </span>
                <span className="min-w-0 flex-1">
                  <span className="block font-semibold">{o.name}</span>
                  <span className="block text-xs text-[rgb(var(--muted))]">{ROLE_LABEL[o.role]}</span>
                </span>
                <Link href={`/company/${o.id}`} className="focusable rounded-xl border border-[rgb(var(--edge-strong))] px-4 py-2.5 text-sm hover:bg-[rgb(var(--raised))]">
                  Policies
                </Link>
                {o.role !== "employee" && (
                  <Link href={`/team/${o.id}`} className={primary}>
                    Team dashboard →
                  </Link>
                )}
              </li>
            ))}
          </ul>
        )}
        <div className="mt-4 grid gap-3 md:grid-cols-2">
          <form
            className="rounded-2xl border border-[rgb(var(--edge))] p-4"
            onSubmit={(e: FormEvent) => {
              e.preventDefault();
              run(() => joinCompany(code), "You joined the company.").then(() => setCode(""));
            }}
          >
            <p className="text-sm font-semibold">Join with an invite code</p>
            <div className="mt-2 flex gap-2">
              <input className={`${field} mono uppercase`} placeholder="e.g. K7Q2M9XA" value={code} onChange={(e) => setCode(e.target.value)} maxLength={16} required />
              <button className={primary} disabled={busy}>Join</button>
            </div>
          </form>
          <form
            className="rounded-2xl border border-[rgb(var(--edge))] p-4"
            onSubmit={(e: FormEvent) => {
              e.preventDefault();
              run(() => createCompany(company), "Workspace created. Share its invite code from the team dashboard.").then(() => setCompany(""));
            }}
          >
            <p className="text-sm font-semibold">Create a company workspace</p>
            <div className="mt-2 flex gap-2">
              <input className={field} placeholder="Company name" value={company} onChange={(e) => setCompany(e.target.value)} maxLength={80} required disabled={guest} />
              <button className={primary} disabled={busy || guest}>Create</button>
            </div>
            {guest && <p className="mt-2 text-xs text-[rgb(var(--faint))]">Needs a full account.</p>}
          </form>
        </div>
      </section>

      <section className={card}>
        <h2 className="text-lg font-semibold">Security</h2>
        {me.user.provider === "email" && (
          <form
            className="mt-3 grid gap-2 sm:grid-cols-[1fr_1fr_auto]"
            onSubmit={(e: FormEvent) => {
              e.preventDefault();
              run(() => changePassword(current, fresh), "Password changed. Your other devices were signed out.").then(() => {
                setCurrent("");
                setFresh("");
              });
            }}
          >
            <input className={field} type="password" placeholder="Current password" value={current} onChange={(e) => setCurrent(e.target.value)} autoComplete="current-password" required />
            <input className={field} type="password" placeholder="New password (10+ characters)" value={fresh} onChange={(e) => setFresh(e.target.value)} autoComplete="new-password" minLength={10} required />
            <button className={primary} disabled={busy}>Change password</button>
          </form>
        )}
        <div className="mt-4 flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-[rgb(var(--edge))] p-4">
          <span className="text-sm">
            <span className="block font-semibold">Sign out everywhere</span>
            <span className="block text-[rgb(var(--muted))]">Ends every session on every device, this one too. Use it if a device was lost.</span>
          </span>
          <button
            type="button"
            disabled={busy}
            onClick={() => run(signOutEverywhere, "Signed out everywhere.").then(() => router.push("/login"))}
            className="focusable rounded-xl border border-[rgb(var(--edge-strong))] px-4 py-2 text-sm transition hover:bg-[rgb(var(--raised))]"
          >
            Sign out everywhere
          </button>
        </div>
      </section>

      <section className={`${card} border-[rgb(var(--crit))]/30`}>
        <h2 className="text-lg font-semibold">Delete account</h2>
        <p className="mt-1 text-sm text-[rgb(var(--muted))]">
          Erases your account, your sign-in, your company memberships and your training record. This can't be undone.
        </p>
        {confirm ? (
          <div className="mt-3 flex flex-wrap gap-2">
            <button
              type="button"
              disabled={busy}
              onClick={() => run(deleteAccount, "Your account was deleted.").then(() => router.push("/"))}
              className="focusable rounded-xl bg-[rgb(var(--crit))] px-4 py-2 text-sm font-semibold text-white"
            >
              Yes, delete everything
            </button>
            <button type="button" onClick={() => setConfirm(false)} className="focusable rounded-xl border border-[rgb(var(--edge-strong))] px-4 py-2 text-sm">
              Keep my account
            </button>
          </div>
        ) : (
          <button type="button" onClick={() => setConfirm(true)} className="focusable mt-3 rounded-xl border border-[rgb(var(--crit))]/50 px-4 py-2 text-sm text-[rgb(var(--crit))]">
            Delete my account
          </button>
        )}
      </section>
    </div>
  );
}
