import { Badge, Ident, Panel, statusForRisk, type Status } from "@/components/ui";
import type { Verdict } from "@/lib/api";

const TIER_LABEL: Record<string, { label: string; status: Status; explain: string }> = {
  autonomous: {
    label: "Autonomous",
    status: "ok",
    explain: "An agent may execute this without asking.",
  },
  approval: {
    label: "Approval required",
    status: "warning",
    explain: "An operator must authorize this before it runs.",
  },
  senior: {
    label: "Senior approval",
    status: "high",
    explain: "A senior operator must authorize this before it runs.",
  },
  denied: {
    label: "Never autonomous",
    status: "critical",
    explain: "There is no path to automatic execution for this action.",
  },
};

/**
 * The approval surface.
 *
 * The design problem here is approval fatigue. An operator shown a plausible
 * plan and a green button will click it, and a rubber stamp is indistinguishable
 * from no policy at all. So this panel leads with what the action will *do* and
 * who it will *affect* — and shows the full risk arithmetic, including every
 * adjustment that pushed it up a tier. Someone approving should be able to say
 * why it needed approving.
 *
 * The dashboard never computes any of these numbers. They come from the verdict,
 * because a second implementation would be a second answer to "how dangerous is
 * this?".
 */
export function VerdictPanel({
  verdict,
  blastRadius,
  affectedUsers,
  expectedPostState,
  rollback,
}: {
  verdict: Verdict;
  blastRadius?: number;
  affectedUsers?: number;
  expectedPostState?: Record<string, string>;
  rollback?: string | null;
}) {
  const tier = TIER_LABEL[verdict.tier] ?? TIER_LABEL.denied;
  const denied = verdict.tier === "denied";

  return (
    <Panel
      title="Authorization"
      aside={<Badge status={tier.status}>{tier.label}</Badge>}
      className={denied ? "border-[rgb(var(--crit))]/30" : ""}
    >
      <p className="text-sm">
        <Ident>{verdict.action_id}</Ident>{" "}
        <span className="text-[rgb(var(--muted))]">— {tier.explain}</span>
      </p>

      {verdict.denial_reason && (
        <p className="mt-3 text-sm text-[rgb(var(--crit))]">{verdict.denial_reason}</p>
      )}

      <div className="mt-5 grid gap-5 sm:grid-cols-3">
        <div>
          <div className="label">Effective risk</div>
          <div
            className={`tnum mt-1 text-2xl font-semibold ${
              statusForRisk(verdict.effective_risk) === "ok"
                ? "text-[rgb(var(--ok))]"
                : statusForRisk(verdict.effective_risk) === "warning"
                  ? "text-[rgb(var(--warn))]"
                  : statusForRisk(verdict.effective_risk) === "high"
                    ? "text-[rgb(var(--high))]"
                    : "text-[rgb(var(--crit))]"
            }`}
          >
            {verdict.effective_risk}
          </div>
          <div className="mt-1 text-xs text-[rgb(var(--faint))]">
            base {verdict.base_risk}
          </div>
        </div>

        <div>
          <div className="label">Blast radius</div>
          <div className="tnum mt-1 text-2xl font-semibold">{blastRadius ?? "—"}</div>
          <div className="mt-1 text-xs text-[rgb(var(--faint))]">
            {affectedUsers != null ? `~${affectedUsers.toLocaleString()} users` : "entities"}
          </div>
        </div>

        <div>
          <div className="label">Rollback</div>
          <div className="mono mt-1 text-sm">{rollback ?? "none"}</div>
          <div className="mt-1 text-xs text-[rgb(var(--faint))]">
            {rollback ? "tested and available" : "no way back — cannot be autonomous"}
          </div>
        </div>
      </div>

      {/* The arithmetic, in full. Someone approving should be able to say why
          it needed approving. */}
      {verdict.adjustments.length > 0 && (
        <div className="mt-6 border-t border-[rgb(var(--edge))] pt-4">
          <h3 className="label">Why the risk rose</h3>
          <ul className="mt-3 space-y-1 text-sm">
            <li className="flex items-baseline justify-between gap-4 text-[rgb(var(--muted))]">
              <span>base risk of {verdict.action_id}</span>
              <span className="tnum">{verdict.base_risk}</span>
            </li>
            {verdict.adjustments.map((adjustment) => (
              <li key={adjustment.reason} className="flex items-baseline justify-between gap-4">
                <span className="text-[rgb(var(--muted))]">{adjustment.reason}</span>
                <span className="tnum text-[rgb(var(--warn))]">+{adjustment.delta}</span>
              </li>
            ))}
            <li className="flex items-baseline justify-between gap-4 border-t border-[rgb(var(--edge))] pt-1 font-medium">
              <span>effective risk</span>
              <span className="tnum">{verdict.effective_risk}</span>
            </li>
          </ul>
          <p className="mt-3 text-xs text-[rgb(var(--faint))]">
            Adjustments only ever raise risk. An action cannot argue its way into a lower
            tier.
          </p>
        </div>
      )}

      {expectedPostState && Object.keys(expectedPostState).length > 0 && (
        <div className="mt-6 border-t border-[rgb(var(--edge))] pt-4">
          <h3 className="label">What success will look like</h3>
          <ul className="mono mt-3 space-y-1 text-xs">
            {Object.entries(expectedPostState).map(([key, value]) => (
              <li key={key} className="flex items-baseline justify-between gap-4">
                <span className="text-[rgb(var(--muted))]">{key}</span>
                <span>{value}</span>
              </li>
            ))}
          </ul>
          <p className="mt-3 text-xs text-[rgb(var(--faint))]">
            Declared before execution. Verification compares observed state to this, and a
            check with no observation counts as a failure — &ldquo;don&rsquo;t know&rdquo;
            is never recorded as success.
          </p>
        </div>
      )}

      <div className="mt-6 flex flex-wrap items-center gap-3 border-t border-[rgb(var(--edge))] pt-4">
        {verdict.required_approvers.length > 0 && (
          <span className="text-xs text-[rgb(var(--muted))]">
            requires: <span className="mono">{verdict.required_approvers.join(", ")}</span>
          </span>
        )}
        {verdict.expires_at && (
          <span className="text-xs text-[rgb(var(--faint))]">
            verdict expires — a stale approval cannot be replayed against changed state
          </span>
        )}
      </div>
    </Panel>
  );
}
