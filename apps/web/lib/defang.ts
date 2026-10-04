/**
 * Defanging (R115) — feed indicators are shown, never served live.
 *
 * Visitors behind corporate and school filters reported the site as
 * *restricted*. Those filters classify a page by what it carries, and the
 * Observatory carried malware-distribution hosts and botnet C2 addresses
 * verbatim in its HTML and its RSC payload. A page that lists live malicious
 * hosts is, to a content scanner, a page that distributes them.
 *
 * So every host and address that came from a feed is rendered in the
 * convention the feeds themselves use for sharing — `evil[.]example[.]com`,
 * `45[.]61[.]184[.]22`, `hxxp://` — and is never an `href`. Every dot, not
 * only the last: `evil.example[.]com` still leaves `evil.example` for a
 * pattern to find.
 *
 * The live value exists only where it is needed: `refang` rebuilds it in the
 * browser, at the moment a reader asks the lookup about it (R78). It is never
 * in what the server sends.
 */

import type { Intel, IntelGroup, IntelReport } from "./api.ts";
import { scan } from "./indicators.ts";

const SCHEME = /\bhtt(ps?):\/\//gi;
const FTP = /\bftp:\/\//gi;
// A host after a defanged scheme is defanged whatever its suffix. `scan`
// only trusts a known suffix, which is right for marking up prose and wrong
// here: a malware host on an unusual TLD is exactly the one to hide.
const SCHEMED_HOST = /\b(hxxps?|fxp):\/\/([^\s/:?#[\]]+)/gi;

/** One host or address, every dot bracketed. */
export function defangHost(host: string): string {
  return host.replace(/\[\.\]/g, ".").replace(/\./g, "[.]");
}

/** Text with every URL scheme, address and recognised domain defanged. CVE
 *  ids and hashes are left alone — they are not reachable. */
export function defang(text: string): string {
  if (!text) return text;
  let out = text.replace(SCHEME, (_, s: string) => `hxx${s.toLowerCase()}://`).replace(FTP, "fxp://");
  out = out.replace(SCHEMED_HOST, (_, scheme, host) => `${scheme}://${defangHost(host)}`);

  const spans = scan(out).filter((span) => span.kind === "ipv4" || span.kind === "domain");
  for (const span of spans.reverse()) {
    out = out.slice(0, span.start) + defangHost(span.value) + out.slice(span.end);
  }
  return out;
}

/** The live form back, for the one call that needs it: the lookup. */
export function refang(text: string): string {
  return (text ?? "")
    .replace(/\[\.\]/g, ".")
    .replace(/\bhxx(ps?):\/\//gi, (_, s: string) => `htt${s.toLowerCase()}://`)
    .replace(/\bfxp:\/\//gi, "ftp://");
}

/**
 * A feed's identifier, defanged outright.
 *
 * The identifier is known to be an indicator — the feed said so — so it does
 * not have to pass `scan`'s suffix test to be hidden. Its occurrences in the
 * title and summary are replaced by the same form, which is what covers a
 * host on a suffix `defang` alone would not recognise.
 */
function hideIn(text: string | null, identifier: string, hidden: string): string | null {
  if (text == null) return text;
  const replaced = identifier ? text.split(identifier).join(hidden) : text;
  return defang(replaced);
}

function defangReport(report: IntelReport, identifier: string, hidden: string): IntelReport {
  return {
    ...report,
    summary: hideIn(report.summary, identifier, hidden) ?? "",
    tags: hideIn(report.tags, identifier, hidden),
    // `url` is the advisory *about* the indicator — the publisher's page —
    // and is the one link a reader is meant to follow. Left as it is.
  };
}

export function defangGroup(group: IntelGroup): IntelGroup {
  // `indicator:url:payload.example.com`, `indicator:ip:45.61.184.22`,
  // `indicator:ip:port:45.61.184.22:443` — the entity kind, the feed's own
  // type for the value, then the value. Feeds name their types themselves
  // (ThreatFox sends `ioc_type`), so reachability is read off the type's
  // first word rather than matched against a closed list.
  const [kind, type = "", ...rest] = group.entity_key.split(":");
  const value = rest.join(":");
  // A CVE, a breach or a claimed victim is not reachable, and bracketing its
  // dots would only make it harder to read.
  const reachable = value !== "" && /^(url|ip|domain|host|hostname)$/i.test(type);
  const hidden = reachable ? defangHost(value) : value;
  const identifier = reachable ? value : "";

  const labels: Record<string, string> = {};
  for (const [key, text] of Object.entries(group.labels ?? {})) {
    labels[key] = hideIn(text, identifier, hidden) ?? text;
  }

  return {
    ...group,
    entity_key: reachable ? `${kind}:${type}:${hidden}` : group.entity_key,
    title: hideIn(group.title, identifier, hidden) ?? "",
    summary: hideIn(group.summary, identifier, hidden) ?? "",
    labels,
    history: (group.history ?? []).map((report) => defangReport(report, identifier, hidden)),
  };
}

/** The Observatory's whole payload, defanged before any of it is rendered. */
export function defangIntel(intel: Intel): Intel {
  return { ...intel, groups: intel.groups.map(defangGroup) };
}
