"use client";

import Link from "next/link";
import { useCallback, useEffect, useState, type FormEvent } from "react";

import { useAccount } from "@/components/account";
import { CompanySignals } from "@/components/companysignals";
import { OrgLogo } from "@/components/orgbrand";
import { daysUntil } from "@/lib/duedate";
import {
  AccountFailure,
  acknowledgePolicy,
  addPolicy,
  companyPolicies,
  removePolicy,
  type Policy,
} from "@/lib/account";
import { MODULES } from "@/lib/training";

/**
 * A company, from inside: its security policies to read and acknowledge, and
 * where the member stands on training. Admins publish and retire policies here
 * and see how many people have acknowledged each one.
 */
export function CompanyPage({ orgId }: { orgId: string }) {
  const { me, ready } = useAccount();
  const [data, setData] = useState<Awaited<ReturnType<typeof companyPolicies>> | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [open, setOpen] = useState<string | null>(null);
  const [title, setTitle] = useState("");
  const [body, setBody] = useState("");
  const [writing, setWriting] = useState(false);
  const [busy, setBusy] = useState(false);

  const reload = useCallback(() => {
    companyPolicies(orgId)
      .then(setData)
      .catch((e) => setError(e instanceof AccountFailure ? e.message : "Couldn't load the company."));
  }, [orgId]);

  useEffect(() => {
    if (ready && me) reload();
  }, [ready, me, reload]);

  if (ready && !me) {
    return (
      <p className="text-sm">
        <Link href={`/login?next=/company/${orgId}`} className="text-[rgb(var(--astra))] underline">Sign in</Link> to see your company.
      </p>
    );
  }
  if (error) return <p className="rounded-2xl border border-[rgb(var(--crit))]/40 bg-[rgb(var(--crit))]/10 p-4 text-sm">{error}</p>;
  if (!data || !me) return <div className="h-72 animate-pulse rounded-3xl bg-[rgb(var(--raised))]" />;

  const admin = data.role !== "employee";
  const pending = data.policies.filter((p) => !p.acknowledged);
  const passed = MODULES.filter((m) => me.training[m.slug]?.passed).length;
  const field =
    "w-full rounded-xl border border-[rgb(var(--edge-strong))] bg-[rgb(var(--ground))] px-3.5 py-2.5 text-sm outline-none focus:border-[rgb(var(--astra))]";

  const publish = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    try {
      await addPolicy(orgId, title, body);
      setTitle("");
      setBody("");
      setWriting(false);
      reload();
    } catch (err) {
      setError(err instanceof AccountFailure ? err.message : "Couldn't publish it.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="mx-auto max-w-4xl space-y-5">
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div className="flex items-center gap-4">
          <OrgLogo name={data.org.name} settings={data.org.settings} size={52} />
          <div>
            <p className="label text-[rgb(var(--astra))]">Your company</p>
            <h1 className="mt-1 text-2xl font-semibold tracking-tight sm:text-3xl">{data.org.name}</h1>
          </div>
        </div>
        {admin && (
          <Link href={`/team/${orgId}`} className="focusable rounded-xl border border-[rgb(var(--edge-strong))] px-4 py-2 text-sm hover:bg-[rgb(var(--raised))]">
            Team dashboard →
          </Link>
        )}
      </header>

      {data.org.settings.welcome && (
        <p className="rise whitespace-pre-wrap rounded-2xl border border-[rgb(var(--astra))]/30 bg-[rgb(var(--astra))]/5 p-4 text-[0.9375rem] leading-relaxed">
          {data.org.settings.welcome}
        </p>
      )}

      {data.org.settings.required.length > 0 && (
        <section className="rounded-3xl border border-[rgb(var(--edge))] bg-[rgb(var(--panel))] p-5">
          <div className="flex flex-wrap items-baseline justify-between gap-2">
            <h2 className="text-lg font-semibold">Required training</h2>
            {data.org.settings.due && (
              <span
                className={`text-sm font-medium ${
                  daysUntil(data.org.settings.due) < 0 ? "text-[rgb(var(--crit))]" : "text-[rgb(var(--muted))]"
                }`}
              >
                {daysUntil(data.org.settings.due) < 0
                  ? `Was due ${new Date(data.org.settings.due + "T00:00").toLocaleDateString()}`
                  : daysUntil(data.org.settings.due) === 0
                    ? "Due today"
                    : `Due in ${daysUntil(data.org.settings.due)} days`}
              </span>
            )}
          </div>
          <ul className="mt-3 space-y-2">
            {MODULES.filter((m) => data.org.settings.required.includes(m.slug)).map((m) => {
              const done = Boolean(me.training[m.slug]?.passed);
              return (
                <li key={m.slug}>
                  <Link
                    href={`/training/${m.slug}`}
                    className="focusable flex items-center gap-3 rounded-xl border border-[rgb(var(--edge))] px-3.5 py-2.5 transition hover:bg-[rgb(var(--raised))]"
                  >
                    <span
                      aria-hidden="true"
                      className={`inline-flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-xs font-semibold ${
                        done ? "bg-[rgb(var(--ok))] text-white" : "bg-[rgb(var(--raised))] text-[rgb(var(--muted))]"
                      }`}
                    >
                      {done ? "✓" : m.level}
                    </span>
                    <span className="min-w-0 flex-1 text-sm">
                      <span className="block font-medium">{m.title}</span>
                      <span className="block text-xs text-[rgb(var(--muted))]">{done ? "Passed" : `${m.minutes} min · not passed yet`}</span>
                    </span>
                    {!done && <span className="text-sm text-[rgb(var(--astra))]">Start →</span>}
                  </Link>
                </li>
              );
            })}
          </ul>
        </section>
      )}

      <div className="grid gap-3 sm:grid-cols-2">
        <Link href="/training" className="focusable lift rounded-2xl border border-[rgb(var(--edge))] bg-[rgb(var(--panel))] p-4">
          <p className="tnum text-3xl font-semibold">
            {passed}
            <span className="text-lg text-[rgb(var(--faint))]">/{MODULES.length}</span>
          </p>
          <p className="text-sm text-[rgb(var(--muted))]">training levels passed · continue →</p>
        </Link>
        <div className="rounded-2xl border border-[rgb(var(--edge))] bg-[rgb(var(--panel))] p-4">
          <p className={`tnum text-3xl font-semibold ${pending.length ? "text-[rgb(var(--warn))]" : "text-[rgb(var(--ok))]"}`}>
            {pending.length}
          </p>
          <p className="text-sm text-[rgb(var(--muted))]">{pending.length === 1 ? "policy" : "policies"} waiting for you to read</p>
        </div>
      </div>

      <section className="rounded-3xl border border-[rgb(var(--edge))] bg-[rgb(var(--panel))] p-5 sm:p-6">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <h2 className="text-lg font-semibold">Security policies</h2>
          {admin && !writing && (
            <button type="button" onClick={() => setWriting(true)} className="focusable rounded-xl bg-[rgb(var(--astra))] px-4 py-2 text-sm font-semibold text-white">
              + Add a policy
            </button>
          )}
        </div>
        {admin && writing && (
          <form onSubmit={publish} className="rise mt-4 space-y-3 rounded-2xl border border-[rgb(var(--astra))]/30 bg-[rgb(var(--astra))]/5 p-4">
            <input className={field} placeholder="Title, e.g. Acceptable use" value={title} onChange={(e) => setTitle(e.target.value)} maxLength={120} required />
            <textarea
              className={`${field} min-h-[12rem] resize-y leading-relaxed`}
              placeholder="Paste the policy text. Members read it here and confirm they have."
              value={body}
              onChange={(e) => setBody(e.target.value)}
              maxLength={20000}
              required
            />
            <div className="flex gap-2">
              <button className="focusable rounded-xl bg-[rgb(var(--astra))] px-4 py-2 text-sm font-semibold text-white disabled:opacity-60" disabled={busy}>
                Publish to the company
              </button>
              <button type="button" onClick={() => setWriting(false)} className="focusable rounded-xl border border-[rgb(var(--edge-strong))] px-4 py-2 text-sm">
                Cancel
              </button>
            </div>
          </form>
        )}
        {data.policies.length === 0 ? (
          <p className="mt-3 text-sm text-[rgb(var(--muted))]">
            {admin
              ? "No policies yet. Add your acceptable use, password or remote-work policy, and every member can read and acknowledge it."
              : "Your company hasn't published any policies yet."}
          </p>
        ) : (
          <ul className="mt-4 space-y-2">
            {data.policies.map((p: Policy) => (
              <li key={p.id} className="overflow-hidden rounded-2xl border border-[rgb(var(--edge))]">
                <button
                  type="button"
                  onClick={() => setOpen(open === p.id ? null : p.id)}
                  aria-expanded={open === p.id}
                  className="focusable flex w-full items-center gap-3 px-4 py-3 text-left hover:bg-[rgb(var(--raised))]"
                >
                  <span
                    aria-hidden="true"
                    className={`inline-flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-xs ${
                      p.acknowledged ? "bg-[rgb(var(--ok))]/15 text-[rgb(var(--ok))]" : "bg-[rgb(var(--warn))]/15 text-[rgb(var(--warn))]"
                    }`}
                  >
                    {p.acknowledged ? "✓" : "!"}
                  </span>
                  <span className="min-w-0 flex-1">
                    <span className="block font-semibold">{p.title}</span>
                    <span className="block text-xs text-[rgb(var(--muted))]">
                      {p.acknowledged ? `You confirmed on ${new Date(p.acknowledged * 1000).toLocaleDateString()}` : "Not read yet"}
                      {p.acks !== undefined && ` · ${p.acks} acknowledged`}
                    </span>
                  </span>
                  <span aria-hidden="true" className="text-[rgb(var(--faint))]">{open === p.id ? "▴" : "▾"}</span>
                </button>
                {open === p.id && (
                  <div className="rise border-t border-[rgb(var(--edge))] px-4 py-4">
                    <div className="max-h-[28rem] overflow-y-auto whitespace-pre-wrap text-sm leading-relaxed text-[rgb(var(--muted))]">{p.body}</div>
                    <div className="mt-4 flex flex-wrap gap-2">
                      {!p.acknowledged && (
                        <button
                          type="button"
                          onClick={() => acknowledgePolicy(orgId, p.id).then(reload)}
                          className="focusable rounded-xl bg-[rgb(var(--ok))] px-4 py-2 text-sm font-semibold text-white"
                        >
                          I have read and will follow this
                        </button>
                      )}
                      {admin && (
                        <button
                          type="button"
                          onClick={() => removePolicy(orgId, p.id).then(reload)}
                          className="focusable rounded-xl px-3 py-2 text-sm text-[rgb(var(--crit))]"
                        >
                          Retire this policy
                        </button>
                      )}
                    </div>
                  </div>
                )}
              </li>
            ))}
          </ul>
        )}
      </section>

      <CompanySignals orgId={orgId} admin={admin} />
    </div>
  );
}
