/**
 * Where this deployment lives.
 *
 * Absolute URLs in a sitemap and in Open Graph tags are not optional — a
 * relative `og:image` is simply not fetched, and a sitemap of relative paths is
 * rejected. Defined once so the canonical host cannot disagree between them.
 */
export const SITE =
  process.env.NEXT_PUBLIC_SITE_URL ?? "https://pashupatastra.vercel.app";
