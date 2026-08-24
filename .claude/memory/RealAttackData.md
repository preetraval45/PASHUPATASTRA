# Real attack data, not scripted scenarios (Phase R)

## The decision

**24 August 2026.** *"i want real time incident and real time help in cyber
space not fake data"*, then *"not my code stuff i want real stuff like the world
cyber attacks and incidents"*. Confirmed: **both** world feeds and a honeypot,
and the three scripted incidents get **deleted**.

Recorded as Phase R (R88–R93) in `docs/REBUILD.md`.

## The distinction the whole phase rests on

Real data arrives in two kinds, and conflating them reintroduces the exact
fabrication the pivot exists to remove.

**Reported attacks** — ransomware.live, Feodo Tracker, ThreatFox, HIBP, CISA
KEV. They carry *that it happened and to whom*. They carry **nothing** about
how. So they get **no causal chain and no action plan**: inventing three
plausible steps and an `isolate_host` proposal for a stranger's breach is an
invented metric wearing a technique id. We also cannot act on someone else's
incident, so a plan would be theatre.

**Observed attacks** — the honeypot (R90). Real attackers, real commands,
telemetry we actually hold. The *only* source that legitimately supports the
full loop.

A group's tradecraft is a fact about **the group**, never about a specific
victim. "Qilin's published tradecraft includes T1486" is sourced; "Qilin used
T1486 here" is a guess.

## Free sources, all verified live, no API key

| Source | What it gives |
|---|---|
| `api.ransomware.live/v2/recentvictims` | named victims, named groups, dates |
| `feodotracker.abuse.ch/.../ipblocklist.json` | live Emotet/QakBot/Dridex C2 |
| `threatfox.abuse.ch/export/json/recent/` | IOCs tied to a malware family |
| `haveibeenpwned.com/api/v3/breaches` | 1,031 disclosed breaches |

**ThreatFox needs no key.** A comment in `sources.py` said it did — true of the
*API*, false of the **bulk export**, which returned 3.9 MB unauthenticated.

`claim_url` on a ransomware.live record is a **Tor leak site serving stolen
data**. Never link it. Provenance points at ransomware.live's clearnet group
page, and a test asserts no `.onion` survives in a serialised event.

## `EntityKind.ORGANISATION` was necessary

A victim is not an `ASSET` — that kind means a resource *this* estate protects.
Filing a stranger's company there puts it on the topology map and lets blast
radius traverse into someone else's business. The existing comment in
`events.py` about external kinds never becoming topology nodes is the precedent.

## Three bugs found by deploying, not by reading

1. **Polled but never served.** `/intel` imported `FEEDS` from `sources.py`
   instead of the merged registry in `ingest.py`. All four feeds polled fine,
   wrote 44 real events, and were filtered out of the only endpoint that reads
   them. Every piece worked; the site showed nothing. The test now asserts
   polled and served are the **same set** — a subset check passes the mirror
   image of this bug.
2. **Breaches dated to the breach, not the disclosure.** Sorted every HIBP
   record off the end of a recency timeline. The event recorded is "this was
   published"; the breach date is a label.
3. **R56's active/offline split assumed every feed reports liveness.** `active`
   was `status == "online"`, so ransomware claims and disclosed breaches — which
   are neither up nor gone — evaluated false and were swept into a panel headed
   "Gone offline". Four of six feeds were live on the site and unreachable.
   Liveness is three-state now; **absent is not offline**. HIBP had compounded
   it by using `status` to mean *verified* — now `confirmation`.

`status` is load-bearing across feeds. Do not overload it.

## Still to do

- **R89** reported attacks as first-class (they are currently mixed into the
  Observatory, where URLhaus volume dominates — `LIMIT` had to go 60 → 200 just
  to surface them)
- **R90** the honeypot on the Oracle free VM
- **R91** real incidents with the full loop
- **R92** delete the scripted scenarios — *last*, because deleting first leaves
  `/incidents`, `/overview`, `/blue-team` and `/actions` empty. Blue team scores
  against a known answer and has none for a real incident; that has to be
  resolved, not discovered.
- **R93** a read must not write to the audit ledger — 143 of 299 records were
  the same page-view line

See [[ObservatoryGrouping]] and [[BuildAttribution]] for the same verification
pattern: compare two independently computed values, never let the checker
supply the answer.
