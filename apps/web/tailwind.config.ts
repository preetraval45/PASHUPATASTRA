import type { Config } from "tailwindcss";

export default {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}", "./lib/**/*.{ts,tsx}"],
  theme: {
    extend: {
      screens: {
        // The width the header's seven nav labels stop colliding with the
        // search box. Measured, not chosen. The gap between the last label and
        // the search field: -7px at 1100, +5px at 1120, +38px at 1160. This
        // used to be `lg`, where "Actions" sits underneath the field outright.
        // 1160 rather than 1120 because five pixels is
        // not clearance — it is the same collision waiting for a font to load
        // slightly wider. There is no default breakpoint between `lg` and
        // `xl`, and `xl` would hand every laptop from 1024 to 1280 a hamburger
        // menu it has the room not to need.
        nav: "1160px",
      },
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
