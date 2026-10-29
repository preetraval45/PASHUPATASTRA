"use client";

import {
  getKatyayaniCases,
  getServerIncidents,
  getTreeExamples,
  rankKatyayani,
  runServerIncident,
  runTreeExample,
} from "@/lib/api";
import { MODELS } from "@/lib/navadurga";

/**
 * The nine Sati models as specialists inside Sati AI.
 *
 * Two answer typed questions (Brahmacharini, Skandamata). Six read data rather
 * than words: log sessions, network flows, incidents, server metrics. For them
 * the chat offers held-out examples the model never trained on; tapping one
 * runs the served model live and replies with its verdict, the truth beside it,
 * and why. Kushmanda is not served publicly yet and says so.
 */
export type SpecialistKind = "auto" | "ask" | "tree" | "cases" | "servers" | "private";

export type Specialist = {
  id: string;
  name: string;
  job: string;
  kind: SpecialistKind;
  /** The Sati AI model id, for specialists that answer questions. */
  model?: string;
  /** What the example strip offers, for specialists that read data. */
  pick?: string;
};

const job = (name: string) => MODELS.find((m) => m.name === name)?.job.split(" — ")[0] ?? "";

export const SPECIALISTS: Specialist[] = [
  { id: "auto", name: "Sati", job: "Ask anything — routed to the right model", kind: "auto" },
  { id: "brahmacharini", name: "Brahmacharini", job: "Names the ATT&CK technique for a behaviour", kind: "ask", model: "sati:brahmacharini" },
  { id: "skandamata", name: "Skandamata", job: "The defences that stop it", kind: "ask", model: "sati:skandamata" },
  { id: "katyayani", name: "Katyayani", job: job("Katyayani") || "Root-cause ranking", kind: "cases", pick: "a real incident it never saw" },
  { id: "kalaratri", name: "Kalaratri", job: job("Kalaratri") || "Log anomaly detection", kind: "tree", pick: "a held-out log session" },
  { id: "chandraghanta", name: "Chandraghanta", job: job("Chandraghanta") || "Network intrusion alerting", kind: "tree", pick: "a flow from unseen attack days" },
  { id: "shailaputri", name: "Shailaputri", job: job("Shailaputri") || "Metric anomaly detection", kind: "servers", pick: "an incident on an unseen server" },
  { id: "siddhidatri", name: "Siddhidatri", job: job("Siddhidatri") || "Fusion", kind: "servers", pick: "an incident on an unseen server" },
  { id: "mahagauri", name: "Mahagauri", job: job("Mahagauri") || "Verification", kind: "servers", pick: "an incident on an unseen server" },
  { id: "kushmanda", name: "Kushmanda", job: job("Kushmanda") || "Sati's own language model", kind: "private" },
];

export function specialist(id: string): Specialist {
  return SPECIALISTS.find((s) => s.id === id) ?? SPECIALISTS[0];
}

export type Example = { id: string; label: string };

/** The held-out examples a data-reading specialist can be run on. */
export async function examplesFor(s: Specialist): Promise<Example[] | null> {
  if (s.kind === "tree") {
    const d = await getTreeExamples(s.id as "kalaratri" | "chandraghanta");
    return d ? d.examples.map((e) => ({ id: e.id, label: e.label })) : null;
  }
  if (s.kind === "cases") {
    const d = await getKatyayaniCases();
    return d ? d.cases.slice(0, 24).map((c) => ({ id: c.id, label: `${c.system} · ${c.services} services` })) : null;
  }
  if (s.kind === "servers") {
    const d = await getServerIncidents();
    return d ? d.incidents.slice(0, 24).map((i) => ({ id: i.id, label: `${i.machine} · ${i.length} min` })) : null;
  }
  return null;
}

function ordinal(n: number): string {
  const teen = n % 100 >= 11 && n % 100 <= 13;
  return `${n}${teen ? "th" : ({ 1: "st", 2: "nd", 3: "rd" } as Record<number, string>)[n % 10] ?? "th"}`;
}

/** Runs the specialist on one example and writes its reply as plain text for the answer formatter. */
export async function runSpecialist(s: Specialist, exampleId: string): Promise<string | null> {
  if (s.kind === "tree") {
    const r = await runTreeExample(s.id as "kalaratri" | "chandraghanta", exampleId);
    if (!r) return null;
    const what = s.id === "kalaratri" ? ["anomalous", "normal"] : ["an attack", "benign"];
    const lines = [
      `${r.correct ? "Right" : "Wrong"}: ${s.name} called ${r.example} ${r.flagged ? what[0] : what[1]}, and it is ${r.truth ? what[0] : what[1]} (${r.label}).`,
      "",
      `Score ${r.score.toFixed(4)} against its threshold of ${r.threshold.toFixed(4)}.`,
    ];
    if (r.why?.length) {
      lines.push("", "What moved the score most:");
      for (const w of r.why) lines.push(`- ${w.feature}: ${w.effect >= 0 ? "raised" : "lowered"} it by ${Math.abs(w.effect).toFixed(2)}`);
    }
    if (r.licence) lines.push("", r.licence);
    return lines.join("\n");
  }
  if (s.kind === "cases") {
    const r = await rankKatyayani(exampleId);
    if (!r) return null;
    const lines = [
      r.correct
        ? `Right: the root cause is ${r.root}, and Katyayani ranked it first.`
        : `The root cause was ${r.root}; Katyayani ranked it ${ordinal(r.position)}.`,
      "",
      `${r.system}, ${r.case}. Most likely first:`,
    ];
    r.ranking.slice(0, 5).forEach((x, i) =>
      lines.push(`${i + 1}. ${x.service}${x.service === r.root ? " (the true root)" : ""}: peak shift ${x.evidence.peak ?? "—"}σ, anomalous #${x.evidence.onset_rank ?? "—"}`),
    );
    return lines.join("\n");
  }
  if (s.kind === "servers") {
    const r = await runServerIncident(exampleId);
    if (!r) return null;
    const [start, end] = r.incident;
    const flagged = r.siddhidatri.flags.filter(Boolean).length;
    const verdict = {
      confirmed: `declared it over correctly, at minute ${r.mahagauri.declared_over}`,
      premature: `declared it over too early, at minute ${r.mahagauri.declared_over}`,
      unconfirmed: "did not declare it over, so a person decides",
    }[r.mahagauri.verdict];
    const rows = {
      shailaputri: `Shailaputri ${r.shailaputri.caught ? `caught it at minute ${r.shailaputri.first_flag}` : "missed it"}, with ${r.shailaputri.false_flags_before} false alarm${r.shailaputri.false_flags_before === 1 ? "" : "s"} before it.`,
      siddhidatri: `Siddhidatri, fusing three detectors, flagged ${flagged} of ${r.minutes} minutes.`,
      mahagauri: `Mahagauri ${verdict}.`,
    };
    const order = [s.id, ...Object.keys(rows).filter((k) => k !== s.id)] as (keyof typeof rows)[];
    return [
      `${r.machine}, a server none of them trained on: the incident ran from minute ${start} to ${end}.`,
      "",
      ...order.map((k) => `- ${rows[k]}`),
    ].join("\n");
  }
  return null;
}
