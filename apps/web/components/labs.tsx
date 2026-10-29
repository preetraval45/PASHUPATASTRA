"use client";

import Link from "next/link";
import { useState, type ReactNode } from "react";

/**
 * Hands-on labs: learning by doing the analyst's work, not by reading about it.
 *
 * Each lab is a small realistic artefact (an email, a sign-in log, a set of
 * observed behaviours) where the learner finds the evidence themselves and
 * gets an explanation the moment they act. Everything is fictional and uses
 * reserved example domains and documentation address ranges (RFC 2606,
 * RFC 5737), so nothing here points at a real person or system. Techniques
 * are MITRE ATT&CK's own identifiers.
 */

// --- Phishing inspector -----------------------------------------------------

const FLAGS = {
  sender: "The sender is 'rn1crosoft-billing.example', not microsoft.com. 'rn' reads as 'm' and '1' as 'i' at a glance: a look-alike domain.",
  urgency: "A deadline of hours and a threat to suspend the account. Pressure to act before thinking is the most common phishing lever.",
  greeting: "'Dear user' instead of your name. A real provider that bills you knows who you are.",
  link: "The button says 'Microsoft 365' but goes to secure-login-verify.example/ms365. Always read where a link goes, not what it says.",
  attachment: "An 'invoice' as .html. HTML attachments open a fake sign-in page locally, which slips past many link scanners.",
} as const;
type Flag = keyof typeof FLAGS;

function Spot({ id, found, onFind, children }: { id: Flag; found: boolean; onFind: (id: Flag) => void; children: ReactNode }) {
  return (
    <button
      type="button"
      onClick={() => onFind(id)}
      className={`focusable rounded px-0.5 text-left transition ${
        found
          ? "bg-[rgb(var(--crit))]/15 text-[rgb(var(--ink))] ring-1 ring-[rgb(var(--crit))]/50"
          : "hover:bg-[rgb(var(--astra))]/10"
      }`}
    >
      {children}
    </button>
  );
}

function PhishingLab() {
  const [found, setFound] = useState<Flag[]>([]);
  const [last, setLast] = useState<Flag | null>(null);
  const [decision, setDecision] = useState<string | null>(null);
  const find = (id: Flag) => {
    setLast(id);
    setFound((f) => (f.includes(id) ? f : [...f, id]));
  };
  const total = Object.keys(FLAGS).length;
  return (
    <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_18rem]">
      <article className="rounded-xl border border-[rgb(var(--edge-strong))] bg-[rgb(var(--ground))] text-sm">
        <header className="space-y-1 border-b border-[rgb(var(--edge))] p-4">
          <p className="text-base font-semibold">
            <Spot id="urgency" found={found.includes("urgency")} onFind={find}>
              Action required: your mailbox will be suspended in 4 hours
            </Spot>
          </p>
          <p className="text-[rgb(var(--muted))]">
            From: Microsoft 365 Billing &lt;
            <Spot id="sender" found={found.includes("sender")} onFind={find}>
              billing@rn1crosoft-billing.example
            </Spot>
            &gt;
          </p>
          <p className="text-xs text-[rgb(var(--faint))]">To: you@northwind.example · Today 07:42</p>
        </header>
        <div className="space-y-3 p-4 leading-relaxed text-[rgb(var(--muted))]">
          <p>
            <Spot id="greeting" found={found.includes("greeting")} onFind={find}>
              Dear user,
            </Spot>
          </p>
          <p>
            We could not process the payment for your subscription. To avoid losing access to your email and files, confirm
            your details today.
          </p>
          <p>
            <Spot id="link" found={found.includes("link")} onFind={find}>
              <span className="inline-block rounded-md bg-[#2f6fed] px-3 py-1.5 font-medium text-white">Sign in to Microsoft 365</span>
              <span className="mt-1 block text-[11px] text-[rgb(var(--faint))]">↳ secure-login-verify.example/ms365</span>
            </Spot>
          </p>
          <p className="flex items-center gap-2 border-t border-[rgb(var(--edge))] pt-3 text-xs">
            <span aria-hidden="true">📎</span>
            <Spot id="attachment" found={found.includes("attachment")} onFind={find}>
              Invoice_0427.html
            </Spot>
          </p>
        </div>
      </article>

      <aside className="space-y-3">
        <p className="text-sm">
          <strong className="tnum">{found.length}</strong> of {total} red flags found. Tap anything suspicious in the email.
        </p>
        <div className="h-1.5 overflow-hidden rounded-full bg-[rgb(var(--raised))]">
          <div className="h-full rounded-full bg-[rgb(var(--astra))] transition-all duration-500" style={{ width: `${(found.length / total) * 100}%` }} />
        </div>
        {last && (
          <p key={last} className="rise rounded-lg border border-[rgb(var(--crit))]/40 bg-[rgb(var(--crit))]/5 p-3 text-sm leading-relaxed">
            {FLAGS[last]}
          </p>
        )}
        {found.length === total && (
          <div className="rise space-y-2 rounded-lg border border-[rgb(var(--edge))] p-3 text-sm">
            <p className="font-medium">All five found. What do you do?</p>
            {[
              ["report", "Report it with the phish button, then delete it", true],
              ["reply", "Reply and ask if it is real", false],
              ["click", "Click the link but don't type anything", false],
            ].map(([id, label, right]) => (
              <button
                key={id as string}
                type="button"
                onClick={() => setDecision(id as string)}
                className={`focusable block w-full rounded-md border px-3 py-2 text-left transition ${
                  decision === id
                    ? right
                      ? "border-[rgb(var(--ok))]/60 bg-[rgb(var(--ok))]/10"
                      : "border-[rgb(var(--crit))]/60 bg-[rgb(var(--crit))]/10"
                    : "border-[rgb(var(--edge))] hover:bg-[rgb(var(--raised))]"
                }`}
              >
                {label as string}
              </button>
            ))}
            {decision && (
              <p className="text-[rgb(var(--muted))]">
                {decision === "report"
                  ? "Right. Reporting lets the security team block it for everyone and find who else received it."
                  : decision === "reply"
                    ? "Replying confirms your address is live and reaches the attacker. Check through a channel you already trust instead."
                    : "Opening the page alone can fingerprint your browser or try an exploit. Don't open it."}
              </p>
            )}
          </div>
        )}
        <Link href="/training/phishing" className="focusable inline-block rounded text-xs text-[rgb(var(--astra))] hover:underline">
          The full phishing level →
        </Link>
      </aside>
    </div>
  );
}

// --- Log detective -------------------------------------------------------------

const LOG = [
  { t: "09:02:11", user: "a.chen", ip: "198.51.100.23", geo: "Charlotte, US", ok: true, bad: false },
  { t: "09:14:40", user: "j.rivera", ip: "203.0.113.77", geo: "Unknown ASN", ok: false, bad: true },
  { t: "09:14:41", user: "m.patel", ip: "203.0.113.77", geo: "Unknown ASN", ok: false, bad: true },
  { t: "09:14:41", user: "s.okafor", ip: "203.0.113.77", geo: "Unknown ASN", ok: false, bad: true },
  { t: "09:15:03", user: "a.chen", ip: "198.51.100.23", geo: "Charlotte, US", ok: false, bad: false },
  { t: "09:15:09", user: "a.chen", ip: "198.51.100.23", geo: "Charlotte, US", ok: true, bad: false },
  { t: "09:16:20", user: "l.novak", ip: "203.0.113.77", geo: "Unknown ASN", ok: false, bad: true },
  { t: "09:16:21", user: "j.rivera", ip: "203.0.113.77", geo: "Unknown ASN", ok: true, bad: true },
  { t: "09:31:55", user: "j.rivera", ip: "192.0.2.140", geo: "Lagos, NG", ok: true, bad: true },
  { t: "09:40:12", user: "k.ito", ip: "198.51.100.61", geo: "Charlotte, US", ok: true, bad: false },
] as const;

function LogLab() {
  const [picked, setPicked] = useState<number[]>([]);
  const [checked, setChecked] = useState(false);
  const toggle = (i: number) => {
    if (checked) return;
    setPicked((p) => (p.includes(i) ? p.filter((x) => x !== i) : [...p, i]));
  };
  const right = LOG.map((l, i) => (l.bad ? i : -1)).filter((i) => i >= 0);
  const hits = picked.filter((i) => LOG[i].bad).length;
  const wrong = picked.filter((i) => !LOG[i].bad).length;
  return (
    <div className="space-y-4">
      <p className="text-sm text-[rgb(var(--muted))]">
        A sign-in log from a fictional company. Select every line that is part of an attack, then check. Hint: look at who,
        from where, and how fast.
      </p>
      <div className="overflow-x-auto rounded-xl border border-[rgb(var(--edge-strong))]">
        <table className="mono w-full min-w-[34rem] text-xs">
          <thead>
            <tr className="text-left text-[rgb(var(--faint))]">
              {["", "time", "user", "source address", "location", "result"].map((h) => (
                <th key={h} className="px-3 py-2 font-normal">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {LOG.map((l, i) => {
              const on = picked.includes(i);
              const tone = !checked
                ? on
                  ? "bg-[rgb(var(--astra))]/10"
                  : "hover:bg-[rgb(var(--raised))]"
                : l.bad
                  ? on
                    ? "bg-[rgb(var(--ok))]/10"
                    : "bg-[rgb(var(--warn))]/10"
                  : on
                    ? "bg-[rgb(var(--crit))]/10"
                    : "";
              return (
                <tr key={i} onClick={() => toggle(i)} className={`cursor-pointer border-t border-[rgb(var(--edge))] transition ${tone}`}>
                  <td className="px-3 py-2">
                    <input
                      type="checkbox"
                      checked={on}
                      onChange={() => toggle(i)}
                      aria-label={`Line ${i + 1}`}
                      className="accent-[rgb(var(--astra))]"
                    />
                  </td>
                  <td className="px-3 py-2 text-[rgb(var(--faint))]">{l.t}</td>
                  <td className="px-3 py-2">{l.user}</td>
                  <td className="px-3 py-2">{l.ip}</td>
                  <td className="px-3 py-2 text-[rgb(var(--muted))]">{l.geo}</td>
                  <td className={`px-3 py-2 ${l.ok ? "text-[rgb(var(--ok))]" : "text-[rgb(var(--crit))]"}`}>{l.ok ? "success" : "failed"}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      {!checked ? (
        <button
          type="button"
          disabled={picked.length === 0}
          onClick={() => setChecked(true)}
          className="focusable rounded-lg bg-[rgb(var(--astra))] px-4 py-2 text-sm font-medium text-[rgb(var(--ground))] transition hover:brightness-110 disabled:opacity-50"
        >
          Check my answer
        </button>
      ) : (
        <div className="rise space-y-2 rounded-xl border border-[rgb(var(--edge))] p-4 text-sm leading-relaxed">
          <p className="font-medium">
            {hits === right.length && wrong === 0
              ? "Spot on: all six attack lines, nothing else."
              : `You found ${hits} of ${right.length} attack lines${wrong ? `, and flagged ${wrong} normal one${wrong === 1 ? "" : "s"}` : ""}.`}
          </p>
          <p className="text-[rgb(var(--muted))]">
            One address, 203.0.113.77, tries a different user every second or two: <strong>password spraying</strong> (ATT&amp;CK
            T1110.003). It succeeds on j.rivera at 09:16:21. Fifteen minutes later j.rivera signs in from Lagos while the company
            is in Charlotte: the stolen account in use (T1078). a.chen&apos;s single failure then success is a typo, not an
            attack: one user, their usual address, seconds apart.
          </p>
          <button
            type="button"
            onClick={() => {
              setPicked([]);
              setChecked(false);
            }}
            className="focusable rounded text-xs text-[rgb(var(--astra))] hover:underline"
          >
            Try again
          </button>
        </div>
      )}
    </div>
  );
}

// --- Map it to ATT&CK -----------------------------------------------------------

const BEHAVIOURS = [
  { b: "A scheduled task runs a script from a temp folder every time anyone logs on.", answer: "T1053.005", options: ["T1053.005", "T1566.001", "T1486"] },
  { b: "Files on the shared drive are renamed to .locked and a ransom note appears.", answer: "T1486", options: ["T1003.001", "T1486", "T1110.003"] },
  { b: "An email with a macro-enabled Word document arrives at the finance team.", answer: "T1566.001", options: ["T1566.001", "T1078", "T1053.005"] },
  { b: "A tool reads the memory of lsass.exe on a domain controller.", answer: "T1003.001", options: ["T1486", "T1003.001", "T1566.001"] },
] as const;

const NAMES: Record<string, string> = {
  "T1053.005": "Scheduled Task",
  "T1486": "Data Encrypted for Impact",
  "T1566.001": "Spearphishing Attachment",
  "T1003.001": "LSASS Memory",
  "T1110.003": "Password Spraying",
  "T1078": "Valid Accounts",
};

function MappingLab() {
  const [answers, setAnswers] = useState<(string | null)[]>(BEHAVIOURS.map(() => null));
  const score = answers.filter((a, i) => a === BEHAVIOURS[i].answer).length;
  return (
    <div className="space-y-3">
      <p className="text-sm text-[rgb(var(--muted))]">
        Each line is something an analyst saw. Pick the ATT&amp;CK technique it is. Sati&apos;s Brahmacharini model does this
        for thousands of descriptions; here you do it.
      </p>
      {BEHAVIOURS.map((item, i) => {
        const chosen = answers[i];
        return (
          <div key={item.b} className="rounded-xl border border-[rgb(var(--edge))] bg-[rgb(var(--ground))] p-4">
            <p className="text-sm font-medium">{item.b}</p>
            <div className="mt-3 flex flex-wrap gap-2">
              {item.options.map((o) => {
                const tone =
                  chosen === null
                    ? "border-[rgb(var(--edge-strong))] hover:border-[rgb(var(--astra))]/60"
                    : o === item.answer
                      ? "border-[rgb(var(--ok))]/60 bg-[rgb(var(--ok))]/10"
                      : o === chosen
                        ? "border-[rgb(var(--crit))]/60 bg-[rgb(var(--crit))]/10"
                        : "border-[rgb(var(--edge))] opacity-50";
                return (
                  <button
                    key={o}
                    type="button"
                    disabled={chosen !== null}
                    onClick={() => setAnswers((a) => a.map((x, j) => (j === i ? o : x)))}
                    className={`focusable rounded-lg border px-3 py-1.5 text-left text-sm transition ${tone}`}
                  >
                    <span className="mono text-xs text-[rgb(var(--astra))]">{o}</span> {NAMES[o]}
                  </button>
                );
              })}
            </div>
          </div>
        );
      })}
      {answers.every((a) => a !== null) && (
        <p className="rise text-sm">
          <strong>{score} of {BEHAVIOURS.length}.</strong>{" "}
          <Link href="/ask?model=sati:brahmacharini" className="text-[rgb(var(--astra))] hover:underline">
            Now ask Brahmacharini about something you have seen →
          </Link>
        </p>
      )}
    </div>
  );
}

// --- The labs, as tabs -----------------------------------------------------------

const LABS = [
  { id: "phishing", title: "Phishing inspector", blurb: "Find the five red flags in a real-looking email", body: <PhishingLab /> },
  { id: "logs", title: "Log detective", blurb: "Spot an attack in a sign-in log", body: <LogLab /> },
  { id: "attack", title: "Map it to ATT&CK", blurb: "Name the technique behind what you saw", body: <MappingLab /> },
] as const;

export function Labs() {
  const [open, setOpen] = useState<string>(LABS[0].id);
  const lab = LABS.find((l) => l.id === open) ?? LABS[0];
  return (
    <div className="space-y-4">
      <div role="tablist" aria-label="Labs" className="grid gap-2 sm:grid-cols-3">
        {LABS.map((l, i) => (
          <button
            key={l.id}
            type="button"
            role="tab"
            aria-selected={l.id === open}
            onClick={() => setOpen(l.id)}
            className={`focusable lift rounded-xl border p-3.5 text-left transition ${
              l.id === open
                ? "border-[rgb(var(--astra))] bg-[rgb(var(--astra))]/10"
                : "border-[rgb(var(--edge))] bg-[rgb(var(--panel))] hover:border-[rgb(var(--astra))]/50"
            }`}
          >
            <span className="tnum text-xs text-[rgb(var(--faint))]">Lab {i + 1}</span>
            <span className="block font-semibold">{l.title}</span>
            <span className="block text-xs text-[rgb(var(--muted))]">{l.blurb}</span>
          </button>
        ))}
      </div>
      <div role="tabpanel" key={lab.id} className="rise rounded-2xl border border-[rgb(var(--edge))] bg-[rgb(var(--panel))] p-4 sm:p-6">
        {lab.body}
      </div>
    </div>
  );
}
