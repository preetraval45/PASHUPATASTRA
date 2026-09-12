# O-1 visa roadmap — what this project can prove, and what it cannot

**What this file is.** A map from the eight O-1A evidentiary criteria to the
things this repository can produce, the things only the owner can do, and the
order they have to happen in. It was written on 12 September 2026 from two
outside reviews of the deployed site and an O-1A strategy document, all three
of which are folded into [REBUILD.md](REBUILD.md) as Phases 5E and 5F.

**What it is not.** Legal advice. Whether any piece of evidence clears a
criterion is an immigration attorney's judgement against the actual petition,
and USCIS weighs the whole record after the criteria are met — three ticks is a
threshold, not an approval. Nothing here should be built into a filing strategy
without that consult. What this file does is make sure that when the attorney
asks "what do you have", the answer is a set of things that survive being
checked.

**The rule that governs everything below** is the site's own: nothing typed,
everything recomputable. A petition exhibit is read by someone whose job is to
doubt it. A number on `/impact` that a script can recount from the store is
evidence; a number in a slide is a claim. The same applies outside the code —
no bought stars, no paid "coverage", no manufactured users, no benchmark result
that did not come from a run somebody else could repeat. Anything that would
not survive the honesty rule the console applies to itself does not go in the
petition either.

---

## The field, in one sentence

*AI-native security operations: correlating fragmented security telemetry into
one intrusion, mapping it to known adversary techniques, and proposing
remediation that a policy engine — not the model — decides whether a human must
authorise.*

That is the sentence every piece of evidence should support. The strategy
document's point about coherence is right: "software engineer plus data science
plus DevOps plus AI plus security" is a résumé, and one field with one artefact
behind it is a case. Everything the owner does that is not about this sentence
is not wasted, but it does not count here.

---

## The eight criteria, honestly

"Today" is what exists on 12 September 2026, not what is planned. "Repo tasks"
are the tasks in REBUILD.md that produce the evidence; "Owner" is what no
amount of engineering does on the owner's behalf.

| # | Criterion | Today | What would count | Repo tasks | Owner |
|---|---|---|---|---|---|
| 1 | Major awards | Nothing. | A win or finalist place in a *selective* AI/security competition, with the selectivity documented. A participation certificate counts for nothing and is worse than nothing in a file. | — | Enter competitions; keep the rules, the judge list, the entrant count. |
| 2 | Selective memberships | Nothing. | Membership that requires outstanding achievement judged by recognised experts. Most societies do not; joining one that does not is noise. | — | Only if a genuinely selective body fits. Do not join things to fill a row. |
| 3 | Published material *about* you | Nothing. The owner's own articles do not count here — they are authored *by* the beneficiary, and USCIS reads that distinction strictly. | An independent outlet, with editorial standing, naming the owner and the work. Trade press, university news, a podcast with an audience. | R107 `/impact`, R109 `/press` — make it easy to write about accurately. | Pitch it. A media kit lowers the cost for a journalist; it does not write the article. |
| 4 | Judging others' work | Nothing recorded. | Reviewing submissions — hackathon, capstone, workshop, conference — with the invitation, the rubric, the count of what was reviewed, and an organiser's letter. | Held: judging inside Blue Team needs accounts (S2). | Seek two or three engagements. Keep every artefact at the time, not afterwards. |
| 5 | Original contributions of major significance | The strongest ground and the least proven. The architecture is real and unusual — policy-bounded autonomy enforced structurally, citations verified rather than trusted, a debrief that distinguishes right from right-by-luck. Two reviewers said so independently. What does not exist is evidence anyone *else* relies on it. | Measured results from a study others could repeat; adoption by people the owner does not know; citations; expert letters that explain *why* it is novel rather than that the owner is capable. | R110 the study, R107 `/impact`, R108 citation, R111 README. The PIB benchmark and `docs/research/tables.md` already exist. | Recruit the study's participants. Get the work in front of people with standing. |
| 6 | Scholarly articles | A draft — [research/PAPER.md](research/PAPER.md) — that says on its first line it is not submittable, and why: two of four benchmark arms have no data, 31 of 104 scenarios execute, diagnosis quality is unmeasured. It is honest and it is unfinished. | A submitted paper, and better, an accepted one. arXiv establishes a public record and is not peer review; say which it is. | R110 produces the security-domain results the current draft lacks. `scripts/papertables.py` already generates tables from runs rather than transcribing them. | Decide: finish PAPER.md as an infrastructure paper, or write the security-operations paper around the study. Pick the venue. Submit. ROADMAP.md already records that submission is the owner's call, not a task done for them. |
| 7 | Critical role at a distinguished organisation | The owner's employment, which this repository knows nothing about and should not. | An employer letter describing the role's importance — systems designed, users served, business impact — not the title. Architecture, deployment and usage records that back the letter. | — | Collect it from the employer while employed there. This is the one criterion where waiting makes it harder. |
| 8 | High remuneration | Not now. | Compensation documented against the field's norms. | — | Later. |

The realistic shape of a case is four or five strong criteria, not eight thin
ones: **5 and 6** built on this project and its study, **4** from judging, **7**
from the employer, and **3** if the work earns coverage. That is the same
conclusion both strategy documents reached, and nothing found in the code
contradicts it.

---

## What two reviewers said, and what became of it

Both reviews are worth keeping because they are the closest thing to
independent evaluation the project has, and because a USCIS reader, a
journalist, or a professor will click the same links they did.

**Review 1** (SOC-analyst walkthrough, 11 September): the causal chain, the
blast-radius graph, the seven-stage trail and the live feeds are real and
labelled honestly; the assistant refused a direct injection and correctly
declined to isolate a host on an incident with none; the Blue Team scoring is
"legitimately good instructional design". Hit: 144 identical approval lines on
one incident, a 503 on the first request of every route, and a debrief
sentence that contradicts its board.

**Review 2** (page-by-page, 11 September): the action registry is "the best
page on the site" for showing rollback and reversibility; the Observatory
rendered "API unreachable" then `No feed named "undefined"`; the site should
move to a custom domain and name its author.

| Finding | Status | Task |
|---|---|---|
| 144 duplicate approval records | Cause found: the incident page writes three audit records per view | R93, then R98 |
| First-request 503 on every route | Not attributable from code; must be reproduced with headers first | R99 |
| Two to three seconds of skeleton per transition | Fifteen API calls in four sequential waves | R100 |
| `No feed named "undefined"` | Same 503, wrong message | R101 |
| Debrief contradicts score | Two resolvers for "decisive", and OR-scoring | R102 |
| NOT GROUNDED label on prose that can still assert an action | The prose is returned verbatim; label is post hoc | R103 |
| No adversarial regression suite | Battery has four cases, no injection | R103 |
| "86% confidence asserted, not earned" | Scenario-author literals, unlabelled | R105; calibration proper waits for R96 |
| Token/cost dashboard | Per-turn data exists, no roll-up | R104 |
| No author, no OG, no how-it-works | **Already shipped** (R57, R16, R54) — reviewer read an older build | none |
| Mobile "unverified" | Verified at four widths (R14, R67) | none |
| Impact dashboard, cite widget, DOI, media kit, domain | None exist; a draft paper and generated benchmark tables do | R107, R108, R109, R112 |

---

## Sequence

Adapted from the strategy document's twelve months to what this repository can
actually deliver in each band, and what has to come from the owner. Bands
overlap; the order inside each is what matters.

**Now — before anyone else is pointed at the link.** Phase 5E. Fix what the
reviewers hit. A professor or an editor who clicks through to an incident page
with 144 identical lines, or an Observatory that says "unreachable", has
finished evaluating. This is a fortnight of work and it precedes everything.

**Then — packaging what already exists.** Phase 5F. `/impact` from real
counts, `CITATION.cff`, `/press`, the README as a research page. Mostly
assembly. Two of these are blocked on decisions only the owner can make — see
below.

**Months 1–3 — the study.** R110 builds the apparatus; the owner recruits ten
to thirty people who are not friends — students, analysts, engineers — and
runs the protocol in `docs/research/STUDY.md`. The output is the first number
about this system that did not come from its author: how long it takes a
person to reach a correct diagnosis with the console, what they open, where
they go wrong. That number is what §7 of the paper has been waiting for.

**Months 2–5 — the paper.** Written from the study and the existing benchmark.
The infrastructure draft's §9 lists what it lacks; the security-operations
version has the study instead. One good paper with a citation trail beats three
nobody reads, and the owner decides which paper it is. Preprint to arXiv
(cs.CR) once it is submittable by its own first line; peer-reviewed venue in
parallel.

**Months 3–8 — recognition.** Talks at university departments, IEEE and ACM
chapters, security meetups. Demo submissions — BSides, DEF CON Demo Labs,
Black Hat Arsenal — where the thing is judged by people who do this for a
living. Judging engagements sought in the same rooms. Every invitation, rubric
and audience count kept the day it arrives.

**Months 4–10 — adoption and coverage.** The repository public with a licence,
the README pointing at the paper and the live site, a DOI on a release.
Independent users and organisations, documented as they appear. Coverage
pitched with `/press`, never bought.

**Months 8–12 — the package.** Only now: the attorney, the criteria actually
met, the gaps that remain. Evidence has to exist at filing; nothing promised
counts.

---

## Decisions only the owner can make

Each of these blocks a task, and the task says so rather than working around
it.

1. **A licence.** README says "to be added once clearance completes". Zenodo
   will not mint a DOI without one, GitHub's citation panel is weaker without
   one, and "open-source" in the field description is a claim the repository
   currently cannot back. This blocks **R108** and everything under adoption.
2. **A domain.** Plain `pashupatastra.com` if it is free; the `.ai` is a
   price, not a signal, once the name already reads as a product. Blocks
   **R112**. Take the matching GitHub and LinkedIn handles at the same time.
3. **Which paper.** Finish the infrastructure draft, or write the
   security-operations paper around the study. Both are honest; the second is
   the one the deployed site demonstrates.
4. **Study recruitment.** R110 builds the instrument; people are the owner's to
   find. Not friends, and it must say so in the protocol.
5. **A Zenodo release.** A tag, a release, the Zenodo toggle — minutes, once
   the licence exists.

---

## Where the evidence lives

Not in this repository. Invitations, letters, employer documents and coverage
are personal records and some of them are other people's; the repository is
public and holds only what is public. Keep a folder outside it, one
subdirectory per criterion, and file each item the day it arrives with the
date and the source URL — an exhibit reconstructed a year later from memory is
the kind of evidence this whole file exists to avoid.

What the repository does hold is the checkable half: the code, the benchmark
runs, the generated tables, the study protocol and its report script, the
citation file, and the tasks in REBUILD.md with their evidence lines. When a
letter says the architecture is novel, this is what it points at.
