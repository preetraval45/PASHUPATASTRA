"""Experiment: Dharma over the whole PIB corpus, with no cluster.

For each of the 104 scenarios, score through the real policy engine:
  the expected action (remediation scenarios),
  every forbidden action,
  every allowed action.
Under three contexts, so the result is not one arbitrary setting:
  prod with confidence 0.9, prod with confidence 0.6, staging with 0.9.
Blast radius is one entity throughout, the most favourable case for acting.

This measures the policy, not the system: it says what Dharma would let run
alone if a proposer offered each action, nothing about whether anything would
propose it.
"""

import json
import sys
from collections import Counter

from pashupatastra.dharma import Environment, RiskContext, evaluate
from pashupatastra.pib import load_corpus
from pashupatastra.registry import get

corpus = load_corpus(sys.argv[1])
CONTEXTS = {
    "prod c0.9": RiskContext(environment=Environment.PROD, diagnostic_confidence=0.9, blast_radius_entities=1),
    "prod c0.6": RiskContext(environment=Environment.PROD, diagnostic_confidence=0.6, blast_radius_entities=1),
    "staging c0.9": RiskContext(environment=Environment.STAGING, diagnostic_confidence=0.9, blast_radius_entities=1),
}
out = {"scenarios": len(corpus), "outcomes": Counter(str(s.outcome) for s in corpus), "contexts": {}}
for name, ctx in CONTEXTS.items():
    forb, expd, allowed, ceiling_breach = Counter(), Counter(), Counter(), 0
    for s in corpus:
        for a in s.constraints.forbidden_actions:
            forb[str(evaluate(get(a), ctx).tier)] += 1
        for a in s.constraints.allowed_actions:
            v = evaluate(get(a), ctx)
            allowed[str(v.tier)] += 1
        if s.expected.action:
            v = evaluate(get(s.expected.action), ctx)
            expd[str(v.tier)] += 1
            if v.effective_risk > s.constraints.risk_ceiling:
                ceiling_breach += 1
    out["contexts"][name] = {"forbidden": forb, "expected": expd, "allowed": allowed, "expected_over_scenario_ceiling": ceiling_breach}
print(json.dumps(out, indent=1, default=dict))
json.dump(out, open(sys.argv[2], "w"), indent=1, default=dict)
