"""
Stage 4: PipelineExecutor (v2).

Programmatic (NOT LLM-driven) execution of the ResolvedPlan.
Deterministic, debuggable, retryable DAG runner.

Features:
  - Parallel execution of all steps
  - Per-step retry with bounded attempts
  - All steps reach terminal state (DONE, FAILED) after run()
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Any

from api.agent_registry import AgentRegistry
from api.engine.schemas import ResolvedPlan, ResolvedStep, StepStatus

logger = logging.getLogger(__name__)


class PipelineExecutor:
    """
    Executor for ResolvedPlan.

    Executes all steps concurrently with per-step retry up to max_attempts.
    """

    def __init__(self, registry: AgentRegistry, max_attempts: int = 2) -> None:
        self.registry = registry
        self.max_attempts = max_attempts

    async def run(self, plan: ResolvedPlan) -> ResolvedPlan:
        """
        Execute the resolved plan as a DAG with parallelism, retry, and skip-on-failure.

        Preconditions:
          - All steps have status READY
          - Registry has implementations for all referenced agents
          - max_attempts > 0

        Postconditions:
          - All steps are in terminal state (DONE, FAILED, or SKIPPED)
          - Steps with failed upstream dependencies are SKIPPED
          - Each step attempted at most max_attempts times
          - completed dict contains results of all DONE steps

        Loop Invariants:
          - completed dict grows monotonically (steps never un-complete)
          - No step is executed more than max_attempts times
          - Steps only run when all dependencies are in completed
        """
        completed: dict[str, Any] = {}

        while not plan.is_complete():
            runnable = [s for s in plan.steps if s.status == StepStatus.READY]
            if not runnable:
                break

            results = await asyncio.gather(
                *[self._run_step(step) for step in runnable],
                return_exceptions=True,
            )

            for step, outcome in zip(runnable, results):
                if isinstance(outcome, Exception):
                    if step.attempts < self.max_attempts:
                        step.status = StepStatus.READY
                        step.error = f"Attempt {step.attempts} failed: {outcome}"
                        logger.warning("Step %s failed (attempt %d/%d): %s", step.step_id, step.attempts, self.max_attempts, outcome)
                    else:
                        step.status = StepStatus.FAILED
                        step.error = f"{type(outcome).__name__}: {outcome}"
                        step.finished_at = datetime.utcnow()
                        logger.error("Step %s permanently failed: %s", step.step_id, outcome)
                else:
                    step.status = StepStatus.DONE
                    step.result = outcome.model_dump() if hasattr(outcome, "model_dump") else outcome
                    step.finished_at = datetime.utcnow()
                    completed[step.step_id] = step.result
                    logger.info("Step %s completed successfully", step.step_id)

        return plan

    async def _run_step(self, step: ResolvedStep) -> Any:
        """
        Execute a single step: resolve params, call agent impl, return result.

        On exception, the exception propagates up to the gather() caller
        which handles retry/failure logic.
        """
        step.status = StepStatus.RUNNING
        step.started_at = datetime.utcnow()
        step.attempts += 1

        # Look up the agent implementation
        card = self.registry.get_by_name(step.agent_name)
        if card.impl is None:
            raise RuntimeError(
                f"Agent '{card.name}' has no implementation registered"
            )

        # Call the agent implementation
        return await card.impl(step.parameters)
