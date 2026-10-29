import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";

/**
 * Vercel rejects a vercel.json with a key its schema does not know, before any
 * build runs. A "//" comment key added on 27 Oct 2026 failed every deployment
 * for a day while every local check passed. JSON has no comments: the reasons
 * for this file's settings are in docs/DEPLOYMENT.md.
 */

const KNOWN = new Set([
  "$schema", "buildCommand", "cleanUrls", "crons", "devCommand", "framework", "functions", "git", "headers",
  "ignoreCommand", "images", "installCommand", "outputDirectory", "public", "redirects", "regions", "rewrites",
  "trailingSlash",
]);

test("vercel.json uses only keys Vercel's schema accepts", () => {
  const config = JSON.parse(readFileSync(new URL("../vercel.json", import.meta.url), "utf8")) as Record<string, unknown>;
  const unknown = Object.keys(config).filter((k) => !KNOWN.has(k));
  assert.deepEqual(unknown, [], `keys Vercel would reject: ${unknown.join(", ")}`);
});
