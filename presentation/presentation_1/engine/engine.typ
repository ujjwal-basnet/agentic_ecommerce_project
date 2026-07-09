#import "../../template.typ": title-slide, slide-layout, divider-slide

#title-slide(
  title: "SmartShop API Core Architecture",
  subtitle: "Part 1: The AI Agentic Engine Layer",
  author: "researchcontentlab@gmail.com",
  project: "project-ba58c036-070e-438e-b8b"
)

#pagebreak()

#show: slide-layout.with(title: "Overview of /api/engine", section: "Engine Introduction")

- The *`api/engine/`* folder is the heart of the SmartShop system.
- It translates conversational inputs into structured plans and executes them.
- *Key constraint verified*: No unused agent wrappers are declared here.
- It dynamically binds capabilities directly to Python implementations in `api/agents`.

#grid(
  columns: (1fr, 1fr),
  gutter: 1.5em,
  [
    *Core Pipeline Files:*
    - `router.py` (HTTP Entrypoint)
    - `planner_v2.py` (LLM Reasoning)
    - `binder.py` (Agent Mapping)
    - `executor_v2.py` (DAG Worker)
  ],
  [
    *Output / Helper Files:*
    - `response.py` (GenUI Formatting)
    - `schemas.py` (Pydantic models)
    - `__init__.py` (Validation helpers)
  ]
)

#pagebreak()

#show: slide-layout.with(title: "High-Level Architecture", section: "System Architecture")

#align(center)[
  #image("../../../typst_proposal/images/architecture_diagram.png", width: 75%)
]

#pagebreak()

#show: slide-layout.with(title: "1. The Entrypoint: router.py", section: "Router Component")

- Coordinates the flow of conversation.
- Fetches session history, processes incoming HTTP text payloads.
- Calls the LLM Planner and hands the resulting plan to the Executor.

*Code Signature:*
```python
@router.post("/chat")
async def chat_endpoint(request: ChatRequest):
    session = await get_session(request.session_id)
    plan = await planner.generate_plan(request.message, session.history)
    result = await executor.execute(plan)
    return format_response(result)
```

#pagebreak()

#show: slide-layout.with(title: "2. The Brain: planner_v2.py", section: "Planner Component")

- Implemented using *`pydantic-ai`*.
- Evaluates raw queries against registered *capabilities* (defined in `schemas.py`).
- Returns a structured `CapabilityPlan` containing dependency links.

*Prompt Optimization:*
- Uses detailed system prompts containing catalog rules and category synonyms.
- Fallbacks to static database keyword queries if the LLM engine fails.

#pagebreak()

#show: slide-layout.with(title: "3. The Glue: binder.py", section: "Binder Component")

- Inspects the planner's `CapabilityPlan`.
- Maps capability names (e.g. `search_products`, `view_cart`) to agent classes.
- *Agent Integration*: Imports and instantiates implementations from the `api/agents` folder.

*Binding Logic:*
```python
def bind_capability(name: str) -> BaseAgent:
    registry = {
        "search_products": ProductSearchAgent,
        "recommend_items": RecommendationAgent,
        "tryon_clothing": TryOnAgent,
        "manage_cart": CartAgent,
    }
    return registry[name]()
```

#pagebreak()

#show: slide-layout.with(title: "4. The Muscle: executor_v2.py", section: "Executor Component")

- Treats the plan as a *Directed Acyclic Graph (DAG)* of actions.
- Resolves independent tasks and runs them concurrently using an asynchronous worker pool (`asyncio.gather`).
- Maximizes performance and cuts response latencies down to less than 1.5 seconds.

```python
async def execute(plan: CapabilityPlan):
    # Sort nodes topologically
    ordered_nodes = topological_sort(plan.nodes)
    for batch in ordered_nodes.batches():
        await asyncio.gather(*[node.run() for node in batch])
```

#pagebreak()

#show: slide-layout.with(title: "5. Response Formatting & Validation", section: "Response Component")

- *`response.py`* processes agent outputs.
- Translates structured JSON lists into fluid markdown messages.
- Inject HTML-based *GenUI / Server-Side Rendered (SSE)* cards:
  - `ProductCard` (image, description, interactive buy buttons)
  - `TryOnModal` (Virtual Fitting visual overlays)
  - `CartSummary` (active item counters)
