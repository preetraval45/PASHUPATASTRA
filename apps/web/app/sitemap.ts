import type { MetadataRoute } from "next";

import { SITE } from "@/lib/site";
import { getIncidents } from "@/lib/api";

/**
 * The pages worth indexing.
 *
 * Incidents are listed from the API rather than hardcoded, so a scenario added
 * later appears without anybody remembering to add it here. Entity and evidence
 * pages are left out on purpose: there are hundreds, they exist to be reached
 * from an incident, and each is a fragment of an argument rather than a page
 * that stands on its own.
 *
 * If the API cannot be reached the static routes are still returned — a sitemap
 * missing three URLs is better than a 500 where a sitemap should be.
 */
export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  const now = new Date();
  const routes: MetadataRoute.Sitemap = [
    { url: SITE, lastModified: now, changeFrequency: "hourly", priority: 1 },
    { url: `${SITE}/incidents`, lastModified: now, changeFrequency: "hourly", priority: 0.9 },
    { url: `${SITE}/ask`, lastModified: now, changeFrequency: "hourly", priority: 0.8 },
    { url: `${SITE}/infrastructure`, lastModified: now, changeFrequency: "hourly", priority: 0.7 },
    { url: `${SITE}/actions`, lastModified: now, changeFrequency: "weekly", priority: 0.7 },
    { url: `${SITE}/audit`, lastModified: now, changeFrequency: "hourly", priority: 0.5 },
  ];

  const incidents = await getIncidents();
  for (const incident of incidents ?? []) {
    routes.push({
      url: `${SITE}/incidents/${encodeURIComponent(incident.id)}`,
      lastModified: new Date(incident.opened_at),
      changeFrequency: "hourly",
      priority: 0.8,
    });
  }
  return routes;
}
