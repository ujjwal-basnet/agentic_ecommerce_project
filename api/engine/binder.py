"""
Stage 2: Binder.

Resolves each capability to a concrete agent via the registry. Pure Python,
no LLM. Preserves parameters extracted by the planner.
"""

from __future__ import annotations

import logging

from api.agent_registry import AgentRegistry
from api.engine.schemas import CapabilityPlan, ResolvedPlan, ResolvedStep

logger = logging.getLogger(__name__)


class BindingError(Exception):
    """Raised when a capability cannot be resolved to any agent."""


def bind_plan(plan: CapabilityPlan, registry: AgentRegistry) -> ResolvedPlan:
    resolved_steps: list[ResolvedStep] = []

    for step in plan.steps:
        candidates = registry.get_by_capability(step.capability)

        if candidates:
            chosen = candidates[0]
            logger.info(
                "%s: '%s' → %s (exact)", step.step_id, step.capability, chosen.name
            )
        else:
            fuzzy = registry.search_by_capability(step.capability, k=3)
            if not fuzzy:
                raise BindingError(
                    f"No agent in registry for capability '{step.capability}' "
                    f"(step {step.step_id})"
                )
            chosen = fuzzy[0]
            logger.info(
                "%s: '%s' → %s (semantic)", step.step_id, step.capability, chosen.name
            )

        resolved_steps.append(
            ResolvedStep(
                step_id=step.step_id,
                capability=step.capability,
                description=step.description,
                agent_name=chosen.name,
                parameters=step.parameters,  # carry through from planner
            )
        )

    return ResolvedPlan(
        plan_id=plan.plan_id,
        user_request=plan.user_request,
        steps=resolved_steps,
    )
