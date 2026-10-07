"""Scoring a diagnosis against the answer key the corpus already carries.

The benchmark could run all four arms and still not say whether Sati is *right*,
because nothing scored the one thing the paper is about. `arms.py` says so in as
many words — "measuring diagnosis needs a real model, and scoring the stub would
measure a fixture" — and that was true of the stub and not a reason for the
instrument to be missing. This is the instrument. It grades; it does not
diagnose.

**Grading is deterministic, and deliberately so.** The obvious alternative is a
model judging another model's answer, and this repository's first engineering
rule forbids exactly that: the language model is never the source of truth. So
diagnosis is posed as a closed-set choice — the corpus authored 60 scenarios
whose root causes are 60 *distinct* labels, one correct per scenario — and
grading is an identity comparison on a string. A model can be wrong here in a
way nobody can argue about.

Three properties that make the resulting number quotable:

* **The random baseline is stated, not implied.** One label in sixty is 1.7%.
  An accuracy figure that does not carry its baseline is unreadable, and a
  60-way choice is a much stronger claim than a 4-way one.
* **Chain credit is reported separately and never blended in.** Naming the right
  root cause and reconstructing the right causal order are different abilities.
  One number averaging them would hide which of the two failed.
* **The label set leaks, and that is recorded.** The labels are descriptive
  English — `connection_leak_from_config_regression` nearly states its own
  answer — so part of this task is reading comprehension over the options.
  `LEAKAGE` below is written to be quoted in the limitations section rather than
  discovered by a reviewer.

Nothing here imports a cloud, a model, or a cluster: it is arithmetic over
strings, so it runs on a laptop and in a unit test.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field

from .pib import PibScenario

#: Quoted in the paper's limitations rather than left to be found.
LEAKAGE = (
    "The options are descriptive English labels authored with the scenarios, so "
    "a correct choice can come partly from reading the option text rather than "
    "from reasoning about the telemetry. The closed set makes grading "
    "unarguable and makes the task easier than open-ended diagnosis; both are "
    "true and neither is adjustable after the fact."
)

#: Why a scenario cannot be graded for diagnosis. Stated per reason, because
#: "excluded by design" and "we could not manage it" are different facts.
UNSCOREABLE: dict[str, str] = {
    "no_root_cause": (
        "the scenario authors no root cause, because its correct outcome is to "
        "do nothing or to escalate — there is no fault to name"
    ),
}


def scoreable(corpus: list[PibScenario]) -> list[PibScenario]:
    """The scenarios a diagnosis can be graded on at all.

    A scenario whose correct outcome is to do nothing has no root cause to name,
    and counting it as a miss would punish an arm for being right.
    """
    return [s for s in corpus if s.expected.root_cause]


def labels(corpus: list[PibScenario]) -> list[str]:
    """Every root cause in the corpus, sorted — the full option set."""
    return sorted({s.expected.root_cause for s in corpus if s.expected.root_cause})


def choices(
    scenario: PibScenario,
    corpus: list[PibScenario],
    count: int = 0,
    seed: int = 0,
) -> list[str]:
    """The options to offer for one scenario, in a fixed order.

    `count` of 0 offers every label in the corpus — the headline condition, one
    in sixty. A smaller `count` offers the correct label plus distractors drawn
    **from the same category first**, which discriminates better: eight
    plausible neighbours are a harder choice than eight labels about unrelated
    subsystems, where elimination does the work instead of reasoning.

    Seeded from the scenario id as well as `seed`, so the option set for a
    scenario is identical on every run and every machine. An option set that
    moved between runs would make repeated runs incomparable, which is the one
    thing a benchmark asked for three repetitions cannot afford.
    """
    correct = scenario.expected.root_cause
    if correct is None:
        raise ValueError(f"{scenario.id} authors no root cause; it is not scoreable")

    everything = labels(corpus)
    if count <= 0 or count >= len(everything):
        return everything

    rng = random.Random(f"{seed}:{scenario.id}")
    kin = [
        s.expected.root_cause
        for s in corpus
        if s.category == scenario.category
        and s.expected.root_cause
        and s.expected.root_cause != correct
    ]
    others = [label for label in everything if label != correct and label not in kin]
    rng.shuffle(kin)
    rng.shuffle(others)

    picked = (kin + others)[: count - 1]
    return sorted([correct, *picked])


def chain_credit(answer: tuple[str, ...], expected: tuple[str, ...]) -> float:
    """How much of the expected causal order the answer reproduces, 0 to 1.

    The longest common subsequence against the expected chain, so naming the
    right steps in the wrong order scores below naming them in order, and extra
    steps neither help nor are punished twice. Reported beside top-1 accuracy
    and never folded into it.
    """
    if not expected:
        return 0.0
    rows = [[0] * (len(expected) + 1) for _ in range(len(answer) + 1)]
    for i, a in enumerate(answer, start=1):
        for j, e in enumerate(expected, start=1):
            rows[i][j] = rows[i - 1][j - 1] + 1 if a == e else max(rows[i - 1][j], rows[i][j - 1])
    return rows[len(answer)][len(expected)] / len(expected)


def wilson(hits: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """A 95% confidence interval for a proportion, Wilson's form.

    At the sizes this corpus allows — sixty scoreable scenarios, three runs — an
    accuracy quoted without an interval is not a result. Wilson rather than the
    normal approximation because it stays inside 0 to 1 near the ends, which is
    exactly where a first model run is likely to land.
    """
    if n == 0:
        return (0.0, 0.0)
    p = hits / n
    denominator = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denominator
    spread = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denominator
    return (max(0.0, centre - spread), min(1.0, centre + spread))


@dataclass
class Graded:
    """One answer, graded."""

    scenario: str
    answer: str | None
    correct: str = ""
    hit: bool = False
    offered: int = 0
    chain: float = 0.0
    #: An answer outside the options offered. Not a miss — a protocol failure,
    #: counted apart so a malformed-output problem cannot be read as a
    #: reasoning problem.
    off_menu: bool = False


def grade(
    scenario: PibScenario,
    answer: str | None,
    offered: list[str],
    chain: tuple[str, ...] = (),
) -> Graded:
    """Grade one answer. Identity on a string, and nothing cleverer.

    No fuzzy matching, no stemming, no "close enough". A grader that decided
    `connection_leak` was near enough to `connection_leak_from_config_regression`
    would be making the judgement call the model was asked to make.
    """
    correct = scenario.expected.root_cause or ""
    normalised = answer.strip() if isinstance(answer, str) else None
    return Graded(
        scenario=scenario.id,
        answer=normalised,
        correct=correct,
        hit=normalised == correct,
        offered=len(offered),
        chain=chain_credit(chain, scenario.expected.causal_chain),
        off_menu=normalised is not None and normalised not in offered,
    )


@dataclass
class Accuracy:
    """What a set of graded answers adds up to."""

    n: int = 0
    hits: int = 0
    off_menu: int = 0
    unanswered: int = 0
    options: int = 0
    chain: float = 0.0
    by_category: dict[str, tuple[int, int]] = field(default_factory=dict)

    @property
    def top1(self) -> float | None:
        """Accuracy, or `None` when nothing was scored — never 0.0.

        The rule `/impact` is built on: a figure that could not be measured is
        absent, because zero is itself a measurement and the two read
        identically on a page.
        """
        return self.hits / self.n if self.n else None

    @property
    def baseline(self) -> float | None:
        """What guessing would score, given the options actually offered."""
        return 1 / self.options if self.options else None

    @property
    def interval(self) -> tuple[float, float] | None:
        return wilson(self.hits, self.n) if self.n else None

    @property
    def above_chance(self) -> bool | None:
        """Whether the interval's floor clears the random baseline.

        The only honest headline for a first run: an accuracy that does not
        clear its own baseline is not evidence of reasoning, however much
        better than zero it looks.
        """
        if self.interval is None or self.baseline is None:
            return None
        return self.interval[0] > self.baseline


def summarise(graded: list[Graded], corpus: list[PibScenario]) -> Accuracy:
    """Roll graded answers up, keeping the categories apart.

    Per-category counts are kept because the corpus is balanced thirteen ways
    across eight categories, and an overall figure can hide an arm that is
    strong on deployment faults and blind on security ones — which, given
    `inject.py` cannot inject a security fault at all, is the specific confound
    a reader should be able to check.
    """
    category = {s.id: s.category for s in corpus}
    accuracy = Accuracy(
        n=len(graded),
        hits=sum(1 for g in graded if g.hit),
        off_menu=sum(1 for g in graded if g.off_menu),
        unanswered=sum(1 for g in graded if g.answer is None),
        options=max((g.offered for g in graded), default=0),
        chain=(sum(g.chain for g in graded) / len(graded)) if graded else 0.0,
    )
    for g in graded:
        name = category.get(g.scenario, "unknown")
        hits, total = accuracy.by_category.get(name, (0, 0))
        accuracy.by_category[name] = (hits + (1 if g.hit else 0), total + 1)
    return accuracy
