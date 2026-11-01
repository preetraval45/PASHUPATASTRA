"use client";

import { useEffect, useState } from "react";

import { initials, useAccount } from "@/components/account";
import type { OrgSettings } from "@/lib/account";

/**
 * A company's brand inside the product (adr/Accounts, customization): its logo
 * where its name appears, and its accent colour across the whole app for its
 * own people. Accents are chart hues validated for both themes (globals.css
 * --series-*), referenced by variable, so the light and dark steps follow the
 * theme switch by themselves.
 */

export const ACCENT_CHOICES: { id: OrgSettings["accent"]; label: string }[] = [
  { id: "default", label: "Teal (default)" },
  { id: "series-1", label: "Blue" },
  { id: "series-7", label: "Violet" },
  { id: "series-5", label: "Magenta" },
  { id: "series-2", label: "Orange" },
  { id: "series-6", label: "Green" },
];

export function accentVar(accent: OrgSettings["accent"]): string {
  // The site's own teal by a fixed token, since --astra itself is what a company accent replaces.
  return accent === "default" ? "var(--brand-teal)" : `var(--${accent})`;
}

/** The company's logo, or its initials in its accent when there is none or the image fails to load. */
export function OrgLogo({ name, settings, size = 40 }: { name: string; settings: OrgSettings; size?: number }) {
  const [broken, setBroken] = useState(false);
  useEffect(() => setBroken(false), [settings.logo]);
  const box = { width: size, height: size };
  if (settings.logo && !broken) {
    return (
      // A company's own image, from its own address: no optimisation proxy, no referrer sent.
      // eslint-disable-next-line @next/next/no-img-element
      <img
        src={settings.logo}
        alt={`${name} logo`}
        style={box}
        referrerPolicy="no-referrer"
        onError={() => setBroken(true)}
        className="shrink-0 rounded-xl border border-[rgb(var(--edge))] bg-white object-contain p-1"
      />
    );
  }
  return (
    <span
      aria-hidden="true"
      style={{ ...box, background: `rgb(${accentVar(settings.accent)})`, fontSize: size * 0.36 }}
      className="inline-flex shrink-0 items-center justify-center rounded-xl font-bold text-white"
    >
      {initials(name)}
    </span>
  );
}

/** Puts the signed-in member's company accent on the whole app. The first company with an accent wins. */
export function OrgTheme() {
  const { me } = useAccount();
  const accent = me?.orgs.find((o) => o.settings?.accent && o.settings.accent !== "default")?.settings.accent;
  useEffect(() => {
    const root = document.documentElement;
    if (accent) root.style.setProperty("--astra", `var(--${accent})`);
    else root.style.removeProperty("--astra");
  }, [accent]);
  return null;
}
