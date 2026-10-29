"use client";

import { useEffect, useState } from "react";

import { installedBuild, releasedBuild } from "@/lib/appbuild";

/**
 * "A new version of the app is ready", inside the Android app only.
 *
 * Pages come from the live site, but the app itself (its icon, shortcuts and
 * native features) only changes when a newer APK is installed. The app names
 * its build in its user agent ("PashupatastraApp/0.1.<build>"); the latest
 * build is the title of the repository's `android` release. When the release
 * is newer, this offers it in one tap. Asked at most once an hour per device.
 */
const RELEASE = "https://api.github.com/repos/preetraval45/PASHUPATASTRA/releases/tags/android";
const APK = "https://github.com/preetraval45/PASHUPATASTRA/releases/download/android/Pashupatastra.apk";
const KEY = "pashu.app.latest";

export function AppUpdate() {
  const [latest, setLatest] = useState<number | null>(null);
  const [installed, setInstalled] = useState<number | null>(null);

  useEffect(() => {
    const mine = installedBuild(navigator.userAgent);
    setInstalled(mine);
    if (mine === null) return;
    try {
      const kept = JSON.parse(localStorage.getItem(KEY) ?? "null") as { build: number; at: number } | null;
      if (kept && Date.now() - kept.at < 3_600_000) {
        setLatest(kept.build);
        return;
      }
    } catch {
      // Ask again.
    }
    fetch(RELEASE, { headers: { Accept: "application/vnd.github+json" } })
      .then((r) => (r.ok ? r.json() : null))
      .then((release: { name?: string } | null) => {
        const build = release?.name ? releasedBuild(release.name) : null;
        if (build === null) return;
        setLatest(build);
        try {
          localStorage.setItem(KEY, JSON.stringify({ build, at: Date.now() }));
        } catch {
          // Not remembered.
        }
      })
      .catch(() => {
        // Offline or rate-limited: no banner, nothing broken.
      });
  }, []);

  if (installed === null || latest === null || latest <= installed) return null;
  return (
    <a
      href={APK}
      className="focusable rise flex items-center gap-3 rounded-2xl border border-[rgb(var(--astra))]/50 bg-[rgb(var(--astra))]/10 p-4 text-sm"
    >
      <span aria-hidden="true" className="inline-flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-[rgb(var(--astra))] text-lg text-[rgb(var(--ground))]">
        ↓
      </span>
      <span className="min-w-0 flex-1">
        <span className="block font-semibold">An update is ready</span>
        <span className="block text-xs text-[rgb(var(--muted))]">
          Build {latest} (you have {installed}). Tap to download, then open it to install over this one.
        </span>
      </span>
    </a>
  );
}
