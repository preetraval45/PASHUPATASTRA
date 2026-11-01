"use client";

import { useState, type FormEvent } from "react";

import { ACCENT_CHOICES, OrgLogo, accentVar } from "@/components/orgbrand";
import { AccountFailure, saveCompanySettings, type OrgSettings } from "@/lib/account";
import { MODULES } from "@/lib/training";

/**
 * Customize a company: its name, accent colour, logo, the welcome its people
 * see, and the training levels it requires by a date. For owners and admins,
 * on the team dashboard. A live preview shows the result before saving.
 */
export function CustomizePanel({
  orgId,
  name: savedName,
  settings: saved,
  onSaved,
}: {
  orgId: string;
  name: string;
  settings: OrgSettings;
  onSaved: () => void;
}) {
  const [open, setOpen] = useState(false);
  const [name, setName] = useState(savedName);
  const [accent, setAccent] = useState(saved.accent);
  const [logo, setLogo] = useState(saved.logo ?? "");
  const [welcome, setWelcome] = useState(saved.welcome);
  const [required, setRequired] = useState<string[]>(saved.required);
  const [due, setDue] = useState(saved.due ?? "");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<{ ok: boolean; text: string } | null>(null);

  const draft: OrgSettings = { accent, logo: logo.trim() || null, welcome, required, due: due || null };
  const field =
    "w-full rounded-xl border border-[rgb(var(--edge-strong))] bg-[rgb(var(--ground))] px-3.5 py-2.5 text-sm outline-none focus:border-[rgb(var(--astra))]";

  const save = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setMessage(null);
    try {
      await saveCompanySettings(orgId, { name, ...draft });
      setMessage({ ok: true, text: "Saved. Your team sees it the next time they open the app." });
      onSaved();
    } catch (err) {
      setMessage({ ok: false, text: err instanceof AccountFailure ? err.message : "Couldn't save. Try again." });
    } finally {
      setBusy(false);
    }
  };

  return (
    <section className="rounded-3xl border border-[rgb(var(--edge))] bg-[rgb(var(--panel))]">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
        className="focusable flex w-full items-center gap-3 rounded-3xl px-5 py-4 text-left"
      >
        <OrgLogo name={savedName} settings={saved} size={36} />
        <span className="min-w-0 flex-1">
          <span className="block font-semibold">Customize your workspace</span>
          <span className="block text-xs text-[rgb(var(--muted))]">Name, colour, logo, welcome message and required training</span>
        </span>
        <span aria-hidden="true" className="text-[rgb(var(--faint))]">{open ? "▴" : "▾"}</span>
      </button>
      {open && (
        <form onSubmit={save} className="rise grid gap-6 border-t border-[rgb(var(--edge))] p-5 lg:grid-cols-[1fr_18rem]">
          <div className="space-y-5">
            <label className="block text-sm">
              <span className="mb-1.5 block font-medium">Company name</span>
              <input className={field} value={name} onChange={(e) => setName(e.target.value)} maxLength={80} required />
            </label>

            <fieldset>
              <legend className="mb-2 text-sm font-medium">Accent colour</legend>
              <div className="flex flex-wrap gap-2">
                {ACCENT_CHOICES.map((c) => (
                  <label
                    key={c.id}
                    className={`flex cursor-pointer items-center gap-2 rounded-full border px-3 py-1.5 text-xs transition ${
                      accent === c.id ? "border-[rgb(var(--ink))]/60 bg-[rgb(var(--raised))]" : "border-[rgb(var(--edge))]"
                    }`}
                  >
                    <input type="radio" name="accent" className="sr-only" checked={accent === c.id} onChange={() => setAccent(c.id)} />
                    <span aria-hidden="true" className="h-4 w-4 rounded-full" style={{ background: `rgb(${accentVar(c.id)})` }} />
                    {c.label}
                  </label>
                ))}
              </div>
              <p className="mt-1.5 text-xs text-[rgb(var(--faint))]">Used across the app for everyone in your company.</p>
            </fieldset>

            <label className="block text-sm">
              <span className="mb-1.5 block font-medium">Logo address</span>
              <input
                className={field}
                type="url"
                placeholder="https://yourcompany.com/logo.png"
                value={logo}
                onChange={(e) => setLogo(e.target.value)}
                maxLength={400}
              />
              <span className="mt-1.5 block text-xs text-[rgb(var(--faint))]">An https:// image. Leave empty to use your initials.</span>
            </label>

            <label className="block text-sm">
              <span className="mb-1.5 block font-medium">Welcome message</span>
              <textarea
                className={`${field} min-h-[5rem] resize-y`}
                placeholder="e.g. Welcome to Northwind's security training. Finish the required levels by the end of the month."
                value={welcome}
                onChange={(e) => setWelcome(e.target.value)}
                maxLength={600}
              />
            </label>

            <fieldset>
              <legend className="mb-2 text-sm font-medium">Required training</legend>
              <div className="grid gap-1.5 sm:grid-cols-2">
                {MODULES.map((m) => (
                  <label key={m.slug} className="flex cursor-pointer items-center gap-2.5 rounded-lg px-2 py-1.5 text-sm hover:bg-[rgb(var(--raised))]">
                    <input
                      type="checkbox"
                      checked={required.includes(m.slug)}
                      onChange={(e) =>
                        setRequired((r) => (e.target.checked ? [...r, m.slug] : r.filter((s) => s !== m.slug)))
                      }
                      className="h-4 w-4 accent-[rgb(var(--astra))]"
                    />
                    <span className="tnum text-[rgb(var(--faint))]">{m.level}</span>
                    <span className="min-w-0 truncate">{m.title}</span>
                  </label>
                ))}
              </div>
              <div className="mt-2 flex flex-wrap gap-2">
                <button type="button" onClick={() => setRequired(MODULES.map((m) => m.slug))} className="focusable rounded-lg border border-[rgb(var(--edge))] px-2.5 py-1 text-xs">
                  Require all
                </button>
                <button type="button" onClick={() => setRequired([])} className="focusable rounded-lg border border-[rgb(var(--edge))] px-2.5 py-1 text-xs">
                  Clear
                </button>
              </div>
            </fieldset>

            <label className="block text-sm">
              <span className="mb-1.5 block font-medium">Due date</span>
              <input className={`${field} max-w-[12rem]`} type="date" value={due} onChange={(e) => setDue(e.target.value)} />
              <span className="mt-1.5 block text-xs text-[rgb(var(--faint))]">Optional. People behind after this date show as overdue.</span>
            </label>
          </div>

          <div className="space-y-3">
            <p className="label">Preview</p>
            <div className="rounded-2xl border border-[rgb(var(--edge))] bg-[rgb(var(--ground))] p-4">
              <div className="flex items-center gap-3">
                <OrgLogo name={name || savedName} settings={draft} size={40} />
                <span className="font-semibold">{name || savedName}</span>
              </div>
              {welcome && <p className="mt-3 text-sm text-[rgb(var(--muted))]">{welcome}</p>}
              <p className="mt-3 text-xs text-[rgb(var(--muted))]">
                {required.length ? `${required.length} required ${required.length === 1 ? "level" : "levels"}` : "No required levels"}
                {due ? ` · due ${due}` : ""}
              </p>
              <span
                className="mt-3 inline-block rounded-xl px-3.5 py-2 text-xs font-semibold text-white"
                style={{ background: `rgb(${accentVar(accent)})` }}
              >
                Continue training
              </span>
            </div>
            {message && (
              <p
                role="status"
                className={`rounded-xl border px-3 py-2 text-sm ${message.ok ? "border-[rgb(var(--ok))]/40 bg-[rgb(var(--ok))]/10" : "border-[rgb(var(--crit))]/40 bg-[rgb(var(--crit))]/10"}`}
              >
                {message.text}
              </p>
            )}
            <button
              type="submit"
              disabled={busy}
              className="focusable w-full rounded-xl px-4 py-2.5 text-sm font-semibold text-white disabled:opacity-60"
              style={{ background: `rgb(${accentVar(accent)})` }}
            >
              {busy ? "Saving…" : "Save changes"}
            </button>
          </div>
        </form>
      )}
    </section>
  );
}
