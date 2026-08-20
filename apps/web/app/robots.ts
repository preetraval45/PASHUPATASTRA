import type { MetadataRoute } from "next";

import { SITE } from "@/lib/site";

/**
 * What a crawler may read.
 *
 * `/search` is excluded: it produces a distinct URL for every query anyone has
 * ever typed, none of which is a page worth indexing, and letting a crawler
 * walk them buries the pages that are.
 */
export default function robots(): MetadataRoute.Robots {
  return {
    rules: { userAgent: "*", allow: "/", disallow: "/search" },
    sitemap: `${SITE}/sitemap.xml`,
  };
}
