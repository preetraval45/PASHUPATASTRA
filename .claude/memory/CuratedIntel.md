# Retrieval beats recollection

- **Date:** 2026-08-21
- **Phase:** Phase 4 — R26
- **Commit(s):** pending

## What changed

The chat agent answers questions about vulnerabilities from the ingested
advisories rather than from what the model remembers.

## The test that mattered

Two questions, and only the second one proves anything.

- `CVE-2026-69836` — ingested by the hourly poll. Answered from the stored
  advisory, citing the stored event id. Grounded, nothing dropped.
- `CVE-2021-44228` — **not** in the store, and known by heart to every model of
  this generation. *"I have no stored advisory for CVE-2021-44228 in the
  evidence repository, so I cannot provide details about it or its severity."*
  `answerable: false`, cited nothing, and not one of Log4j / Log4Shell / JNDI /
  LDAP in the reply.

The first result alone would have proved only that retrieval agreed with what
the model already thought. **Test the case where the two disagree.**

## Decisions made

- **Retrieved before the model is asked**, not by the model choosing to look. A
  model asked about a CVE already has an opinion, and an opinion is what it
  gives when nothing better is in front of it. Up-front retrieval makes the
  grounded answer the easy one rather than the disciplined one.
- **An unknown identifier produces no evidence block at all.** A block reading
  "nothing on file for CVE-X" hands the model a ref to cite for a claim about
  nothing — an answer that looks grounded while resting on an absence.
- **The extraction pattern is narrow on purpose**: word-bounded CVE ids only. A
  looser pattern would turn every question into a lookup of whatever string it
  contained, which on a public console is an interface for asking which of *our*
  entities exist. A CVE id is a public identifier for a public document.
- **The tool validates rather than passes through.** Without it the argument is
  an arbitrary string reaching `entity_events`, and `account:j.rivera` is an
  arbitrary string.
- **Prompt version 3**, which retires every answer cached under 2.

## Copy discipline

This is retrieval over a curated corpus. No weights changed, nothing was
fine-tuned, and nothing in the product describes the agent as *learning*. The
only "Learn" on the site is the platform's own Observe → … → Learn loop, which
is a different claim and predates this.

## A recurring hazard in this session

Bash heredocs mangle backslash escapes: `\b` became a literal backspace inside a
regex (which then silently matched nothing), and `\n` inside f-strings became
real newlines and broke the files. When patching Python that contains escapes,
write the block to a file and splice it, or build the string with `chr(92)`.

## Open questions

- The Groq key was pasted into a chat window on 21 August 2026. **Rotate it.**

## Next session should

- **R27** — Blue Team mode: show only the first alert, let the player choose
  what to investigate and which read-only action to run, score the diagnosis,
  reveal the chain at the end.
