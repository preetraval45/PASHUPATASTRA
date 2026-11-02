// Writes the training tests' answer keys for the API to mark against (services/api/app/quizkeys.json).
// The questions are written once, in apps/web/lib/training.ts; this copies what marking needs, and
// apps/web/lib/quizkeys.test.ts fails if the two ever disagree. Run: node scripts/exportquiz.mjs
import { writeFileSync } from "node:fs";

const { MODULES, PASS_MARK } = await import("../apps/web/lib/training.ts");

const keys = {
  pass_mark: PASS_MARK,
  modules: Object.fromEntries(
    MODULES.map((m) => [m.slug, m.quiz.map((q) => ({ q: q.q, options: q.options, answer: q.options[q.answer] }))]),
  ),
};
writeFileSync(new URL("../services/api/app/quizkeys.json", import.meta.url), JSON.stringify(keys, null, 1) + "\n");
console.log(`wrote ${Object.keys(keys.modules).length} modules`);
