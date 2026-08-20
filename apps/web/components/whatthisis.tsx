import type { Health } from "@/lib/api";

/**
 * What a visitor is actually looking at.
 *
 * Without this the console reads as a live security tool, and it is not one:
 * the incidents are written, no model is answering, nothing is executed, and
 * the whole store is a process that forgets. Each of those was already visible
 * somewhere — a `degraded` chip, a `dry run` badge, provenance on an event —
 * but only to someone who already knew what to look for, which is nobody
 * arriving for the first time.
 *
 * It reads its claims from `/health` rather than asserting them, so it cannot
 * keep saying "nothing executes" after that stops being true.
 */
export function WhatThisIs({ health }: { health: Health }) {
  const stubbed = !health.model.configured;
  const durable = health.audit_storage !== "memory";

  return (
    <details className="panel group open:bg-[rgb(var(--panel))]" open>
      <summary className="focusable cursor-pointer list-none px-5 py-3 text-sm">
        <span className="text-[rgb(var(--ink))]">What you are looking at</span>
        <span className="ml-2 text-xs text-[rgb(var(--muted))]">
          — a demonstration, not a live system
        </span>
      </summary>

      <div className="border-t border-[rgb(var(--edge))] px-5 py-4">
        <p className="max-w-3xl text-sm text-[rgb(var(--muted))]">
          An incident-response console. It shows how a detection becomes a diagnosis,
          how that diagnosis is challenged, and what the policy engine will and will not
          allow in response.
        </p>

        <dl className="mt-4 grid gap-x-8 gap-y-3 text-xs sm:grid-cols-2">
          <div>
            <dt className="text-[rgb(var(--ink))]">The incidents are written</dt>
            <dd className="mt-0.5 text-[rgb(var(--muted))]">
              Three scripted scenarios. Nothing here was observed on a real network, and
              every event says so in its provenance.
            </dd>
          </div>

          <div>
            <dt className="text-[rgb(var(--ink))]">
              {stubbed ? "No model is answering" : `Model: ${health.model.model}`}
            </dt>
            <dd className="mt-0.5 text-[rgb(var(--muted))]">
              {stubbed
                ? `The AI gateway is set to the deterministic stub (${health.model.provider}). The
                   correlation, risk scoring and policy decisions are ordinary code — they
                   never ask a model whether something is safe.`
                : "Reasoning is grounded in stored telemetry; risk and policy remain deterministic."}
            </dd>
          </div>

          <div>
            <dt className="text-[rgb(var(--ink))]">
              {health.dry_run ? "Nothing is executed" : "Live execution is enabled"}
            </dt>
            <dd className="mt-0.5 text-[rgb(var(--muted))]">
              {health.dry_run
                ? `Every action is scored, tiered and shown with its rollback — and then not
                   performed. There is no host to isolate and no account to disable.`
                : "Actions reach real systems once authorised."}
            </dd>
          </div>

          <div>
            <dt className="text-[rgb(var(--ink))]">
              {durable ? "State is durable" : "State is forgotten"}
            </dt>
            <dd className="mt-0.5 text-[rgb(var(--muted))]">
              {durable
                ? "Incidents and the audit trail are persisted."
                : `Everything lives in the server process. That is why the header says memory
                   only — an audit trail that does not survive a restart is not an audit
                   trail, so it reports itself as degraded rather than pretending.`}
            </dd>
          </div>
        </dl>

        <p className="mt-4 max-w-3xl text-xs text-[rgb(var(--faint))]">
          The reasoning is the point. Each scenario carries an explanation that looks
          right and turns out to be wrong, and the evidence that rules it out is cited
          and can be clicked.
        </p>
      </div>
    </details>
  );
}
