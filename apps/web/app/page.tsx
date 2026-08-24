import type { Metadata } from "next";
import Link from "next/link";

import { getIncidents } from "@/lib/api";

/**
 * The page a stranger sees.
 *
 * `/` was the operator's dashboard — severity counts, a posture bar, an audit
 * ledger — shown to people with no idea what any of it meant. A console is the
 * right shape for someone who already bought the product and the wrong shape
 * for everyone who has not.
 *
 * Four things and then it stops: what the loop is, what an incident looks like
 * before and after, what "bounded autonomy" actually constrains, and a door
 * into the live thing. **No pricing** — this has no accounts and no billing,
 * and a price invites a question the site cannot answer.
 *
 * Every number here comes from the scenarios the demo actually serves, and the
 * page links to the incident it is describing. Nothing on this page is a
 * benchmark: `ROADMAP.md` records that MTTR is not computable in this
 * deployment, so a measured time-saving claim would be an invention, and an
 * invented number on the front page would undo the thing the rest of the
 * product spends its effort proving.
 */

export const metadata: Metadata = {
  title: "Pashupatastra",
  description:
    "A security console that assembles scattered signals into one incident with a causal chain, scores the response, and needs a human before anything consequential runs.",
};

export const dynamic = "force-dynamic";

const LOOP = ["Observe", "Understand", "Predict", "Decide", "Act", "Verify", "Learn"];

/** The scattered signals of one real scenario, in the order they arrive. Taken
 *  from INC-2026-0903 — each is individually ignorable, which is the point. */
const SCATTERED = [
  ["09:12", "a host talks to an address nothing has used before"],
  ["09:14", "the connection repeats every 60 seconds, ±2"],
  ["10:31", "SMB opens to two hosts it has never contacted"],
  ["10:42", "a scheduled task appears on one of them"],
];

export default async function LandingPage() {
  const incidents = await getIncidents();

  // The incident this page describes, not merely the first one.
  //
  // "Open it →" sat under a panel describing the beaconing scenario and linked
  // to whichever incident happened to be first — credential stuffing. The
  // sentence and the destination disagreed, on the one page whose entire job is
  // that the two match.
  //
  // Matched on the hypothesis rather than the id, because an id is a fixture
  // detail and would go stale silently the day the scenarios are renumbered;
  // this falls back to the list instead of pointing somewhere wrong.
  const described = incidents?.find((incident) =>
    incident.hypotheses[0]?.statement.toLowerCase().includes("beaconing"),
  );
  const demo = described
    ? `/incidents/${encodeURIComponent(described.id)}`
    : "/incidents";

  return (
    <div className="space-y-16 pb-8">
      {/* --- what it is ------------------------------------------------- */}
      <section className="space-y-6">
        <p className="label text-[rgb(var(--astra))]">
          Observe. Reason. Act. Verify.
        </p>
        <h1 className="max-w-4xl text-3xl font-semibold leading-tight tracking-tight sm:text-5xl">
          Four alerts in four tools are one intrusion.{" "}
          <span className="text-[rgb(var(--muted))]">
            This is the thing that says so.
          </span>
        </h1>
        <p className="max-w-2xl text-base leading-relaxed text-[rgb(var(--muted))]">
          Pashupatastra assembles scattered signals into a single incident with
          a causal chain, maps each step to a known technique, and proposes a
          response that is scored before anyone runs it. Every claim it makes
          carries a link to the evidence it came from.
        </p>

        {/* R58: the one affordance a skimmer needs, and it says what it opens.
            Plain links — no modal, no overlay, nothing that has to boot before
            the page beneath it renders, and it works with JavaScript off.

            The previous label said "Open a real incident" and pointed at a
            scripted scenario. That was the site's own honesty rule broken on
            its first screen, and it got worse the day genuinely real attacks
            landed on /observatory: two things were being called real and only
            one of them was. */}
        <div className="pt-2">
          <p className="label mb-3 text-[rgb(var(--faint))]">Start here</p>
          <div className="flex flex-wrap items-center gap-3">
            <Link
              href={demo}
              className="focusable rounded-lg border border-[rgb(var(--astra))]/50 bg-[rgb(var(--astra))]/10 px-5 py-2.5 text-sm font-medium transition hover:bg-[rgb(var(--astra))]/20"
            >
              Open a worked incident →
            </Link>
            <Link
              href="/observatory"
              className="focusable rounded-lg border border-[rgb(var(--edge-strong))] px-5 py-2.5 text-sm transition hover:bg-[rgb(var(--raised))]"
            >
              Or today&rsquo;s real attacks
            </Link>
            <Link
              href="/blue-team"
              className="focusable rounded-lg border border-[rgb(var(--edge))] px-5 py-2.5 text-sm text-[rgb(var(--muted))] transition hover:bg-[rgb(var(--raised))] hover:text-[rgb(var(--ink))]"
            >
              Work one yourself
            </Link>
          </div>
          <p className="mt-3 max-w-2xl text-xs leading-relaxed text-[rgb(var(--faint))]">
            The worked incident is a written scenario, labelled as one wherever
            it appears — it exists to show the whole chain end to end. The
            attacks on the Observatory are real: ransomware groups naming
            victims, botnet controllers answering right now, breaches as they
            are disclosed.
          </p>
        </div>

        <ol className="flex flex-wrap items-center gap-x-2 gap-y-2 pt-4 text-xs text-[rgb(var(--faint))]">
          {LOOP.map((stage, index) => (
            <li key={stage} className="flex items-center gap-2">
              {index > 0 && <span aria-hidden="true">→</span>}
              <span
                className={
                  index < 6 ? "text-[rgb(var(--muted))]" : "text-[rgb(var(--faint))]"
                }
              >
                {stage}
              </span>
            </li>
          ))}
          <li className="w-full pt-1 sm:w-auto sm:pl-3">
            Most tools stop after the second one.
          </li>
        </ol>
      </section>

      {/* --- before and after -------------------------------------------- */}
      <section className="space-y-5">
        <h2 className="text-xl font-semibold tracking-tight sm:text-2xl">
          What an incident looks like, before and after
        </h2>

        <div className="grid gap-5 lg:grid-cols-2">
          <div className="panel p-5">
            <p className="label mb-3">Before — four separate alerts</p>
            <ol className="space-y-2.5">
              {SCATTERED.map(([at, what]) => (
                <li key={at} className="flex gap-3 text-sm">
                  <span className="mono shrink-0 text-[rgb(var(--faint))]">{at}</span>
                  <span className="text-[rgb(var(--muted))]">{what}</span>
                </li>
              ))}
            </ol>
            <p className="mt-4 border-t border-[rgb(var(--edge))] pt-3 text-xs text-[rgb(var(--faint))]">
              Ninety minutes apart, in different tools. Each one is individually
              ignorable, and each one was ignored.
            </p>
          </div>

          <div className="panel p-5">
            <p className="label mb-3">After — one incident</p>
            <p className="text-sm leading-relaxed">
              A workstation is beaconing to a command-and-control host and has
              begun moving laterally: new SMB peers, then a scheduled task on
              one of them.
            </p>
            <ul className="mt-4 space-y-1.5 text-xs text-[rgb(var(--muted))]">
              <li>· three causal steps, each citing the signal it rests on</li>
              <li>· mapped to T1071.001, T1021.002 and T1053.005</li>
              <li>· blast radius over observed access, not guesswork</li>
              <li>· a two-step plan, scored before anything runs</li>
            </ul>
            <p className="mt-4 border-t border-[rgb(var(--edge))] pt-3 text-xs">
              <Link
                href={demo}
                className="focusable rounded underline decoration-dotted underline-offset-2 hover:text-[rgb(var(--astra))]"
              >
                See the whole chain on this one — open it →
              </Link>
            </p>
          </div>
        </div>

        {/* The arithmetic, made of the demo's own numbers rather than a
            benchmark. The cost of an incident is the gap between the first
            signal and somebody joining it to the fourth. */}
        <p className="max-w-3xl text-sm leading-relaxed text-[rgb(var(--muted))]">
          The cost of an intrusion is not the alert. It is the gap between the
          first signal and the moment someone connects it to the fourth. In the
          three scenarios on this site that gap is{" "}
          <span className="text-[rgb(var(--ink))]">11, 30 and 90 minutes</span>{" "}
          — and every minute of it is an attacker working uninterrupted while
          four true alerts sit in four different tools, each one too small to
          act on alone.
        </p>
      </section>

      {/* --- bounded autonomy -------------------------------------------- */}
      <section className="space-y-5">
        <h2 className="text-xl font-semibold tracking-tight sm:text-2xl">
          It proposes. A human authorises.
        </h2>
        <p className="max-w-2xl text-sm leading-relaxed text-[rgb(var(--muted))]">
          Every executable action is registered with a risk score and routed
          through the policy engine. There is no path around it — not in the
          product, and not in the demo fixtures.
        </p>

        <div className="grid gap-4 sm:grid-cols-3">
          {[
            {
              title: "Scored, not judged",
              body: "Risk is computed from blast radius, confidence and reversibility — then a tier decides who may authorise it.",
            },
            {
              title: "Rollback declared first",
              body: "An action states how to undo it and what it expects to be true afterwards, before it is allowed to run.",
            },
            {
              title: "Two shut gates",
              body: "This deployment is in dry run and its environment is not on the live list. Both must open before anything executes.",
            },
          ].map((card) => (
            <div key={card.title} className="panel p-4">
              <p className="mb-2 text-sm font-medium">{card.title}</p>
              <p className="text-xs leading-relaxed text-[rgb(var(--muted))]">
                {card.body}
              </p>
            </div>
          ))}
        </div>

        <p className="text-sm text-[rgb(var(--muted))]">
          The tiers, the gates and the registry are on{" "}
          <Link
            href="/how-it-works"
            className="focusable rounded underline decoration-dotted underline-offset-2 hover:text-[rgb(var(--astra))]"
          >
            how it works
          </Link>
          , generated from the running system rather than written down.
        </p>
        <p className="text-sm text-[rgb(var(--muted))]">
          The assistant is bound by the same rule: ask it to isolate a host and
          it names the action, sends it for approval, and executes nothing.{" "}
          <Link
            href="/ask"
            className="focusable rounded underline decoration-dotted underline-offset-2 hover:text-[rgb(var(--astra))]"
          >
            Try that →
          </Link>
        </p>
      </section>

      {/* --- the way in --------------------------------------------------- */}
      <section className="panel space-y-4 p-6">
        <h2 className="text-lg font-semibold tracking-tight">
          Everything here is live
        </h2>
        <p className="max-w-2xl text-sm leading-relaxed text-[rgb(var(--muted))]">
          The worked incidents are scripted and labelled as such. Everything on
          the Observatory is real and polled hourly: ransomware groups naming
          victims, botnet command-and-control servers answering now, breaches as
          they are disclosed, and CISA&rsquo;s catalogue of vulnerabilities being
          exploited in the wild. Nothing on this site executes anything.
        </p>
        <div className="flex flex-wrap gap-3 pt-1">
          <Link
            href={demo}
            className="focusable rounded border border-[rgb(var(--edge-strong))] px-4 py-2 text-sm transition hover:bg-[rgb(var(--raised))]"
          >
            A worked incident
          </Link>
          <Link
            href="/blue-team"
            className="focusable rounded border border-[rgb(var(--edge-strong))] px-4 py-2 text-sm transition hover:bg-[rgb(var(--raised))]"
          >
            Work one yourself
          </Link>
          <Link
            href="/observatory"
            className="focusable rounded border border-[rgb(var(--edge-strong))] px-4 py-2 text-sm transition hover:bg-[rgb(var(--raised))]"
          >
            Today&rsquo;s advisories
          </Link>
          <Link
            href="/overview"
            className="focusable rounded border border-[rgb(var(--edge))] px-4 py-2 text-sm text-[rgb(var(--muted))] transition hover:bg-[rgb(var(--raised))] hover:text-[rgb(var(--ink))]"
          >
            The console
          </Link>
        </div>
      </section>
    </div>
  );
}
