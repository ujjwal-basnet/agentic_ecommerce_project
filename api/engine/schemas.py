"""
Pipeline data models for the 4-stage engine.

CapabilityPlan (Stage 1 — Planner output):
    Steps reference CAPABILITIES, not agents. The planner also extracts
    parameters in the same call (merged Stage 1 + Stage 3 for latency).

BoundPlan (Stage 2 — Binder output):
    Same plan, each step resolved to a concrete agent_name.

ResolvedPlan (what Stage 4 consumes):
    BoundPlan + parameters ready for execution.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, model_validator

# The capabilities the planner may emit. Making this a Literal lets guided
# decoding (xgrammar) FORCE the model to pick a real one — a small local model
# can't invent "fetch_product_details" or over-decompose into fake sub-steps.
#
# NOTE: `search_products` (vector/embedding search) is deliberately excluded.
# The catalog is small and lives in the planner prompt, so the planner should
# pick IDs and call `resolve_products` (a direct DB fetch, no embedding backend
# needed). A small model otherwise over-picks search_products and gets empty
# results when no embedding endpoint is served.
Capability = Literal[
    "resolve_products",
    "add_to_cart",
    "remove_from_cart",
    "view_cart",
    "clear_cart",
    "checkout_cart",
    "perform_virtual_try_on",
    "recommend_products",
    "search_knowledge_base",
]


# ============ Stage 1 output ============


class CapabilityStep(BaseModel):
    """A single step in capability/domain terms, with parameters pre-extracted."""

    step_id: str = Field(
        default="s1",
        description="Unique within plan, e.g. 's1', 's2'",
    )
    capability: Capability = Field(
        description="Which tool to invoke. MUST be one of the allowed values.",
    )
    description: str = Field(
        default="Executing planner step",
        description="Human-readable explanation of this step",
    )
    parameters: dict[str, Any] = Field(
        default_factory=dict,
        description=(
            "Parameters extracted from the user request. Keys depend on capability:\n"
            "- resolve_products: product_ids (list[int])\n"
            "- search_products: query (str), color (str), category (str), max_price (float), min_price (float), limit (int)\n"
            "- add_to_cart: product_id (int), product_name (str), quantity (int)\n"
            "- remove_from_cart: product_id (int), product_name (str)\n"
            "- view_cart / clear_cart / checkout_cart: no params needed\n"
            "- perform_virtual_try_on: product_id (int)\n"
            "- recommend_products: context (str), limit (int)\n"
            "- search_knowledge_base: query (str)\n"
        ),
    )

    @model_validator(mode="before")
    @classmethod
    def _heal_params(cls, data: Any) -> Any:
        if isinstance(data, dict):
            # Heal params -> parameters
            if "params" in data and "parameters" not in data:
                data["parameters"] = data.pop("params")

            valid_caps = {
                "resolve_products", "add_to_cart", "remove_from_cart",
                "view_cart", "clear_cart", "checkout_cart",
                "perform_virtual_try_on", "recommend_products",
                "search_knowledge_base"
            }

            # Heal capability from step_type field (model sometimes uses this)
            if "capability" not in data and "step_type" in data:
                step_type = data["step_type"]
                if step_type in valid_caps:
                    data["capability"] = step_type

            # Heal capability from step_id if still missing
            if "capability" not in data and "step_id" in data:
                step_id = data["step_id"]
                if step_id.startswith("step_"):
                    step_id = step_id[5:]
                if step_id in valid_caps:
                    data["capability"] = step_id

        return data


class CapabilityPlan(BaseModel):
    """Stage 1 output. Pure reasoning — no agents named."""

    plan_id: UUID = Field(default_factory=uuid4)
    user_request: str = ""
    created_at: datetime = Field(default_factory=datetime.utcnow)
    steps: list[CapabilityStep] = Field(default_factory=list)
    overall_strategy: str = ""
    direct_response: str | None = Field(
        default=None,
        description=(
            "For greetings, smalltalk, or questions the planner can answer "
            "directly without tool calls. When set, pipeline short-circuits."
        ),
    )

    @model_validator(mode="before")
    @classmethod
    def _heal_flat_step(cls, data: Any) -> Any:
        if isinstance(data, dict):
            # If the model emitted a flat step directly at the top level
            if "capability" in data and "steps" not in data:
                step = {
                    "step_id": data.get("step_id") or "s1",
                    "capability": data["capability"],
                    "description": data.get("description") or "Auto-recovered step from flat LLM output",
                    "parameters": data.get("parameters") or {},
                }
                # If they placed parameters at the top level instead (e.g. product_ids, query)
                # extract them into parameters if it's empty
                if not step["parameters"]:
                    params = {}
                    for k, v in data.items():
                        if k not in ("step_id", "capability", "description", "parameters", "plan_id", "user_request", "created_at", "overall_strategy", "direct_response"):
                            params[k] = v
                    step["parameters"] = params

                data = {
                    "steps": [step],
                    "overall_strategy": data.get("overall_strategy") or "",
                    "direct_response": data.get("direct_response"),
                    "plan_id": data.get("plan_id"),
                    "user_request": data.get("user_request") or "",
                }
        return data

    @model_validator(mode="after")
    def _validate_plan(self) -> "CapabilityPlan":
        # Drop steps the LLM emitted with no capability — this happens when
        # a model spuriously appends an empty step at the end of the list.
        self.steps = [s for s in self.steps if s.capability.strip()]

        # Auto-assign unique step_ids instead of raising on collisions. Small
        # models routinely omit step_id, so every step defaults to 's1' and a
        # hard error here would waste a whole generation. Renumbering is safe:
        # nothing references step_id across steps in this pipeline.
        for i, step in enumerate(self.steps, start=1):
            step.step_id = f"s{i}"
        return self


# ============ Stage 2 (Executor consumes this) ============


class StepStatus(str, Enum):
    READY = "ready"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"
    SKIPPED = "skipped"


class ResolvedStep(BaseModel):
    step_id: str
    capability: str
    agent_name: str
    description: str
    parameters: dict[str, Any] = Field(default_factory=dict)

    status: StepStatus = StepStatus.READY
    attempts: int = 0
    result: Any | None = None
    error: str | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None


class ResolvedPlan(BaseModel):
    plan_id: UUID
    user_request: str
    steps: list[ResolvedStep]
    final_summary: str | None = None

    def is_complete(self) -> bool:
        return all(
            s.status in (StepStatus.DONE, StepStatus.FAILED, StepStatus.SKIPPED)
            for s in self.steps
        )

    def get(self, step_id: str) -> ResolvedStep:
        for s in self.steps:
            if s.step_id == step_id:
                return s
        raise KeyError(step_id)
