import type { Config } from "tailwindcss";

export default {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}", "./lib/**/*.{ts,tsx}"],
  theme: {
    extend: {
      // The fallbacks are real, not decoration: `display: swap` renders text in
      // them while the webfont loads, so a stack ending at `sans-serif` would
      // show a serif for that moment on some systems.
      fontFamily: {
        sans: ["var(--font-sans)", "ui-sans-serif", "system-ui", "Segoe UI", "Helvetica", "Arial", "sans-serif"],
        mono: ["var(--font-mono)", "ui-monospace", "SF Mono", "Cascadia Mono", "Menlo", "monospace"],
      },
    },
  },
  plugins: [],
} satisfies Config;
