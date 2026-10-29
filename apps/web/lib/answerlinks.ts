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
