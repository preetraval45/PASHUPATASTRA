/** Links and follow-ups read from Sati's plain-text answers (components/answertext.tsx). */

/** The official page for an ATT&CK technique or mitigation, a CAPEC pattern or a CVE. */
export function idUrl(id: string): string {
  if (id.startsWith("CVE-")) return `https://nvd.nist.gov/vuln/detail/${id}`;
  if (id.startsWith("CAPEC-")) return `https://capec.mitre.org/data/definitions/${id.slice(6)}.html`;
  if (id.startsWith("M")) return `https://attack.mitre.org/mitigations/${id}/`;
  return `https://attack.mitre.org/techniques/${id.replace(".", "/")}/`;
}

/** The technique an answer names first, as a follow-up question about defending against it. */
export function defendFollowUp(text: string): string | null {
  const match = text.match(/(?:^|\n)(?:\d+\. |For )?([A-Z][^()\n]{2,60}?) \((T\d{4}(?:\.\d{3})?)\)/);
  if (!match || /defen[cs]es?|mitigations?/i.test(text.split("\n")[0])) return null;
  return `How do we defend against ${match[1].trim()} (${match[2]})?`;
}

/** What an answer is about: its bold title, the technique it defends against, or its first ranked
 *  technique, whichever comes first in the text (its own first line). */
export function answerSubject(text: string): { title: string; id: string } | null {
  const found = [
    /\*\*([^*\n]+)\*\* \(([A-Z][\w.-]+)\)/.exec(text),
    /defend against ([^\n(]+?) \((T\d{4}(?:\.\d{3})?|TA\d{4}|CAPEC-\d+)\)/.exec(text),
    /(?:^|\n)1\. ([^\n(]+?) \((T\d{4}(?:\.\d{3})?)\)/.exec(text),
  ].filter((m): m is RegExpExecArray => m !== null);
  if (!found.length) return null;
  const first = found.reduce((x, y) => (y.index < x.index ? y : x));
  return { title: first[1].trim(), id: first[2] };
}

/**
 * Up to three questions to ask next, each one the served models answer well:
 * how to defend against what was explained, what the defended-against thing
 * is, and the related entries the answer named. Read from the answer's own
 * text, so every suggestion is about something it actually said.
 */
export function followUps(text: string): string[] {
  const subject = answerSubject(text);
  const out: string[] = [];
  if (subject) {
    if (/^To defend against/m.test(text)) out.push(`How does ${subject.title} work?`);
    else if (!subject.id.startsWith("CVE-")) out.push(`How do we defend against ${subject.title}?`);
  }
  const ranked = [...text.matchAll(/(?:^|\n)\d\. ([^\n(]+?) \((T\d{4}(?:\.\d{3})?)\)/g)].map((m) => m[1].trim());
  for (const r of ranked.slice(1, 3)) out.push(`What is ${r}?`);
  const related = text.match(/(?:^|\n)Related: (.+)\.\s*(?:\n|$)/);
  if (related) {
    for (const part of related[1].split("; ")) {
      const name = part.replace(/\s*\([^)]*\)\s*$/, "").trim();
      if (name && !/^Mitigation for /.test(name)) out.push(`What is ${name}?`);
    }
  }
  return [...new Set(out)].filter((q) => !subject || q !== `What is ${subject.title}?`).slice(0, 3);
}
