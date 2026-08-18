"""The benchmark arms.

Four are specified. Two can honestly be run today.

`runbook` and `pashupatastra` are real and complete: both receive the identical
proposal from the identical shared proposer, so the only thing that differs
between them is what the architecture does with a proposal once it has one.
That is the claim Phase 5 is testing, and holding the proposal constant is what
isolates it.

`naive-llm` is implemented as a code path and **refuses to run without a
configured model**. Driving it with the deterministic stub would produce a
second runbook wearing a different label, and reporting that as "naive LLM
agent" would be fabricating the comparison the paper depends on.

`human` is not code. It needs operators running the scenarios, and the only
honest thing to build here is somewhere to record their results.
"""

from __future__ import annotations

import time
from enum import StrEnum

from pashupatastra.arms import Brief, Decision, unhealthy
from pashupatastra.dharma import Environment, RiskContext, Tier, evaluate
from pashupatastra.registry import get as get_action

from .stack import BASELINE_READY, REPLICAS, EphemeralStack, kubectl


class ArmUnavailable(RuntimeError):
    """An arm that cannot run honestly under the current configuration."""


class Ablation(StrEnum):
    """One component removed from the full architecture.

    An ablation is only meaningful if the arm actually uses the component. Three
    of the five the roadmap names live in the reasoning path — hypotheses,
    memory, correlation — and this arm does not exercise any of them: the shared
    proposer stands in for diagnosis precisely because there is no model to do
    it. Removing a stage that never ran would produce an identical score and be
    reported as "no effect", which is the most misleading result available here.
    """

    NONE = "none"
    NO_POLICY = "no-policy"
    NO_VERIFICATION = "no-verification"
    NO_EVIDENCE = "no-evidence"
    NO_MEMORY = "no-memory"
    NO_ADJACENCY = "no-adjacency"


UNMEASURABLE: dict[Ablation, str] = {
    Ablation.NO_EVIDENCE: (
        "the hypothesis evidence requirement sits in the reasoning layer, which "
        "this arm never invokes — the shared proposer replaces diagnosis. "
        "Removing it would change nothing and report as 'no effect'"
    ),
    Ablation.NO_MEMORY: (
        "Smriti retrieval is not part of this arm's decision path; each scenario "
        "runs in a fresh namespace with no prior incidents to recall"
    ),
    Ablation.NO_ADJACENCY: (
        "topology-adjacency correlation runs before an incident is formed, and "
        "the harness hands the arm one already-scoped fault"
    ),
}


def propose(brief: Brief) -> str | None:
    """The shared proposal, identical for every arm.

    Deliberately shallow — it reacts to unhealthy state and picks the first
    permitted action. It is not a diagnosis and is not meant to be: measuring
    diagnosis needs a real model, and scoring the stub would measure a fixture
    this repository wrote. What varies between arms is what happens next.
    """
    if not unhealthy(brief):
        return None
    return brief.allowed_actions[0] if brief.allowed_actions else "restart_service"


class RunbookArm:
    """Threshold-triggered automation. Fires when a number crosses a line.

    No policy evaluation, no verification, and no concept of handing off — a
    runbook that could decide not to run would be an agent. This is the baseline
    the architecture has to beat, and on the cases where doing nothing is
    correct it is expected to do badly.
    """

    name = "runbook"

    def decide(self, brief: Brief) -> Decision:
        action = propose(brief)
        if action is None:
            return Decision(rationale="no threshold crossed")
        return Decision(action=action, rationale="threshold crossed; ran the runbook")


class NaiveLLMArm:
    """Model with tool access, no policy layer, no verification.

    Refuses to run against the deterministic stub. A naive agent whose
    "reasoning" is a fixture is a runbook with extra steps, and the difference
    this arm exists to measure would be manufactured rather than observed.
    """

    name = "naive-llm"

    def __init__(self, model_configured: bool = False) -> None:
        self.model_configured = model_configured

    def decide(self, brief: Brief) -> Decision:
        if not self.model_configured:
            raise ArmUnavailable(
                "naive-llm needs a configured model. Running it against the echo "
                "stub would report a fixture as an LLM baseline, which is the one "
                "result in this benchmark that would be pure fabrication."
            )
        raise ArmUnavailable(
            "naive-llm model path is not wired yet — see T-5.3. The gate above is "
            "deliberate: this arm should stay unavailable rather than approximate."
        )


class PashupatastraArm:
    """The full architecture: propose, then let Dharma decide, then verify.

    Given the same proposal as the runbook arm, the differences are exactly the
    three things the architecture adds — it declines to act when nothing is
    wrong, it routes every action through a policy verdict, and it checks the
    result instead of assuming it.
    """

    name = "pashupatastra"

    def __init__(
        self,
        stack: EphemeralStack | None = None,
        ablation: Ablation = Ablation.NONE,
    ) -> None:
        if reason := UNMEASURABLE.get(ablation):
            raise ArmUnavailable(f"ablation {ablation.value!r} is not measurable here — {reason}")
        self.stack = stack
        self.ablation = ablation

    def decide(self, brief: Brief) -> Decision:
        action_id = propose(brief)
        if action_id is None:
            # Nothing observably wrong. Silence is an answer, and it is the one
            # the runbook arm structurally cannot give.
            return Decision(rationale="no fault observed; took no action")

        try:
            spec = get_action(action_id)
        except KeyError:
            return Decision(
                escalated=True,
                cause="unrecognised_situation",
                rationale=f"{action_id} is not a registered action",
            )

        # Blast radius is the number of services actually affected. Passing the
        # count of *healthy* replicas here scored every action at 100 and denied
        # the entire corpus — the architecture looked maximally cautious when it
        # was being fed a nonsense input.
        ready = brief.observed.get("ready_replicas", float(BASELINE_READY))
        affected = max(1, int((BASELINE_READY - ready) // REPLICAS))

        verdict = evaluate(
            spec,
            RiskContext(
                environment=Environment.PROD,
                blast_radius_entities=affected,
                # Left at their defaults on purpose. An ephemeral namespace makes
                # every run look novel and every diagnosis look uncertain, but
                # both are artefacts of how the harness provisions rather than
                # facts about the scenario, and penalising them would measure the
                # rig.
                dry_run=False,
            ),
            incident_ref=brief.scenario_id,
        )

        # The scenario's risk_ceiling is read as the authority granted for this
        # incident, so an action inside it counts as approved. Demanding tier
        # AUTONOMOUS instead would make the arm escalate every remediation in the
        # corpus — rollback_deployment alone is base risk 45 — which measures the
        # absence of a human in the loop rather than the architecture.
        # The policy ablation removes exactly this gate and nothing else.
        if self.ablation is not Ablation.NO_POLICY and (
            verdict.tier is Tier.DENIED or verdict.effective_risk > brief.risk_ceiling
        ):
            return Decision(
                escalated=True,
                cause="policy_ceiling",
                rationale=(
                    f"Dharma scored {action_id} at {verdict.effective_risk} against a "
                    f"ceiling of {brief.risk_ceiling} → handing off"
                ),
            )

        # Act, then check. Verification ran before the action in the first cut
        # of this arm, which meant it was grading a stack that still had the
        # fault in it and escalating every remediation it had just authorised.
        self._execute(action_id)
        if self.ablation is Ablation.NO_VERIFICATION:
            # Reports the action as done without checking, which is what a system
            # with no verification stage genuinely does.
            return Decision(action=action_id, rationale=f"authorised at {verdict.tier}; unverified")

        if not self._verified():
            return Decision(
                escalated=True,
                cause="verification_failed",
                rationale=f"{action_id} did not reach its expected post-state; escalating",
            )

        return Decision(
            action=action_id,
            rationale=f"authorised at {verdict.tier} and verified",
        )

    def _execute(self, action_id: str) -> None:
        """Apply the action to whichever services are actually degraded."""
        if self.stack is None:
            return
        ns = self.stack.namespace
        for service in self.stack.unhealthy_services():
            target = f"deployment/{service}"
            try:
                if action_id in ("rollback_deployment", "redeploy_version"):
                    kubectl("rollout", "undo", target, "-n", ns, context=self.stack.context)
                elif action_id == "restart_service":
                    kubectl("rollout", "restart", target, "-n", ns, context=self.stack.context)
                elif action_id == "scale_service":
                    kubectl("scale", target, "--replicas=2", "-n", ns, context=self.stack.context)
                elif action_id == "disable_deployment":
                    kubectl("rollout", "pause", target, "-n", ns, context=self.stack.context)
            except Exception:  # noqa: BLE001
                # A failed execution is a failed remediation, not a crash. It
                # surfaces through verification below rather than as an error.
                return

    def _verified(self, settle: float = 12.0) -> bool:
        """Whether the stack actually recovered.

        With no stack attached the honest answer is that nothing was observed,
        and unobserved never counts as success — the same rule the production
        loop follows.
        """
        if self.stack is None:
            return False
        time.sleep(settle)
        return self.stack.observe().get("availability", 0.0) >= 100.0


class HumanArm:
    """Not implementable. Recorded, not run.

    An operator with dashboards is a person, and a simulated human would be this
    repository writing the number it wants the baseline to be. Results come from
    `benchmark/results/human/` once real runs exist.
    """

    name = "human"

    def decide(self, brief: Brief) -> Decision:
        raise ArmUnavailable(
            "the human arm requires operators running the scenarios. Record real "
            "runs under benchmark/results/human/; a simulated human is not a baseline."
        )


RUNNABLE = {"runbook": RunbookArm, "pashupatastra": PashupatastraArm}
GATED = {"naive-llm": NaiveLLMArm, "human": HumanArm}
