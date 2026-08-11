"use client";

import { useEffect, useState } from "react";

type Theme = "dark" | "light";

/**
 * Theme toggle.
 *
 * Dark is the default rather than "follow the system", because this is an
 * operations console: it is usually opened at night, and the service map reads
 * better on a dark ground. Someone who wants light asks for it, and the choice
 * persists.
 */
export function ThemeToggle() {
  const [theme, setTheme] = useState<Theme>("dark");

  useEffect(() => {
    const stored = window.localStorage.getItem("theme");
    if (stored === "light" || stored === "dark") setTheme(stored);
  }, []);

  useEffect(() => {
    document.documentElement.setAttribute("data-theme", theme);
    window.localStorage.setItem("theme", theme);
  }, [theme]);

  return (
    <button
      type="button"
      onClick={() => setTheme((t) => (t === "dark" ? "light" : "dark"))}
      aria-label={`Switch to ${theme === "dark" ? "light" : "dark"} theme`}
      title={`Switch to ${theme === "dark" ? "light" : "dark"} theme`}
      className="focusable rounded border border-[rgb(var(--edge))] px-2 py-0.5 text-xs text-[rgb(var(--muted))] hover:text-[rgb(var(--ink))]"
    >
      <span aria-hidden="true">{theme === "dark" ? "☾" : "☀"}</span>
    </button>
  );
}

/**
 * Applies the stored theme before first paint. Without this the page renders
 * dark and then snaps to light, and a flash of the wrong theme on every
 * navigation is exactly the kind of thing that makes a tool feel unreliable.
 */
export const themeScript = `
(function () {
  try {
    var t = localStorage.getItem('theme');
    document.documentElement.setAttribute('data-theme', t === 'light' ? 'light' : 'dark');
  } catch (e) {
    document.documentElement.setAttribute('data-theme', 'dark');
  }
})();
`;
