import type { Metadata } from "next";
import Image from "next/image";
import Link from "next/link";

import { Cite } from "@/components/cite";
import { Offline, Page, Panel } from "@/components/ui";
import { getFigures, getImpact } from "@/lib/api";
import press from "@/lib/press.generated.json";
import { SITE } from "@/lib/site";

export const metadata: Metadata = {
  title: "Press kit",
  description:
    "What Pashupatastra is, in a paragraph anyone can quote, with screenshots captured from the running console and figures anyone can recount.",
};

export const dynamic = "force-dynamic";

/**
 * A media kit, built so somebody can write about this without doing the
 * research twice (R109).
 *
 * The screenshots are captured from the running site by
 * `scripts/buildpress.py`, and every caption prints the URL the image came
 * from, at which commit and when. A mockup would be easier and would be a
 * picture of something that does not exist; a caption typed by hand would
 * drift from what was photographed.
 *
 * **The mark is deliberately not offered.** A press kit exists so that someone
 * can republish, and BRAND.md records that the artwork's origin and licensing
 * have not been established — "resolve before any public launch, not after".
 * Handing it to the people most likely to publish it would be exactly the
 * wrong order. The page says so rather than quietly omitting it, because a
 * journalist who cannot find the logo should know why rather than assume an
 * oversight.
 */
export default async function PressPage() {
  const [impact, figures] = await Promise.all([getImpact(), getFigures()]);
  if (impact === null) return <Offline />;

  const intel = impact.intelligence.value;
  const citations = figures?.citations.value ?? null;

  return (
    <Page
      title="Press kit"
      description="What this is, what it does, and pictures of it doing that."
      actions={
        <p className="text-xs text-[rgb(var(--faint))]">
          captured {press.captured_at.slice(0, 10)} at {press.commit}
        </p>
      }
    >
      <Panel title="In a paragraph" aside="quote it as it stands">
        <p className="text-sm leading-relaxed">
          Pashupatastra is a security operations console that treats a set of unrelated alerts as
          one intrusion. It correlates the telemetry into a single incident with a causal chain,
          maps each step to a MITRE ATT&amp;CK technique, and proposes remediation that a
          deterministic policy engine — not a language model — decides whether a human must
          authorise. Every claim it makes carries a reference to the record behind it, and the
          assistant cannot act: it can name an action, and the action waits for a person. It is
          built and maintained by Preet Raval, and the whole of it is open to read.
        </p>
        <dl className="mt-4 grid gap-x-6 gap-y-2 text-sm sm:grid-cols-[auto_1fr]">
          <dt className="label">live</dt>
          <dd className="mono break-all">
            <Link href="/" className="focusable rounded underline decoration-dotted">
              {SITE}
            </Link>
          </dd>
          <dt className="label">source</dt>
          <dd className="mono break-all">https://github.com/preetraval45/PASHUPATASTRA</dd>
          <dt className="label">contact</dt>
          <dd className="mono break-all">preetraval45@gmail.com</dd>
          <dt className="label">built by</dt>
          <dd>Preet Raval</dd>
        </dl>
      </Panel>

      <Panel title="Figures, each recountable" aside="nothing here is typed">
        <ul className="space-y-2 text-sm">
          {citations && (
            <li>
              <span className="tnum text-[rgb(var(--ink))]">
                {citations.resolved} of {citations.cited}
              </span>{" "}
              evidence references resolve to the stored record they cite —{" "}
              <Link href="/incidents" className="focusable rounded underline decoration-dotted">
                follow them
              </Link>
            </li>
          )}
          {figures?.accountability.value && (
            <li>
              <span className="tnum text-[rgb(var(--ink))]">
                {figures.accountability.value.needs_a_human} of{" "}
                {figures.accountability.value.registered}
              </span>{" "}
              registered actions cannot run without a person —{" "}
              <Link href="/actions" className="focusable rounded underline decoration-dotted">
                the registry
              </Link>
            </li>
          )}
          {intel && (
            <li>
              <span className="tnum text-[rgb(var(--ink))]">
                {intel.indicators.toLocaleString()}
              </span>{" "}
              live threat indicators ingested from {intel.feeds} public feeds —{" "}
              <Link href="/observatory" className="focusable rounded underline decoration-dotted">
                the observatory
              </Link>
            </li>
          )}
          <li>
            Every figure above is recomputed on request from the store or the registry.{" "}
            <Link href="/impact" className="focusable rounded underline decoration-dotted">
              Where each number comes from
            </Link>
            , including the one this project cannot yet evidence.
          </li>
        </ul>
      </Panel>

      <Panel
        title="Screenshots"
        aside={`${press.shots.length}, captured from the running site at ${press.shots[0]?.width}px`}
      >
        <ul className="space-y-8">
          {press.shots.map((shot) => (
            <li key={shot.name} data-shot={shot.name} className="min-w-0">
              <Image
                src={shot.file}
                alt={shot.caption}
                width={shot.width}
                height={shot.height}
                className="h-auto w-full rounded-lg border border-[rgb(var(--edge))]"
                // Below the fold on a page nobody reaches in a hurry, and five
                // full-width captures is a lot of bytes to spend before a
                // reader has asked for them.
                loading="lazy"
                unoptimized
              />
              <p className="mt-2 text-sm leading-relaxed text-[rgb(var(--muted))]">
                {shot.caption}
              </p>
              {/* The URL, printed. A caption is somebody's description; this is
                  what was photographed, and the two cannot drift. */}
              <p className="mono mt-1 break-all text-[11px] text-[rgb(var(--faint))]">
                captured from {shot.route} · {shot.width}×{shot.height}
              </p>
            </li>
          ))}
        </ul>
      </Panel>

      <Panel title="The mark" aside="not offered for republication">
        <p className="text-sm leading-relaxed text-[rgb(var(--muted))]">
          There is no logo download here, and that is deliberate rather than an oversight. The
          artwork this project uses as its mark has unestablished origin and licensing, recorded
          in its own brand notes as something to resolve before any public launch rather than
          after. Offering it to the people most likely to publish it would be the wrong order.
          The screenshots above are this project&rsquo;s own interface and may be used to
          illustrate writing about it; please credit <span className="text-[rgb(var(--ink))]">
            Pashupatastra
          </span>{" "}
          and link to <span className="mono break-all">{SITE}</span>.
        </p>
      </Panel>

      <Panel title="Cite this work" aside="from CITATION.cff">
        <Cite />
      </Panel>
    </Page>
  );
}
