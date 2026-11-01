"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { initials, useAccount } from "@/components/account";
import { accentVar } from "@/components/orgbrand";
import { AccountFailure, adminOverview, type AdminOverview } from "@/lib/account";

/**
 * The platform's administration, as an ERP's Settings › Users & Companies: every
 * account and every company workspace. Platform administrators only; the API
 * refuses everyone else, so this page only decides what to say to them.
 */
export function AdminConsole() {
  const { me, ready } = useAccount();
  const [data, setData] = useState<AdminOverview | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [tab, setTab] = useState<"users" | "companies">("users");
  const [find, setFind] = useState("");

  useEffect(() => {
    if (ready && me?.platform_admin) {
      adminOverview()
        .then(setData)
        .catch((e) => setError(e instanceof AccountFailure ? e.message : "Couldn't load."));
    }
  }, [ready, me]);

  if (!ready) return null;
  if (!me?.platform_admin) {
    return (
      <div className="mx-auto max-w-lg rounded-3xl border border-[rgb(var(--edge))] bg-[rgb(var(--panel))] p-6 text-center">
        <h1 className="text-xl font-semibold">Administrators only</h1>
        <p className="mt-2 text-sm text-[rgb(var(--muted))]">
          {me ? "Your account isn't a platform administrator." : "Sign in with an administrator account."}
        </p>
        {!me && (
          <Link href="/login?next=/admin" className="focusable mt-4 inline-block rounded-xl bg-[rgb(var(--astra))] px-4 py-2 text-sm font-semibold text-white">
            Sign in
          </Link>
        )}
      </div>
    );
  }
  if (error) return <p className="rounded-2xl border border-[rgb(var(--crit))]/40 bg-[rgb(var(--crit))]/10 p-4 text-sm">{error}</p>;
  if (!data) return <div className="h-72 animate-pulse rounded-3xl bg-[rgb(var(--raised))]" />;

  const q = find.trim().toLowerCase();
  const users = data.users.filter((u) => !q || `${u.name} ${u.email ?? ""} ${u.id}`.toLowerCase().includes(q));
  const companies = data.companies.filter((c) => !q || `${c.name} ${c.id}`.toLowerCase().includes(q));
  const when = (t: number | null) => (t ? new Date(t * 1000).toLocaleDateString() : "—");
  const counts = {
    email: data.users.filter((u) => u.provider === "email").length,
    guest: data.users.filter((u) => u.provider === "guest").length,
  };
  const tile = "rounded-2xl border border-[rgb(var(--edge))] bg-[rgb(var(--panel))] p-4";

  return (
    <div className="space-y-5">
      <header>
        <p className="label text-[rgb(var(--astra))]">Settings</p>
        <h1 className="mt-1 text-2xl font-semibold tracking-tight sm:text-3xl">Users &amp; companies</h1>
      </header>
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <div className={tile}>
          <p className="tnum text-3xl font-semibold">{data.users.length}</p>
          <p className="text-sm text-[rgb(var(--muted))]">accounts</p>
        </div>
        <div className={tile}>
          <p className="tnum text-3xl font-semibold">{counts.email}</p>
          <p className="text-sm text-[rgb(var(--muted))]">with email sign-in</p>
        </div>
        <div className={tile}>
          <p className="tnum text-3xl font-semibold">{counts.guest}</p>
          <p className="text-sm text-[rgb(var(--muted))]">guests</p>
        </div>
        <div className={tile}>
          <p className="tnum text-3xl font-semibold">{data.companies.length}</p>
          <p className="text-sm text-[rgb(var(--muted))]">company workspaces</p>
        </div>
      </div>

      <section className="overflow-hidden rounded-3xl border border-[rgb(var(--edge))] bg-[rgb(var(--panel))]">
        <div className="flex flex-wrap items-center gap-2 border-b border-[rgb(var(--edge))] px-4 py-3">
          {(["users", "companies"] as const).map((t) => (
            <button
              key={t}
              type="button"
              onClick={() => setTab(t)}
              aria-pressed={tab === t}
              className={`focusable rounded-full px-3.5 py-1.5 text-sm font-medium ${
                tab === t ? "bg-[rgb(var(--astra))] text-white" : "text-[rgb(var(--muted))] hover:bg-[rgb(var(--raised))]"
              }`}
            >
              {t === "users" ? `Users (${data.users.length})` : `Companies (${data.companies.length})`}
            </button>
          ))}
          <input
            value={find}
            onChange={(e) => setFind(e.target.value)}
            placeholder="Search name, email or id"
            className="ml-auto w-full max-w-xs rounded-lg border border-[rgb(var(--edge))] bg-[rgb(var(--ground))] px-3 py-1.5 text-sm outline-none focus:border-[rgb(var(--astra))]/60"
          />
        </div>
        <div className="overflow-x-auto">
          {tab === "users" ? (
            <table className="w-full text-sm">
              <thead className="text-left text-xs text-[rgb(var(--muted))]">
                <tr>
                  <th className="px-4 py-2 font-medium">Name</th>
                  <th className="px-4 py-2 font-medium">Email</th>
                  <th className="px-4 py-2 font-medium">Sign-in</th>
                  <th className="px-4 py-2 font-medium">Joined</th>
                  <th className="px-4 py-2 font-medium">Account id</th>
                </tr>
              </thead>
              <tbody>
                {users.map((u) => (
                  <tr key={u.id} className="border-t border-[rgb(var(--edge))]">
                    <td className="px-4 py-2.5">
                      <span className="flex items-center gap-2">
                        <span className="inline-flex h-7 w-7 items-center justify-center rounded-full bg-[rgb(var(--raised))] text-[11px] font-bold">{initials(u.name)}</span>
                        {u.name}
                        {u.admin && <span className="rounded-full bg-[rgb(var(--astra))]/15 px-2 py-0.5 text-[10px] font-semibold text-[rgb(var(--astra))]">ADMIN</span>}
                      </span>
                    </td>
                    <td className="px-4 py-2.5 text-[rgb(var(--muted))]">{u.email ?? "—"}</td>
                    <td className="px-4 py-2.5 text-[rgb(var(--muted))]">{u.provider}</td>
                    <td className="tnum px-4 py-2.5 text-[rgb(var(--muted))]">{when(u.created)}</td>
                    <td className="mono px-4 py-2.5 text-xs text-[rgb(var(--faint))]">{u.id}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <table className="w-full text-sm">
              <thead className="text-left text-xs text-[rgb(var(--muted))]">
                <tr>
                  <th className="px-4 py-2 font-medium">Company</th>
                  <th className="px-4 py-2 text-right font-medium">Members</th>
                  <th className="px-4 py-2 font-medium">Created</th>
                  <th className="px-4 py-2 font-medium">Id</th>
                </tr>
              </thead>
              <tbody>
                {companies.map((c) => (
                  <tr key={c.id} className="border-t border-[rgb(var(--edge))]">
                    <td className="px-4 py-2.5">
                      <span className="flex items-center gap-2">
                        <span aria-hidden="true" className="h-3 w-3 rounded-full" style={{ background: `rgb(${accentVar(c.accent)})` }} />
                        {c.name}
                      </span>
                    </td>
                    <td className="tnum px-4 py-2.5 text-right">{c.members}</td>
                    <td className="tnum px-4 py-2.5 text-[rgb(var(--muted))]">{when(c.created)}</td>
                    <td className="mono px-4 py-2.5 text-xs text-[rgb(var(--faint))]">{c.id}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </section>
    </div>
  );
}
