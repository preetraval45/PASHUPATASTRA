import assert from "node:assert/strict";
import { test } from "node:test";

import { defendFollowUp, idUrl } from "./answerlinks.ts";

test("each identifier links to its official page", () => {
  assert.equal(idUrl("T1003.001"), "https://attack.mitre.org/techniques/T1003/001/");
  assert.equal(idUrl("T1486"), "https://attack.mitre.org/techniques/T1486/");
  assert.equal(idUrl("M1053"), "https://attack.mitre.org/mitigations/M1053/");
  assert.equal(idUrl("CAPEC-600"), "https://capec.mitre.org/data/definitions/600.html");
  assert.equal(idUrl("CVE-2021-44228"), "https://nvd.nist.gov/vuln/detail/CVE-2021-44228");
});

test("a technique answer offers to ask how to defend against it", () => {
  const answer = "The ATT&CK techniques this most resembles, most likely first:\n\n1. Scheduled Task (T1053.005)\n2. Scheduled Task/Job (T1053)";
  assert.equal(defendFollowUp(answer), "How do we defend against Scheduled Task (T1053.005)?");
});

test("an answer that already lists defences offers no defence follow-up", () => {
  const answer = "For Data Encrypted for Impact (T1486), which this matches, ATT&CK lists these defences, most relevant first:\n\n- Data Backup (M1053)";
  assert.equal(defendFollowUp(answer), null);
});
