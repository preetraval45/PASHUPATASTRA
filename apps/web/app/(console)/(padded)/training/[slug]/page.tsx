import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";

import { Quiz } from "@/components/course";
import { Page, Panel } from "@/components/ui";
import { MODULES, moduleBySlug, PASS_MARK } from "@/lib/training";

type Params = Promise<{ slug: string }>;

export function generateStaticParams() {
  return MODULES.map((m) => ({ slug: m.slug }));
}

export async function generateMetadata({ params }: { params: Params }): Promise<Metadata> {
  const { slug } = await params;
  const m = moduleBySlug(slug);
  return m ? { title: `${m.title} · Training`, description: m.summary } : {};
}

/** One module: learn it, see how it applies in real life, then test it. */
export default async function ModulePage({ params }: { params: Params }) {
  const { slug } = await params;
  const m = moduleBySlug(slug);
  if (!m) notFound();

  const index = MODULES.findIndex((x) => x.slug === m.slug);
  const next = MODULES[index + 1];

  return (
    <Page title={m.title} description={m.summary}>
      <p className="-mt-4 flex flex-wrap items-center gap-2 text-xs text-[rgb(var(--faint))]">
        <Link href="/training" className="focusable rounded hover:text-[rgb(var(--ink))]">← Training</Link>
        <span>·</span>
        <span>Module {index + 1} of {MODULES.length}</span>
        <span>·</span>
        <span>{m.level}</span>
        <span>·</span>
        <span>about {m.minutes} minutes</span>
      </p>

      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_20rem]">
        <article className="space-y-6">
          {m.lessons.map((lesson, i) => (
            <section key={lesson.heading} className="rounded-xl border border-[rgb(var(--edge))] bg-[rgb(var(--panel))] p-5">
              <h2 className="flex items-center gap-2 text-lg font-semibold tracking-tight">
                <span className="tnum inline-flex h-6 w-6 items-center justify-center rounded-full bg-[rgb(var(--astra))]/15 text-xs text-[rgb(var(--astra))]">
                  {i + 1}
                </span>
                {lesson.heading}
              </h2>
              <div className="mt-3 space-y-3 text-[0.9375rem] leading-relaxed text-[rgb(var(--muted))]">
                {lesson.body.map((p) => (
                  <p key={p.slice(0, 40)}>{p}</p>
                ))}
              </div>
            </section>
          ))}
        </article>

        <aside className="space-y-4 lg:sticky lg:top-4 lg:self-start">
          <Panel title="Use it in real life">
            <ul className="space-y-2 text-sm text-[rgb(var(--muted))]">
              {m.realLife.map((item) => (
                <li key={item} className="flex gap-2">
                  <span aria-hidden="true" className="text-[rgb(var(--ok))]">✓</span>
                  <span>{item}</span>
                </li>
              ))}
            </ul>
          </Panel>
          {m.attack && (
            <Panel title="ATT&CK techniques">
              <ul className="space-y-1.5 text-sm">
                {m.attack.map((t) => (
                  <li key={t.id}>
                    <a
                      href={`https://attack.mitre.org/techniques/${t.id.replace(".", "/")}/`}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="focusable rounded hover:text-[rgb(var(--astra))]"
                    >
                      <span className="mono text-xs text-[rgb(var(--astra))]">{t.id}</span> {t.name}
                    </a>
                  </li>
                ))}
              </ul>
            </Panel>
          )}
          {m.drill && (
            <Panel title="Practise it">
              <Link
                href={m.drill.href}
                className="focusable block rounded-lg border border-[rgb(var(--astra))]/40 bg-[rgb(var(--astra))]/10 px-3 py-2.5 text-sm transition hover:bg-[rgb(var(--astra))]/20"
              >
                {m.drill.label} →
              </Link>
            </Panel>
          )}
        </aside>
      </div>

      <section className="rounded-xl border border-[rgb(var(--edge-strong))] bg-[rgb(var(--panel))] p-5">
        <h2 className="text-xl font-semibold tracking-tight">Test what you learned</h2>
        <p className="mt-1 mb-5 text-sm text-[rgb(var(--muted))]">
          {m.quiz.length} questions · pass mark {PASS_MARK * 100}% · every answer explains itself after you submit.
        </p>
        <Quiz slug={m.slug} questions={m.quiz} />
      </section>

      {next && (
        <Link
          href={`/training/${next.slug}`}
          className="focusable lift flex items-center justify-between rounded-xl border border-[rgb(var(--edge))] bg-[rgb(var(--panel))] p-5 transition hover:border-[rgb(var(--astra))]/50"
        >
          <span>
            <span className="label">Next module</span>
            <span className="mt-1 block font-medium">{next.title}</span>
          </span>
          <span aria-hidden="true" className="text-xl text-[rgb(var(--astra))]">→</span>
        </Link>
      )}
    </Page>
  );
}
