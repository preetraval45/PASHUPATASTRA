import Link from "next/link";
import { getHealth, getIncidents } from "@/lib/api";

export const dynamic = "force-dynamic";

export default async function OverviewPage() {
  const [health, incidents] = await Promise.all([getHealth(), getIncidents()]);
  const open = (incidents ?? []).filter((i) => i.state !== "resolved");

  return (
    <div className="space-y-10">
      <section>
        <h1 className="text-2xl font-semibold">Overview</h1>
        <p className="mt-1 text-sm text-[rgb(var(--muted))]">
          System state, open incidents, and the autonomy posture currently in force.
        </p>
      </section>

      {!health && (
        <div className="panel border-amber-500/30 bg-amber-500/5 p-4 text-sm text-amber-300">
          API unreachable. Start it with{" "}
          <code className="mono">uvicorn app.main:app --reload</code> in{" "}
          <code className="mono">services/api</code>.
        </div>
      )}

      <section className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Stat label="Open incidents" value={open.length} />
        <Stat
          label="Users affected"
          value={open.reduce((n, i) => n + i.impact.estimated_users_affected, 0)}
        />
        <Stat label="Environment" value={health?.environment ?? "—"} />
        <Stat
          label="Execution mode"
          value={health ? (health.dry_run ? "Dry run" : "Live") : "—"}
          tone={health && !health.dry_run ? "warn" : "ok"}
        />
      </section>

      <section className="space-y-3">
        <h2 className="label">Open incidents</h2>
        {open.length === 0 ? (
          <div className="panel p-6 text-sm text-[rgb(var(--muted))]">
            No open incidents.
          </div>
        ) : (
          open.map((incident) => (
            <Link
              key={incident.id}
              href={`/incidents`}
              className="panel block p-5 transition hover:border-[rgb(var(--astra))]/40"
            >
              <div className="flex flex-wrap items-center gap-3">
                <span className="mono text-sm">{incident.id}</span>
                <span className="rounded border border-rose-500/30 bg-rose-500/10 px-2 py-0.5 text-[11px] uppercase tracking-wide text-rose-300">
                  {incident.severity}
                </span>
                <span className="text-[11px] uppercase tracking-wide text-[rgb(var(--muted))]">
                  {incident.state.replace(/_/g, " ")}
                </span>
              </div>
              <p className="mt-3 text-sm">
                {incident.hypotheses[0]?.statement ?? "Diagnosis pending."}
              </p>
              <div className="mt-3 flex gap-6 text-xs text-[rgb(var(--muted))]">
                <span>
                  Root cause probability{" "}
                  <span className="text-[rgb(var(--ink))]">
                    {Math.round((incident.hypotheses[0]?.confidence ?? 0) * 100)}%
                  </span>
                </span>
                <span>
                  Users{" "}
                  <span className="text-[rgb(var(--ink))]">
                    {incident.impact.estimated_users_affected.toLocaleString()}
                  </span>
                </span>
                <span>
                  Blast radius{" "}
                  <span className="text-[rgb(var(--ink))]">
                    {incident.impact.blast_radius_entities} entities
                  </span>
                </span>
              </div>
            </Link>
          ))
        )}
      </section>

      <section className="panel p-5">
        <h2 className="label">The loop</h2>
        <div className="mono mt-3 flex flex-wrap gap-x-2 gap-y-1 text-xs text-[rgb(var(--muted))]">
          {["Observe", "Understand", "Predict", "Decide", "Act", "Verify", "Learn"].map(
            (stage, index, all) => (
              <span key={stage}>
                <span className="text-[rgb(var(--ink))]">{stage}</span>
                {index < all.length - 1 && <span className="px-1">→</span>}
              </span>
            ),
          )}
        </div>
      </section>
    </div>
  );
}

function Stat({
  label,
  value,
  tone = "ok",
}: {
  label: string;
  value: string | number;
  tone?: "ok" | "warn";
}) {
  return (
    <div className="panel p-4">
      <div className="label">{label}</div>
      <div
        className={`mt-2 text-2xl font-semibold ${
          tone === "warn" ? "text-amber-400" : "text-[rgb(var(--ink))]"
        }`}
      >
        {typeof value === "number" ? value.toLocaleString() : value}
      </div>
    </div>
  );
}
