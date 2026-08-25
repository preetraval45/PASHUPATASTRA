import { Badge, Ident, Panel, STATUS, statusForRisk, type Status } from "@/components/ui";
import {
  FACTOR_LABEL,
  riskBand,
  tierLabel,
  type PolicyModel,
  type Tier,
  type TierStep,
  type Verdict,
} from "@/lib/api";

/** What each tier means for the person reading it. The tier's *name* is not
 *  here — `tierLabel` already holds it, and two spellings of "senior approval"
 *  is one more than a policy engine should have. */
const TIER: Record<Tier, { status: Status; explain: string }> = {
  autonomous: { status: "ok", explain: "An agent may execute this without asking." },
  approval: { status: "warning", explain: "An operator must authorize this before it runs." },
  senior: { status: "high", explain: "A senior operator must authorize this before it runs." },
  denied: {
    status: "critical",
    explain: "There is no path to automatic execution for this action.",
  },
};

/**
 * Where this action landed on the autonomy scale, and where its score alone
 * would have put it.
 *
 * Drawn rather than named because the interesting fact is usually the gap. An
 * action that scores in the autonomous band and still needs an operator is the
 * case a number cannot explain, and a badge reading "approval required" beside
 * a risk of 12 reads as a bug in the arithmetic.
 *
 * The tiers, their order and their bands come from `/policy/model` — the table
 * the engine itself branches on. Four cells typed in here would be a second
 * answer to "what are the tiers", and on the day they disagreed the wrong one
 * would be the one an operator was looking at while deciding.
 *
 * Position, name and marker carry the state. Colour only agrees with them:
 * senior and denied share the ▲ glyph, so the glyph alone never has to.
 */
function Scale({
  tiers,
  landed,
  fromScore,
}: {
  tiers: PolicyModel["tiers"];
  landed: Tier;
  fromScore: Tier | null;
}) {
  return (
    <ol className="mt-5 grid grid-cols-2 gap-2 sm:grid-cols-4">
      {tiers.map(({ tier, min_risk, max_risk }) => {
        const here = tier === landed;
        const scored = tier === fromScore && !here;
        const s = STATUS[TIER[tier].status];
        return (
          <li
            key={tier}
            aria-current={here ? "step" : undefined}
            className={`rounded border px-3 py-2 ${
              here
                ? `border-2 ${s.ring} ${s.text}`
                : scored
                  ? "border-dashed border-[rgb(var(--edge-strong))] text-[rgb(var(--muted))]"
                  : "border-[rgb(var(--edge))] text-[rgb(var(--faint))]"
            }`}
          >
            <div className="flex items-baseline gap-1.5 text-sm">
              <span aria-hidden="true">{s.glyph}</span>
              <span className={here ? "font-semibold" : ""}>{tierLabel(tier)}</span>
            </div>
            {/* Lifted off `--faint` in the marked cell: that cell is tinted, and
                faint-on-tint measured 4.25:1 against the 4.5 AA floor. */}
            <div
              className={`tnum mt-0.5 text-xs ${
                here ? "text-[rgb(var(--muted))]" : "text-[rgb(var(--faint))]"
              }`}
            >
              risk {min_risk}&ndash;{max_risk}
            </div>
            <div className="mt-1 text-xs">
              {here ? (
                <span className="font-medium">&#9654; this action</span>
              ) : scored ? (
                <span>the score alone</span>
              ) : (
                <span className="invisible" aria-hidden="true">
                  &#9654; this action
                </span>
              )}
            </div>
          </li>
        );
      })}
    </ol>
  );
}

/**
 * Why the tier is the tier, in the engine's own words.
 *
 * Each line is emitted by the branch that applied it, carrying the numbers that
 * branch tested. The panel decides nothing here and could not: it holds no copy
 * of the thresholds it could disagree with.
 */
function WhyThisTier({ steps }: { steps: TierStep[] }) {
  return (
    <div className="mt-6 border-t border-[rgb(var(--edge))] pt-4">
      <h3 className="label">Why this tier</h3>
      <ol className="mt-3 space-y-2 text-sm">
        {steps.map((step, index) => (
          <li key={`${step.rule}-${index}`} className="sm:flex sm:items-baseline sm:gap-4">
            {/* Its own line on a narrow screen. Inline, the label ran straight
                into the sentence it labels — "scoreeffective risk 60". */}
            <span className="label block shrink-0 whitespace-nowrap sm:w-28">
              {step.factor ? FACTOR_LABEL[step.factor] : "score"}
            </span>
            <span className="text-[rgb(var(--muted))] sm:flex-1">{step.detail}</span>
            <span className="mono mt-0.5 block shrink-0 text-xs sm:mt-0 sm:text-right">
              {step.from_tier === step.to_tier
                ? index === 0
                  ? tierLabel(step.to_tier)
                  : `held at ${tierLabel(step.to_tier)}`
                : `${tierLabel(step.from_tier)} → ${tierLabel(step.to_tier)}`}
            </span>
          </li>
        ))}
      </ol>
      <p className="mt-3 text-xs text-[rgb(var(--faint))]">
        A rule that fired without moving the tier is listed as held rather than dropped — it
        is a reason the answer would have been the same anyway.
      </p>
    </div>
  );
}

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
  tiers,
  blastRadius,
  affectedUsers,
  expectedPostState,
  rollback,
}: {
  verdict: Verdict;
  tiers?: PolicyModel["tiers"] | null;
  blastRadius?: number;
  affectedUsers?: number;
  expectedPostState?: Record<string, string>;
  rollback?: string | null;
}) {
  const tier = TIER[verdict.tier] ?? TIER.denied;
  const denied = verdict.tier === "denied";
  const steps = verdict.tier_reasons ?? [];
  // Where the score alone put it, before any hard override — the first step is
  // always the band. Absent on a verdict issued before the engine recorded its
  // reasoning, and the scale then only marks where the action landed.
  const fromScore = steps[0]?.to_tier ?? null;
  const riskStatus = statusForRisk(verdict.effective_risk);

  return (
    <Panel
      title="Authorization"
      aside={<Badge status={tier.status}>{tierLabel(verdict.tier)}</Badge>}
      className={denied ? "border-[rgb(var(--crit))]/30" : ""}
    >
      <p className="text-sm">
        <Ident>{verdict.action_id}</Ident>{" "}
        <span className="text-[rgb(var(--muted))]">— {tier.explain}</span>
      </p>

      {verdict.denial_reason && (
        <p className="mt-3 text-sm text-[rgb(var(--crit))]">{verdict.denial_reason}</p>
      )}

      {tiers?.length ? <Scale tiers={tiers} landed={verdict.tier} fromScore={fromScore} /> : null}

      {steps.length > 0 && <WhyThisTier steps={steps} />}

      <div className="mt-6 grid gap-5 border-t border-[rgb(var(--edge))] pt-4 sm:grid-cols-3">
        <div>
          <div className="label">Effective risk</div>
          <div className={`mt-1 flex items-baseline gap-2 ${STATUS[riskStatus].text}`}>
            {/* The glyph at the size of the number it qualifies. A tinted figure
                says "medium" to someone who can see the tint and says nothing to
                anyone else — and this is the number that decides whether a human
                has to approve. */}
            <span aria-hidden="true" className="text-2xl">
              {STATUS[riskStatus].glyph}
            </span>
            <span className="tnum text-2xl font-semibold">{verdict.effective_risk}</span>
          </div>
          <div className="mt-1 text-xs text-[rgb(var(--muted))]">
            {riskBand(verdict.effective_risk).label} · base {verdict.base_risk}
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
                <span className="text-[rgb(var(--muted))]">
                  {adjustment.reason}
                  {/* Tagged with the same factor the tier explanation uses, so
                      the two halves of the panel name one term one way — except
                      where the reason already opens with it, and the tag would
                      be the phrase "blast radius" printed twice on one line. */}
                  {adjustment.factor &&
                    !adjustment.reason
                      .toLowerCase()
                      .startsWith(FACTOR_LABEL[adjustment.factor]) && (
                      <span className="label ml-2">{FACTOR_LABEL[adjustment.factor]}</span>
                    )}
                </span>
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
