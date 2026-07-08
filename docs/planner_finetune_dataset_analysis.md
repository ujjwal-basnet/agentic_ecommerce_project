# SmartShop Planner and Fine-Tuning Dataset Analysis

This note summarizes the current planner architecture and the dataset generated
for Qwen3-8B planner fine-tuning.

## Current Planner Flow

The application is planner-first. A user message is sanitized, given recent chat
context, passed to the planner, bound to registered capabilities, executed by
specialist agents, validated, and then converted into the final response.

Important files:

- `api/engine/planner_v2.py`: LLM planner prompt and guided JSON output.
- `api/engine/schemas.py`: fixed `CapabilityPlan` and `Capability` schema.
- `api/engine/__init__.py`: runtime orchestration, deterministic guards,
  product constraint validation and response assembly.
- `api/agents/__init__.py`: specialist agent registry.
- `api/routes/facebook.py`, `api/routes/instagram.py`, `api/mcp_server.py`:
  reply-message-only channels that still use the same engine.

The planner is good enough for the current architecture because it now has a
fixed capability schema, guided JSON output and strict rules for product
queries. The main weakness is that an 8B model can still confuse product
queries with policy questions unless it has seen many examples of that routing
boundary.

## Deterministic Parts Found

These deterministic parts should stay even after fine-tuning:

- Product constraint validation in `api/engine/__init__.py`: color, category,
  price and stock checks prevent wrong product cards such as returning a red
  dumbbell for "red shirt".
- Budget filtering: numeric price comparison is safer in code than in an LLM.
- Cart, checkout and order execution: these mutate state and must remain
  database-backed.
- Final response/card assembly: product cards, prices and stock should come
  from runtime data, not model memory.
- Fixed capability schema in `api/engine/schemas.py`: this prevents fake tools.

These deterministic parts can be reduced later if the fine-tuned model is
strong:

- The fuzzy add-to-cart shortcut. Fine-tuning can teach the planner to emit
  `add_to_cart` directly for most explicit add requests, but the shortcut is
  still useful as a fallback.
- Some greeting/acknowledgement fast paths. They are cheap latency optimizations
  and are not harmful.
- The unused LLM classifier/rewriter path can be removed later if it remains
  disconnected from the engine.

## Dataset Design

The generated dataset trains only the planner output:

- User input now matches `api.engine.planner_v2.create_plan()` exactly: optional `Context:` block plus `User request:` line. Channel rendering is handled after tool execution, so channel metadata is not included in the fine-tuning prompt.
- Assistant output is one `CapabilityPlan` JSON object.
- The dataset does not train the model to write product cards or final product
  descriptions. It trains exact product IDs because the current `resolve_products` schema expects IDs; if the catalog changes, regenerate the dataset and eval cases or migrate the planner schema to query/filters.


Generated files:

- `data/finetune_dataset.jsonl`: main training file used by
  `scripts/finetune_qwen3_8b_a100.py`
- `data/finetune_train.jsonl`: explicit train split
- `data/finetune_validation.jsonl`: validation prompts
- `data/finetune_test.jsonl`: held-out prompts
- `data/finetune_manifest.json`: counts and notes

Coverage includes:

- Product browsing and recommendation using `resolve_products`
- Product-vs-policy traps such as "anything for my wife" vs delivery questions
- AND-filter cases such as red shirt, blue shirt, white charger and no-match
  constraints
- Typos and romanized Nepali phrases
- Cart add/remove/view/clear/checkout actions
- Context references such as "red one", "how much is this" and "add second one"
- Virtual try-on success and rejection cases
- Policy queries through `search_knowledge_base`
- Small talk and off-topic redirects

## Training Recommendation

The current dataset has 1,167 examples. With this size, more GPU time does not
mean better quality. Train with validation and stop based on held-out routing
accuracy, not just low loss. For QLoRA on Qwen3-8B, 3 to 6 epochs is usually a
reasonable range for this dataset. If there are 42 hours available, spend the
extra time on evaluation and adding real failed prompts from logs rather than
running many more epochs on the same examples.
