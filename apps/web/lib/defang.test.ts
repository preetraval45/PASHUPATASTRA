import assert from "node:assert/strict";
import { test } from "node:test";

import { defang, defangGroup, defangHost, refang } from "./defang.ts";

/**
 * R115: nothing a feed supplied reaches the page in its live form, and the
 * live form can always be rebuilt for the lookup.
 */

const LIVE = /\bhttps?:\/\/|(?<![\w[])(?:\d{1,3}\.){3}\d{1,3}(?![\w\]])|\b[a-z0-9-]+\.(?:com|net|xyz|top|ru|zzzzz)\b/i;

test("a host has every dot bracketed, not only the last", () => {
  assert.equal(defangHost("evil.example.com"), "evil[.]example[.]com");
  assert.equal(defangHost("45.61.184.22"), "45[.]61[.]184[.]22");
  assert.equal(defangHost("evil[.]com"), "evil[.]com", "already defanged is left defanged");
});

test("schemes, addresses and domains in prose are defanged", () => {
  assert.equal(
    defang("Malware distribution reported at http://evil.example.com/x.sh"),
    // `.sh` is a country suffix, so a filename in the path is bracketed too.
    // Harmless, and it round-trips; a filter cannot tell it from a host.
    "Malware distribution reported at hxxp://evil[.]example[.]com/x[.]sh",
  );
  assert.equal(defang("C2 at 45.61.184.22 answering"), "C2 at 45[.]61[.]184[.]22 answering");
  assert.equal(defang("HTTPS://bad.xyz"), "hxxps://bad[.]xyz", "the scheme is normalised");
});

test("a scheme's host is defanged even on a suffix the scanner does not trust", () => {
  assert.equal(defang("https://thing.zzzzz/payload"), "hxxps://thing[.]zzzzz/payload");
});

test("what cannot be reached is left readable", () => {
  for (const text of ["CVE-2024-3400", "d41d8cd98f00b204e9800998ecf8427e", "account j.rivera", "end of sentence."]) {
    assert.equal(defang(text), text);
  }
});

test("refang undoes defang", () => {
  for (const text of [
    "http://evil.example.com/x.sh",
    "https://thing.zzzzz/p",
    "seen at 45.61.184.22 and bad.xyz",
    "ftp://files.example.net/a",
  ]) {
    assert.equal(refang(defang(text)), text);
  }
});

test("a feed group carries no live indicator anywhere", () => {
  const group = defangGroup({
    entity_key: "indicator:url:payload.badhost.zzzzz",
    source: "urlhaus",
    severity: "warning",
    verification: "reported",
    title: "Malware distribution reported at payload.badhost.zzzzz",
    summary: "payload.badhost.zzzzz serving mozi; status online",
    provenance: { source_system: "urlhaus", url: "https://urlhaus.abuse.ch/url/1/" },
    labels: { status: "online", tags: "elf, mozi", host: "payload.badhost.zzzzz" },
    reports: 2,
    reports_in_window: 2,
    window_hours: 3,
    first_at: "2026-10-04T00:00:00Z",
    last_at: "2026-10-04T01:00:00Z",
    active: true,
    history: [
      { id: "a", at: "2026-10-04T00:00:00Z", status: "online", tags: "seen at 45.61.184.22", summary: "payload.badhost.zzzzz", url: "https://urlhaus.abuse.ch/url/1/" },
    ],
  });

  const { provenance, history, ...rest } = group;
  const served = JSON.stringify({ ...rest, history: history.map(({ url: _url, ...report }) => report) });
  assert.ok(!/payload\.badhost/.test(served), served);
  assert.ok(!LIVE.test(served), served);
  assert.equal(group.entity_key, "indicator:url:payload[.]badhost[.]zzzzz");
  // The advisory is the publisher's page, and is the link a reader follows.
  assert.equal(provenance.url, "https://urlhaus.abuse.ch/url/1/");
  assert.equal(history[0].url, "https://urlhaus.abuse.ch/url/1/");
});

test("a ThreatFox ip:port indicator is hidden whole", () => {
  const group = defangGroup({
    entity_key: "indicator:ip:port:45.61.184.22:443",
    source: "threatfox", severity: null, verification: "reported",
    title: "45.61.184.22:443 tied to Cobalt Strike", summary: "", provenance: {}, labels: {},
    reports: 1, reports_in_window: 1, window_hours: 3, first_at: "", last_at: "", active: null, history: [],
  });
  assert.equal(group.entity_key, "indicator:ip:port:45[.]61[.]184[.]22:443");
  assert.ok(!LIVE.test(group.title + group.entity_key), group.title);
});

test("a CVE group is not bracketed", () => {
  const group = defangGroup({
    entity_key: "vulnerability:CVE-2024-3400",
    source: "cisa-kev",
    severity: "critical",
    verification: "confirmed",
    title: "CVE-2024-3400 exploited",
    summary: "",
    provenance: {},
    labels: {},
    reports: 1,
    reports_in_window: 1,
    window_hours: 3,
    first_at: "",
    last_at: "",
    active: null,
    history: [],
  });
  assert.equal(group.entity_key, "vulnerability:CVE-2024-3400");
  assert.equal(group.title, "CVE-2024-3400 exploited");
});
