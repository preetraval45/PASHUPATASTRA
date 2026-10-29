import type { ReactNode } from "react";

import { idUrl } from "@/lib/answerlinks";

export { defendFollowUp } from "@/lib/answerlinks";

/**
 * Sati's plain-text answers, laid out to be read: the first line as the lead,
 * "- " and "1. " lines as a list, the "Sources:" line as links, and every
 * ATT&CK, CAPEC or CVE identifier as a link to its official page, so a
 * reader can check a claim in one tap (rule 1: claims carry their grounds).
 *
 * Only identifiers in the answer's own text become links, built from the
 * identifier itself; nothing is looked up or invented.
 */
const ID = /\b(T\d{4}(?:\.\d{3})?|M\d{4}|CAPEC-\d+|CVE-\d{4}-\d{4,})\b/g;

function linkify(text: string): ReactNode[] {
  const out: ReactNode[] = [];
  let last = 0;
  for (const match of text.matchAll(ID)) {
    const at = match.index ?? 0;
    if (at > last) out.push(text.slice(last, at));
    out.push(
      <a
        key={at}
        href={idUrl(match[0])}
        target="_blank"
        rel="noopener noreferrer"
        className="mono rounded bg-[rgb(var(--astra))]/10 px-1 text-[0.85em] text-[rgb(var(--astra))] hover:underline"
      >
        {match[0]}
      </a>,
    );
    last = at + match[0].length;
  }
  if (last < text.length) out.push(text.slice(last));
  return out;
}

export function AnswerText({ text, muted = false }: { text: string; muted?: boolean }) {
  const lines = text.split("\n");
  const lead = lines.findIndex((l) => l.trim());
  // Each line rises in just after the one before, so an answer arrives as it would be read.
  // Capped, so a long answer is never held back; the reduced-motion rule in globals.css stills it.
  const reveal = (i: number) => ({ animationDelay: `${Math.min(i, 12) * 45}ms` });
  return (
    <div className="space-y-2 text-[0.9375rem] leading-relaxed">
      {lines.map((line, i) => {
        if (!line.trim()) return null;
        if (line.startsWith("Sources: ")) {
          const urls = line.slice(9).split(" · ").filter((u) => u.startsWith("http"));
          return (
            <p key={i} className="rise flex flex-wrap gap-1.5 pt-1" style={reveal(i)}>
              {urls.map((u) => (
                <a
                  key={u}
                  href={u}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="focusable max-w-full truncate rounded-full border border-[rgb(var(--edge))] px-2.5 py-0.5 text-[11px] text-[rgb(var(--faint))] transition hover:border-[rgb(var(--astra))]/50 hover:text-[rgb(var(--astra))]"
                >
                  {u.replace(/^https?:\/\/(www\.)?/, "").replace(/\/$/, "")} ↗
                </a>
              ))}
            </p>
          );
        }
        const item = line.match(/^(?:- |(\d+)\. )(.*)$/);
        if (item) {
          return (
            <p key={i} className="rise flex gap-2.5" style={reveal(i)}>
              <span aria-hidden="true" className="tnum w-4 shrink-0 text-right text-[rgb(var(--astra))]">
                {item[1] ?? "›"}
              </span>
              <span className="min-w-0">{linkify(item[2])}</span>
            </p>
          );
        }
        return (
          <p
            key={i}
            style={reveal(i)}
            className={
              i === lead && !muted ? "rise font-medium text-[rgb(var(--ink))]" : "rise text-[rgb(var(--muted))]"
            }
          >
            {linkify(line)}
          </p>
        );
      })}
    </div>
  );
}
