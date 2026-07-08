"""
Minimal OpenAI-compatible /v1/embeddings server.
Uses HuggingFace transformers + PyTorch (CPU only) — no GPU needed.
Mimics the vLLM/OpenAI API so the router.py works without changes.

Usage:
  source ~/vllm-env/bin/activate
  python scripts/embed_server.py
"""

import time
import torch
import uvicorn
from fastapi import FastAPI
from pydantic import BaseModel
from transformers import AutoTokenizer, AutoModel

# ── Config ────────────────────────────────────────────────────────────────────
MODEL_NAME = "BAAI/bge-small-en-v1.5"
PORT = 8003
HOST = "0.0.0.0"
MAX_LENGTH = 512

# ── Load model on CPU ─────────────────────────────────────────────────────────
print(f"[embed_server] Loading {MODEL_NAME} on CPU...")
tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
model = AutoModel.from_pretrained(MODEL_NAME, torch_dtype=torch.float32)
model.eval()
print(f"[embed_server] Model ready on CPU.")

# ── FastAPI app ───────────────────────────────────────────────────────────────
app = FastAPI(title="CPU Embedding Server")


class EmbedRequest(BaseModel):
    model: str = MODEL_NAME
    input: str | list[str]
    encoding_format: str = "float"


class EmbedData(BaseModel):
    object: str = "embedding"
    index: int
    embedding: list[float]


class EmbedResponse(BaseModel):
    object: str = "list"
    data: list[EmbedData]
    model: str
    usage: dict


def mean_pool(token_embeddings: torch.Tensor, attention_mask: torch.Tensor) -> torch.Tensor:
    """CLS pooling — uses first [CLS] token representation."""
    return token_embeddings[:, 0, :]


def encode(texts: list[str]) -> list[list[float]]:
    encoded = tokenizer(
        texts,
        padding=True,
        truncation=True,
        max_length=MAX_LENGTH,
        return_tensors="pt",
    )
    with torch.no_grad():
        output = model(**encoded)
    # CLS pooling then L2-normalize
    embeddings = mean_pool(output.last_hidden_state, encoded["attention_mask"])
    norms = embeddings.norm(dim=1, keepdim=True).clamp(min=1e-9)
    embeddings = embeddings / norms
    return embeddings.tolist()


@app.get("/health")
def health():
    return {"status": "ok", "model": MODEL_NAME}


@app.post("/v1/embeddings")
def embeddings(req: EmbedRequest):
    t0 = time.time()
    texts = [req.input] if isinstance(req.input, str) else req.input
    vecs = encode(texts)
    elapsed = time.time() - t0
    data = [EmbedData(index=i, embedding=v) for i, v in enumerate(vecs)]
    total_tokens = sum(len(t.split()) for t in texts)
    print(f"[embed_server] Encoded {len(texts)} text(s) in {elapsed:.3f}s")
    return EmbedResponse(
        data=data,
        model=MODEL_NAME,
        usage={"prompt_tokens": total_tokens, "total_tokens": total_tokens},
    )

# Also support /embeddings (without /v1 prefix) for compatibility
@app.post("/embeddings")
def embeddings_no_prefix(req: EmbedRequest):
    return embeddings(req)


if __name__ == "__main__":
    print(f"[embed_server] Starting on http://{HOST}:{PORT}")
    uvicorn.run(app, host=HOST, port=PORT, log_level="warning")
