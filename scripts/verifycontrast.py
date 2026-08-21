"""Measure the interface's contrast in a real browser, in both themes.

Contrast cannot be read off a palette. A status badge sets its text to
`--crit` and its background to `--crit` at 10% over a panel, so the colour that
actually lands behind the text exists only after compositing — and the palette
file says nothing about it.

So this asks the browser. For every element carrying text it takes the computed
colour, walks up the ancestors compositing background layers until something is
opaque, and computes the WCAG ratio against that.

Thresholds, per WCAG 2.1 AA:

  4.5:1  normal text
  3.0:1  large text (>=24px, or >=18.66px bold) and non-text graphics

The glyph in a status badge is measured as text because that is what it is —
a `▲` in a `<span>` — and holding it to the graphics threshold would be reading
the spec to get the answer we want.

Usage:  python scripts/verifycontrast.py [url]
"""

from __future__ import annotations

import argparse

DEFAULT_URL = "https://pashupatastra.vercel.app"

ROUTES = ["/", "/incidents/INC-2026-0901", "/infrastructure", "/actions", "/audit"]

THEMES = ["dark", "light"]

# Returns [{selector, color, background, ratio, size, bold, text}] for every
# text-bearing element on the page.
MEASURE = """
() => {
  const parse = (c) => {
    const m = c.match(/[\\d.]+/g);
    if (!m) return null;
    return [ +m[0], +m[1], +m[2], m.length > 3 ? +m[3] : 1 ];
  };
  const over = (fg, bg) => {
    const a = fg[3];
    return [ fg[0]*a + bg[0]*(1-a), fg[1]*a + bg[1]*(1-a), fg[2]*a + bg[2]*(1-a), 1 ];
  };
  const lum = ([r,g,b]) => {
    const f = (v) => { v /= 255; return v <= 0.03928 ? v/12.92 : Math.pow((v+0.055)/1.055, 2.4); };
    return 0.2126*f(r) + 0.7152*f(g) + 0.0722*f(b);
  };
  const ratio = (a, b) => {
    const [l1, l2] = [lum(a), lum(b)].sort((x, y) => y - x);
    return (l1 + 0.05) / (l2 + 0.05);
  };

  // Composite every background layer from this element upward until opaque.
  //
  // `background-image` counts. A surface painted by a gradient reports
  // `backgroundColor: transparent`, so reading only the colour walks straight
  // past it to the page ground and measures text against a background it is
  // not on — which reported two false failures the moment panels gained a
  // gradient. The gradient's own stops are sampled instead.
  const gradientStops = (image) => {
    if (!image || image === 'none') return null;
    const stops = image.match(/rgba?\([^)]*\)/g);
    if (!stops || !stops.length) return null;
    // The darkest stop, because it is the worst case for text sitting on it.
    return stops.map(parse).filter(Boolean).sort((a, b) => {
      const l = (c) => 0.2126*c[0] + 0.7152*c[1] + 0.0722*c[2];
      return l(a) - l(b);
    })[0];
  };

  const effectiveBackground = (el) => {
    const layers = [];
    for (let n = el; n; n = n.parentElement) {
      const s = getComputedStyle(n);
      const c = parse(s.backgroundColor);
      if (c && c[3] > 0) { layers.push(c); if (c[3] === 1) break; }
      const g = gradientStops(s.backgroundImage);
      if (g && g[3] > 0) { layers.push(g); if (g[3] === 1) break; }
    }
    let base = layers.length && layers[layers.length-1][3] === 1
      ? layers.pop()
      : parse(getComputedStyle(document.body).backgroundColor) || [255,255,255,1];
    while (layers.length) base = over(layers.pop(), base);
    return base;
  };

  const out = [];
  for (const el of document.querySelectorAll('body *')) {
    const own = [...el.childNodes].filter(n => n.nodeType === 3 && n.textContent.trim());
    if (!own.length) continue;
    const s = getComputedStyle(el);
    if (s.visibility === 'hidden' || s.display === 'none' || +s.opacity === 0) continue;
    const fg = parse(s.color);
    if (!fg) continue;
    const bg = effectiveBackground(el);
    const size = parseFloat(s.fontSize);
    const bold = +s.fontWeight >= 700;
    out.push({
      tag: el.tagName.toLowerCase(),
      cls: String(el.className || '').slice(0, 44),
      text: own.map(n => n.textContent.trim()).join(' ').slice(0, 28),
      color: s.color,
      background: `rgb(${bg.map(v => Math.round(v)).join(', ')})`,
      ratio: Math.round(ratio(over(fg, bg), bg) * 100) / 100,
      size, bold,
    });
  }
  return out;
}
"""


def threshold(size: float, bold: bool) -> float:
    """WCAG's large-text carve-out, and nothing more generous than it."""
    large = size >= 24 or (bold and size >= 18.66)
    return 3.0 if large else 4.5


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("url", nargs="?", default=DEFAULT_URL)
    parser.add_argument("--routes", default=",".join(ROUTES))
    args = parser.parse_args()

    from playwright.sync_api import sync_playwright

    routes = [r for r in args.routes.split(",") if r]
    failures: dict[tuple, dict] = {}
    worst: dict[str, dict] = {}
    checked = 0

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        for theme in THEMES:
            context = browser.new_context(viewport={"width": 1440, "height": 900})
            page = context.new_page()
            page.add_init_script(
                f"try {{ localStorage.setItem('theme', '{theme}'); }} catch (e) {{}}"
            )
            for route in routes:
                page.goto(args.url.rstrip("/") + route, wait_until="networkidle")
                page.evaluate(
                    f"document.documentElement.setAttribute('data-theme', '{theme}')"
                )
                page.wait_for_timeout(150)
                for row in page.evaluate(MEASURE):
                    checked += 1
                    need = threshold(row["size"], row["bold"])
                    key = (theme, row["color"], row["background"], row["size"])
                    seen = worst.get(f"{theme}|{row['color']}")
                    if seen is None or row["ratio"] < seen["ratio"]:
                        worst[f"{theme}|{row['color']}"] = {**row, "theme": theme}
                    if row["ratio"] < need and key not in failures:
                        failures[key] = {**row, "theme": theme, "need": need, "route": route}
            context.close()
        browser.close()

    print(f"{args.url} — {checked} text elements across {len(routes)} routes x {len(THEMES)} themes\n")
    print(f"{'theme':6} {'ratio':>6} {'need':>5} {'px':>5}  {'colour':<22} {'on':<22} sample")
    print("-" * 104)
    for row in sorted(worst.values(), key=lambda r: r["ratio"]):
        mark = " " if row["ratio"] >= threshold(row["size"], row["bold"]) else "FAIL"
        print(
            f"{row['theme']:6} {row['ratio']:6.2f} {threshold(row['size'], row['bold']):5.1f} "
            f"{row['size']:5.0f}  {row['color']:<22} {row['background']:<22} "
            f"{row['text'][:24]!r} {mark}"
        )

    if failures:
        print(f"\n{len(failures)} failing pairings:")
        for row in sorted(failures.values(), key=lambda r: r["ratio"]):
            print(
                f"  {row['theme']:6} {row['ratio']:.2f} < {row['need']} "
                f"{row['color']} on {row['background']} — {row['route']} "
                f"<{row['tag']} class={row['cls']!r}> {row['text']!r}"
            )
        return 1

    print("\nevery pairing meets WCAG AA in both themes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
