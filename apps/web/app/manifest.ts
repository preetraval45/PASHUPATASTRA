import type { MetadataRoute } from "next";

/**
 * The web app manifest, as a route rather than a static file so the icon list
 * cannot drift from what `scripts/buildbrand.py` actually writes.
 *
 * `theme_color` matches `--ground` in the dark palette, which is the theme this
 * console defaults to — an installed icon that opens onto a white flash before
 * the page paints looks broken for that moment.
 */
export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "Pashupatastra",
    short_name: "Pashupatastra",
    description:
      "Security incident response: observe, reason, act under policy, verify.",
    start_url: "/",
    display: "standalone",
    background_color: "#0b0d11",
    theme_color: "#0b0d11",
    icons: [
      { src: "/favicon-48x48.png", sizes: "48x48", type: "image/png" },
      { src: "/favicon-96x96.png", sizes: "96x96", type: "image/png" },
      { src: "/icon.png", sizes: "512x512", type: "image/png", purpose: "any" },
      { src: "/apple-icon.png", sizes: "180x180", type: "image/png" },
    ],
  };
}
