"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";

import { initials, useAccount } from "@/components/account";
import { CustomizePanel } from "@/components/companysettings";
import { OrgLogo } from "@/components/orgbrand";
import { daysUntil } from "@/lib/duedate";
import { AccountFailure, adminResetLink, companyMembers, newInvite, removeMember, setRole, type Member } from "@/lib/account";
import { MODULES } from "@/lib/training";

/**
 * A company's training at a glance, for its owner and admins: who has joined,
 * which of the nine levels each person has passed, scores, and who has gone
 * quiet. The invite code and link are here to bring the rest of the team in.
 */
const DAY = 86_400;

function since(seconds: number | null): string {
  if (!seconds) return "never";
  const d = Math.floor((Date.now() / 1000 - seconds) / DAY);
  return d <= 0 ? "today" : d === 1 ? "yesterday" : `${d} days ago`;
}

function csv(rows: Member[]): string {
  const head = ["Name", "Email", "Role", "Levels passed", ...MODULES.map((m) => `L${m.level} ${m.title}`), "Average best score", "Last active"];
  const quote = (v: string) => `"${v.replace(/"/g, '""')}"`;
  const lines = rows.map((m) =>
    [
      m.name,
      m.email ?? "",
      m.role,
      String(m.passed.length),
      ...MODULES.map((x) => (m.passed.includes(x.slug) ? "passed" : "")),
      m.average === null ? "" : `${Math.round(m.average * 100)}%`,
      m.last_active ? new Date(m.last_active * 1000).toISOString().slice(0, 10) : "",
    ]
      .map(quote)
      .join(","),
  );
  return [head.map(quote).join(","), ...lines].join("\n");
}

export function TeamDashboard({ orgId }: { orgId: string }) {
  const { me, ready } = useAccount();
  const [data, setData] = useState<Awaited<ReturnType<typeof companyMembers>> | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState<string | null>(null);
  const [filter, setFilter] = useState<"all" | "behind" | "done">("all");
  const [resetFor, setResetFor] = useState<{ id: string; link: string } | null>(null);

  const reload = useCallback(() => {
    companyMembers(orgId)
      .then(setData)
      .catch((e) => setError(e instanceof AccountFailure ? e.message : "Couldn't load the team."));
  }, [orgId]);

  useEffect(() => {
    if (ready && me) reload();
  }, [ready, me, reload]);

  const isOwner = me?.orgs.find((o) => o.id === orgId)?.role === "owner";
  const members = data?.members ?? [];
  const stats = useMemo(() => {
    const done = members.filter((m) => m.passed.length === MODULES.length).length;
    const quiet = members.filter((m) => !m.last_active || Date.now() / 1000 - m.last_active > 14 * DAY).length;
    const levels = members.length ? members.reduce((s, m) => s + m.passed.length, 0) / members.length : 0;
    const required = data?.org.settings.required ?? [];
    const due = data?.org.settings.due ?? null;
    const requiredDone = required.length ? members.filter((m) => m.required_passed >= required.length).length : 0;
    const overdue = required.length && due && daysUntil(due) < 0 ? members.length - requiredDone : 0;
    return { done, quiet, levels, required, due, requiredDone, overdue };
  }, [members, data]);
  const shown = members.filter((m) =>
    filter === "done" ? m.passed.length === MODULES.length : filter === "behind" ? m.passed.length < MODULES.length : true,
  );

  if (ready && !me) {
    return (
      <p className="text-sm">
        <Link href={`/login?next=/team/${orgId}`} className="text-[rgb(var(--astra))] underline">Sign in</Link> to see your team.
      </p>
    );
  }
  if (error) return <p className="rounded-2xl border border-[rgb(var(--crit))]/40 bg-[rgb(var(--crit))]/10 p-4 text-sm">{error}</p>;
  if (!data) return <div className="h-72 animate-pulse rounded-3xl bg-[rgb(var(--raised))]" />;

  const link = typeof window === "undefined" ? "" : `${window.location.origin}/signup?invite=${data.org.invite}`;
  const copy = async (text: string, what: string) => {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(what);
      setTimeout(() => setCopied(null), 1600);
    } catch {
      // Clipboard blocked: the text is on screen to copy by hand.
    }
  };
  const download = () => {
    const blob = new Blob([csv(members)], { type: "text/csv" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = `${data.org.name.replace(/[^\w-]+/g, "-")}-training.csv`;
    a.click();
    URL.revokeObjectURL(a.href);
  };
  const tile = "rounded-2xl border border-[rgb(var(--edge))] bg-[rgb(var(--panel))] p-4";

  return (
    <div className="space-y-5">
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div className="flex items-center gap-4">
          <OrgLogo name={data.org.name} settings={data.org.settings} size={52} />
          <div>
            <p className="label text-[rgb(var(--astra))]">Team dashboard</p>
            <h1 className="mt-1 text-2xl font-semibold tracking-tight sm:text-3xl">{data.org.name}</h1>
          </div>
        </div>
        <span className="flex gap-2">
          <Link href={`/company/${orgId}`} className="focusable rounded-xl border border-[rgb(var(--edge-strong))] px-4 py-2 text-sm transition hover:bg-[rgb(var(--raised))]">
            Policies
          </Link>
          <button type="button" onClick={download} className="focusable rounded-xl border border-[rgb(var(--edge-strong))] px-4 py-2 text-sm transition hover:bg-[rgb(var(--raised))]">
            ↓ Export CSV
          </button>
        </span>
      </header>

      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <div className={tile}>
          <p className="tnum text-3xl font-semibold">{members.length}</p>
          <p className="text-sm text-[rgb(var(--muted))]">people in the workspace</p>
        </div>
        {stats.required.length > 0 ? (
          <div className={tile}>
            <p className="tnum text-3xl font-semibold text-[rgb(var(--ok))]">
              {stats.requiredDone}
              <span className="text-lg text-[rgb(var(--faint))]">/{members.length}</span>
            </p>
            <p className="text-sm text-[rgb(var(--muted))]">
              finished required training
              {stats.due && (
                <span className={stats.overdue ? " text-[rgb(var(--crit))]" : ""}>
                  {" "}· {daysUntil(stats.due) < 0 ? `${stats.overdue} overdue` : `due in ${daysUntil(stats.due)} days`}
                </span>
              )}
            </p>
          </div>
        ) : (
          <div className={tile}>
            <p className="tnum text-3xl font-semibold text-[rgb(var(--ok))]">{stats.done}</p>
            <p className="text-sm text-[rgb(var(--muted))]">finished all nine levels</p>
          </div>
        )}
        <div className={tile}>
          <p className="tnum text-3xl font-semibold">{stats.levels.toFixed(1)}</p>
          <p className="text-sm text-[rgb(var(--muted))]">levels passed on average</p>
        </div>
        <div className={tile}>
          <p className="tnum text-3xl font-semibold text-[rgb(var(--warn))]">{stats.quiet}</p>
          <p className="text-sm text-[rgb(var(--muted))]">quiet for 14+ days</p>
        </div>
      </div>

      <section className="rounded-3xl border border-[rgb(var(--astra))]/30 bg-[rgb(var(--astra))]/5 p-5">
        <h2 className="font-semibold">Invite your team</h2>
        <p className="mt-1 text-sm text-[rgb(var(--muted))]">
          Share the link, or the code to enter under Account. Anyone with it can join as an employee.
        </p>
        <div className="mt-3 flex flex-wrap items-center gap-2">
          <span className="mono rounded-xl border border-[rgb(var(--edge-strong))] bg-[rgb(var(--ground))] px-4 py-2 text-lg font-semibold tracking-widest">
            {data.org.invite}
          </span>
          <button type="button" onClick={() => copy(data.org.invite, "code")} className="focusable rounded-xl border border-[rgb(var(--edge-strong))] px-3 py-2 text-sm">
            {copied === "code" ? "Copied ✓" : "Copy code"}
          </button>
          <button type="button" onClick={() => copy(link, "link")} className="focusable rounded-xl bg-[rgb(var(--astra))] px-3 py-2 text-sm font-semibold text-white">
            {copied === "link" ? "Copied ✓" : "Copy invite link"}
          </button>
          <button
            type="button"
            onClick={() => newInvite(orgId).then(reload)}
            className="focusable rounded-xl px-3 py-2 text-sm text-[rgb(var(--muted))] hover:text-[rgb(var(--ink))]"
            title="The old code stops working"
          >
            New code
          </button>
        </div>
      </section>

      <CustomizePanel orgId={orgId} name={data.org.name} settings={data.org.settings} onSaved={reload} />

      <section className="overflow-hidden rounded-3xl border border-[rgb(var(--edge))] bg-[rgb(var(--panel))]">
        <div className="flex flex-wrap items-center gap-2 border-b border-[rgb(var(--edge))] px-4 py-3">
          <h2 className="mr-auto font-semibold">People</h2>
          {(["all", "behind", "done"] as const).map((f) => (
            <button
              key={f}
              type="button"
              onClick={() => setFilter(f)}
              aria-pressed={filter === f}
              className={`focusable rounded-full px-3 py-1 text-xs font-medium ${
                filter === f ? "bg-[rgb(var(--astra))] text-white" : "border border-[rgb(var(--edge))] text-[rgb(var(--muted))]"
              }`}
            >
              {f === "all" ? "Everyone" : f === "behind" ? "Still training" : "Finished"}
            </button>
          ))}
        </div>
        <ul className="divide-y divide-[rgb(var(--edge))]">
          {shown.map((m) => (
            <li key={m.id} className="flex flex-wrap items-center gap-3 px-4 py-3">
              <span className="inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-[rgb(var(--raised))] text-xs font-bold">
                {initials(m.name)}
              </span>
              <span className="min-w-[10rem] flex-1">
                <span className="block font-medium">
                  {m.name}
                  {m.id === me?.user.id && <span className="text-xs text-[rgb(var(--faint))]"> (you)</span>}
                </span>
                <span className="block text-xs text-[rgb(var(--muted))]">
                  {m.email ?? "guest"} · {m.role} · active {since(m.last_active)}
                </span>
                {stats.required.length > 0 && (
                  <span
                    className={`mt-1 inline-block rounded-full px-2 py-0.5 text-[11px] font-medium ${
                      m.required_passed >= stats.required.length
                        ? "bg-[rgb(var(--ok))]/15 text-[rgb(var(--ok))]"
                        : stats.due && daysUntil(stats.due) < 0
                          ? "bg-[rgb(var(--crit))]/15 text-[rgb(var(--crit))]"
                          : "bg-[rgb(var(--raised))] text-[rgb(var(--muted))]"
                    }`}
                  >
                    required {m.required_passed}/{stats.required.length}
                    {m.required_passed < stats.required.length && stats.due && daysUntil(stats.due) < 0 ? " · overdue" : ""}
                  </span>
                )}
              </span>
              <span className="flex gap-1" aria-label={`${m.passed.length} of ${MODULES.length} levels passed`}>
                {MODULES.map((x) => (
                  <span
                    key={x.slug}
                    title={`Level ${x.level}: ${x.title}`}
                    className={`h-6 w-3 rounded-sm ${m.passed.includes(x.slug) ? "bg-[rgb(var(--ok))]" : "bg-[rgb(var(--raised))]"}`}
                  />
                ))}
              </span>
              <span className="tnum w-14 text-right text-sm">{m.average === null ? "—" : `${Math.round(m.average * 100)}%`}</span>
              <span className="tnum w-20 text-right text-xs text-[rgb(var(--muted))]" title="Company policies this person has acknowledged">
                {m.policies_acknowledged} {m.policies_acknowledged === 1 ? "policy" : "policies"}
              </span>
              {m.provider === "email" && m.id !== me?.user.id && m.role !== "owner" && (
                <button
                  type="button"
                  onClick={() => adminResetLink(orgId, m.id).then((r) => setResetFor({ id: m.id, link: r.link })).catch((e) => setError(e instanceof AccountFailure ? e.message : "Couldn't make a reset link."))}
                  className="focusable rounded-lg border border-[rgb(var(--edge))] px-2 py-1 text-xs"
                >
                  Reset password
                </button>
              )}
              {resetFor?.id === m.id && (
                <span className="rise flex w-full flex-wrap items-center gap-2 rounded-xl border border-[rgb(var(--astra))]/30 bg-[rgb(var(--astra))]/5 p-2.5 text-xs">
                  <span className="text-[rgb(var(--muted))]">Give {m.name} this link. It works once, for one hour:</span>
                  <code className="mono min-w-0 flex-1 truncate">{resetFor.link}</code>
                  <button type="button" onClick={() => copy(resetFor.link, `reset-${m.id}`)} className="focusable rounded-lg bg-[rgb(var(--astra))] px-2.5 py-1 font-semibold text-white">
                    {copied === `reset-${m.id}` ? "Copied ✓" : "Copy"}
                  </button>
                </span>
              )}
              {isOwner && m.role !== "owner" && (
                <span className="flex gap-1">
                  <button
                    type="button"
                    onClick={() => setRole(orgId, m.id, m.role === "admin" ? "employee" : "admin").then(reload)}
                    className="focusable rounded-lg border border-[rgb(var(--edge))] px-2 py-1 text-xs"
                  >
                    {m.role === "admin" ? "Make employee" : "Make admin"}
                  </button>
                  <button
                    type="button"
                    onClick={() => removeMember(orgId, m.id).then(reload)}
                    className="focusable rounded-lg px-2 py-1 text-xs text-[rgb(var(--crit))]"
                    aria-label={`Remove ${m.name}`}
                  >
                    Remove
                  </button>
                </span>
              )}
            </li>
          ))}
          {shown.length === 0 && <li className="px-4 py-6 text-sm text-[rgb(var(--faint))]">Nobody here yet.</li>}
        </ul>
      </section>
      <p className="text-xs text-[rgb(var(--faint))]">
        Scores are marked in each person's browser: read them as their own training record, not a supervised exam.
      </p>
    </div>
  );
}
