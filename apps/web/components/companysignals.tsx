"use client";

import { useCallback, useEffect, useState } from "react";

import { API_BASE } from "@/lib/api";
import { AccountFailure, companySignals, createIntakeKey, revokeIntakeKey, type Signal } from "@/lib/account";

/**
 * A company's own alerts (RP-107): what its systems sent to its intake URL, newest first, for every
 * member. Admins connect a system here: a key shown once, the URL, and a working example. Observation
 * only: nothing here acts, so an alert is something to read and investigate, never something that runs.
 */
const TONE: Record<Signal["severity"], string> = {
  critical: "--crit",
  high: "--high",
  medium: "--warn",
  low: "--ok",
  info: "--astra",
};

export function CompanySignals({ orgId, admin }: { orgId: string; admin: boolean }) {
  const [data, setData] = useState<Awaited<ReturnType<typeof companySignals>> | null>(null);
  const [made, setMade] = useState<{ key: string; url: string } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const reload = useCallback(() => {
    companySignals(orgId)
      .then(setData)
      .catch((e) => setError(e instanceof AccountFailure ? e.message : "Couldn't load the alerts."));
  }, [orgId]);

  useEffect(reload, [reload]);

  const act = async (work: () => Promise<void>) => {
    setBusy(true);
    setError(null);
    try {
      await work();
      reload();
    } catch (e) {
      setError(e instanceof AccountFailure ? e.message : "That didn't work. Try again.");
    } finally {
      setBusy(false);
    }
  };

  const signals = data?.signals ?? [];
  const example = made
    ? `curl -X POST ${made.url} \\\n  -H "X-Pashupatastra-Key: ${made.key}" \\\n  -H "Content-Type: application/json" \\\n  -d '{"title": "Impossible travel for ana", "severity": "high", "source": "Okta", "entity": "ana"}'`
    : "";

  return (
    <section className="rounded-3xl border border-[rgb(var(--edge))] bg-[rgb(var(--panel))] p-5">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h2 className="text-lg font-semibold">Alerts from your systems</h2>
        <span className="text-sm text-[rgb(var(--muted))]">
          {signals.length === 0 ? "None yet" : `${signals.length} most recent`}
        </span>
      </div>
      <p className="mt-1 text-sm text-[rgb(var(--muted))]">
        What your company&apos;s own tools send in: a SIEM, cloud alarms, an EDR, or a script. Read and investigated here;
        nothing runs because of an alert.
      </p>

      {admin && (
        <div className="mt-4 rounded-2xl border border-[rgb(var(--edge))] bg-[rgb(var(--ground))] p-4 text-sm">
          <p className="font-semibold">Connect a system</p>
          {made ? (
            <div className="mt-2 space-y-2">
              <p className="text-[rgb(var(--warn))]">Copy the key now: it is shown once, and only its fingerprint is kept.</p>
              <pre className="mono overflow-x-auto whitespace-pre rounded-xl bg-[rgb(var(--raised))] p-3 text-xs">{example}</pre>
            </div>
          ) : (
            <p className="mt-1 text-[rgb(var(--muted))]">
              {data?.intake
                ? `A key ending …${data.intake.end} is active since ${new Date(data.intake.created * 1000).toLocaleDateString()}.`
                : "No key yet. Make one, then point your tool's webhook or alert action at the URL it gives you."}
            </p>
          )}
          <div className="mt-3 flex flex-wrap gap-2">
            <button
              type="button"
              disabled={busy}
              onClick={() =>
                act(async () => {
                  const { key, path } = await createIntakeKey(orgId);
                  setMade({ key, url: `${API_BASE}${path}` });
                })
              }
              className="focusable rounded-xl bg-[rgb(var(--astra))] px-4 py-2 font-semibold text-[rgb(var(--ground))]"
            >
              {data?.intake ? "Replace the key" : "Make an intake key"}
            </button>
            {data?.intake && (
              <button
                type="button"
                disabled={busy}
                onClick={() =>
                  act(async () => {
                    await revokeIntakeKey(orgId);
                    setMade(null);
                  })
                }
                className="focusable rounded-xl px-3 py-2 text-[rgb(var(--crit))]"
              >
                Revoke
              </button>
            )}
          </div>
        </div>
      )}

      {error && <p className="mt-3 text-sm text-[rgb(var(--crit))]">{error}</p>}

      {signals.length > 0 && (
        <ul className="mt-4 divide-y divide-[rgb(var(--edge))]">
          {signals.map((s) => (
            <li key={s.id} className="py-3">
              <div className="flex flex-wrap items-center gap-2 text-xs">
                <span
                  className="rounded-full px-2 py-0.5 font-semibold uppercase tracking-wide"
                  style={{ background: `rgb(var(${TONE[s.severity]}) / 0.15)`, color: `rgb(var(${TONE[s.severity]}))` }}
                >
                  {s.severity}
                </span>
                {s.source && <span className="text-[rgb(var(--muted))]">{s.source}</span>}
                {s.entity && <span className="mono text-[rgb(var(--muted))]">{s.entity}</span>}
                <span className="ml-auto text-[rgb(var(--faint))]">{new Date(s.received * 1000).toLocaleString()}</span>
              </div>
              <p className="mt-1 font-medium">{s.title}</p>
              {s.details && <p className="mt-0.5 whitespace-pre-wrap text-sm text-[rgb(var(--muted))]">{s.details}</p>}
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
