# Tool-Call Fine-Tuning Dataset

This dataset is for the current SmartShop `CapabilityPlan` planner. It teaches tool choice and argument extraction, not product memorization.

## Web Research Summary

- OpenAI model optimization: supervised fine-tuning means giving examples of correct responses, useful for specific formats and instruction-following fixes: https://developers.openai.com/api/docs/guides/model-optimization
- OpenAI function calling: strict schema adherence is recommended for reliable tool calls: https://developers.openai.com/api/docs/guides/function-calling
- OpenAI structured outputs: use clear schema keys/descriptions and evals to improve schema quality: https://developers.openai.com/api/docs/guides/structured-outputs
- Recent tool-calling research separates structural validity from semantic tool choice, so this dataset covers both: valid JSON and hard product-vs-policy routing examples.

## Dataset Design

Each JSONL line is ChatML:

```json
{"messages":[{"role":"system","content":"..."},{"role":"user","content":"..."},{"role":"assistant","content":"{...CapabilityPlan JSON...}"}]}
```

The user message includes:

- `Channel: web | mcp | facebook | instagram`
- `Surface: ...`
- `Renderer: product_card_and_answer | reply_message_only`
- optional `Context:` for recent conversation or uploaded photo
- `User request: ...`

Important: the planner does not emit `reply_message` or product-card UI tools because the current backend does not support those as planner capabilities. The renderer decides the final output:

- web: `resolve_products` becomes product cards plus text
- MCP/Facebook/Instagram: the same tool result becomes text only through `engine.run_text`

## What This Teaches

- product queries -> `resolve_products(product_ids=[...])`
- policy queries -> `search_knowledge_base(query=...)`
- social/MCP channels still use tools when needed, but their final renderer is reply-only
- hard negative examples prevent `anything for my wife` from becoming delivery policy
- no-match product requests become `direct_response`
- cart, checkout, and virtual try-on use exact capability names

## Do Not Mix Schemas

If you later add real capabilities like `reply_message`, `web_search`, or `show_product_cards`, add them to `api/engine/schemas.py` first and generate a new dataset version. Training the current planner on capabilities it cannot execute will make Pydantic reject the model output.

## Regenerate

```bash
python3 scripts/generate_finetune_data.py
```

Then train with the existing fine-tune script:

```bash
python3 scripts/finetune.py --dataset data/finetune_dataset.jsonl
```
