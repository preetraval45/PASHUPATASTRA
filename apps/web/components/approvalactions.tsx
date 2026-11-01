"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";

import { useAccount } from "@/components/account";
import { AccountFailure, approveAction, denyAction, type PolicyQuestion } from "@/lib/account";

/**
 * Approve or deny the action this panel scored. Only a platform administrator
 * can, as in an ERP where approval is a permission, not a button anyone may
 * press; everyone else sees who may. Actions stay dry-run: approving records
 * the decision in the audit trail and the approval-fatigue measure, and no
 * write reaches a system.
 */
export function ApprovalActions({ question, tier }: { question: PolicyQuestion; tier: string }) {
  const { me, ready } = useAccount();
  const presented = useRef(new Date());
  const [busy, setBusy] = useState(false);
  const [denying, setDenying] = useState(false);
  const [reason, setReason] = useState("");
  const [done, setDone] = useState<{ ok: boolean; text: string } | null>(null);
  useEffect(() => {
    presented.current = new Date();
  }, []);

  if (tier === "autonomous") {
    return <p className="mt-4 text-sm text-[rgb(var(--muted))]">This tier runs without a person. Nothing to approve.</p>;
  }
  if (tier === "denied") {
    return <p className="mt-4 text-sm text-[rgb(var(--muted))]">Denied by policy. No one can approve it.</p>;
  }
  if (!ready) return null;
  if (!me?.platform_admin) {
    return (
      <p className="mt-4 rounded-xl border border-[rgb(var(--edge))] px-4 py-3 text-sm text-[rgb(var(--muted))]">
        Approving is an administrator&apos;s permission.{" "}
        {me ? "Your account doesn't have it." : <><Link href="/login" className="text-[rgb(var(--astra))] underline">Sign in</Link> as an administrator to approve or deny.</>}
      </p>
    );
  }

  const run = async (work: () => Promise<unknown>, ok: string) => {
    setBusy(true);
    try {
      await work();
      setDone({ ok: true, text: ok });
    } catch (e) {
      setDone({ ok: false, text: e instanceof AccountFailure ? e.message : "That didn't go through. Try again." });
    } finally {
      setBusy(false);
    }
  };

  if (done?.ok) {
    return (
      <p role="status" className="rise mt-4 rounded-xl border border-[rgb(var(--ok))]/40 bg-[rgb(var(--ok))]/10 px-4 py-3 text-sm">
        {done.text} It is in the <Link href="/audit" className="underline">audit trail</Link>. Execution stays dry-run.
      </p>
    );
  }

  return (
    <div className="mt-5 border-t border-[rgb(var(--edge))] pt-4">
      <p className="mb-3 text-sm text-[rgb(var(--muted))]">
        You are approving as <strong className="text-[rgb(var(--ink))]">{me.user.name}</strong>, a platform administrator.
      </p>
      {denying ? (
        <form
          className="flex flex-wrap gap-2"
          onSubmit={(e) => {
            e.preventDefault();
            run(() => denyAction(question, reason, presented.current), "Denied, with your reason.");
          }}
        >
          <input
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            required
            maxLength={300}
            placeholder="Why not? (recorded with the decision)"
            className="min-w-0 flex-1 rounded-xl border border-[rgb(var(--edge-strong))] bg-[rgb(var(--ground))] px-3.5 py-2 text-sm outline-none focus:border-[rgb(var(--astra))]"
            autoFocus
          />
          <button disabled={busy} className="focusable rounded-xl bg-[rgb(var(--crit))] px-4 py-2 text-sm font-semibold text-white disabled:opacity-60">
            Deny
          </button>
          <button type="button" onClick={() => setDenying(false)} className="focusable rounded-xl border border-[rgb(var(--edge-strong))] px-4 py-2 text-sm">
            Cancel
          </button>
        </form>
      ) : (
        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            disabled={busy}
            onClick={() => run(() => approveAction(question, presented.current), "Approved.")}
            className="focusable rounded-xl bg-[rgb(var(--ok))] px-5 py-2 text-sm font-semibold text-white disabled:opacity-60"
          >
            {busy ? "Recording…" : "Approve"}
          </button>
          <button
            type="button"
            disabled={busy}
            onClick={() => setDenying(true)}
            className="focusable rounded-xl border border-[rgb(var(--crit))]/50 px-5 py-2 text-sm font-semibold text-[rgb(var(--crit))]"
          >
            Deny…
          </button>
        </div>
      )}
      {done && !done.ok && <p role="alert" className="mt-2 text-sm text-[rgb(var(--crit))]">{done.text}</p>}
    </div>
  );
}
