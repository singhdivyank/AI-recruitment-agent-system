"""
Inference Service
==================
Dedicated container for ML model inference.
Keeps model weights (all-MiniLM-L6-v2 + CrossEncoder) out of the backend.

Endpoints:
  POST /embed       → embed a list of texts, return vectors
  POST /rerank      → score (query, passage) pairs, return scores
  GET  /health      → liveness + model load status
  GET  /models      → which models are loaded

Models are loaded once at startup and kept warm in memory.
All endpoints are synchronous internally (sentence-transformers releases the GIL
for the heavy matrix ops, so FastAPI's threadpool handles concurrency fine).
"""
from __future__ import annotations

import time
from contextlib import asynccontextmanager
from typing import Optional

import structlog
import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sentence_transformers import CrossEncoder, SentenceTransformer

from schemas import (
    EmbedRequest, 
    EmbedResponse, 
    RerankRequest, 
    RerankResponse
)

logger = structlog.get_logger()

EMBEDDING_MODEL = "all-MiniLM-L6-v2"
RERANKER_MODEL  = "cross-encoder/ms-marco-MiniLM-L-6-v2"
CACHE_DIR       = "/models"

# Module-level model holders
_embedder: Optional[SentenceTransformer] = None
_reranker: Optional[CrossEncoder]        = None
_startup_time: float = 0.0

@asynccontextmanager
async def lifespan(app: FastAPI):
    global _embedder, _reranker, _startup_time
    t0 = time.monotonic()

    logger.info("loading_embedding_model", model=EMBEDDING_MODEL, cache=CACHE_DIR)
    _embedder = SentenceTransformer(EMBEDDING_MODEL, cache_folder=CACHE_DIR)

    logger.info("loading_reranker_model", model=RERANKER_MODEL, cache=CACHE_DIR)
    _reranker = CrossEncoder(RERANKER_MODEL, max_length=512)

    _startup_time = time.monotonic() - t0
    logger.info("models_ready", elapsed_s=round(_startup_time, 2))

    yield

    logger.info("inference_service_shutdown")

app = FastAPI(
    title="Recruitment Inference Service",
    description="Embedding + reranking inference. Separate from backend — no torch in backend container.",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["POST", "GET"],
    allow_headers=["*"],
)


@app.get("/health")
def health():
    return {
        "status": "ok",
        "models_loaded": _embedder is not None and _reranker is not None,
        "embedding_model": EMBEDDING_MODEL,
        "reranker_model": RERANKER_MODEL,
        "startup_time_s": round(_startup_time, 2),
    }


@app.get("/models")
def list_models():
    return {
        "embedding": {
            "name": EMBEDDING_MODEL,
            "dim": _embedder.get_sentence_embedding_dimension() if _embedder else None,
        },
        "reranker": {
            "name": RERANKER_MODEL,
        },
        "cache_dir": CACHE_DIR,
    }


@app.post("/embed", response_model=EmbedResponse)
def embed(req: EmbedRequest):
    """
    Embed a list of texts using all-MiniLM-L6-v2.
    Returns one 384-dim vector per input text.
    """
    if _embedder is None:
        raise HTTPException(status_code=503, detail="Embedding model not loaded yet")
    if not req.texts:
        raise HTTPException(status_code=422, detail="texts list is empty")

    t0 = time.monotonic()
    vectors = _embedder.encode(
        req.texts,
        batch_size=req.batch_size,
        show_progress_bar=False,
        convert_to_numpy=True,
        normalize_embeddings=True,   # unit norm → cosine similarity = dot product
    )
    elapsed_ms = int((time.monotonic() - t0) * 1000)

    logger.info("embed", count=len(req.texts), latency_ms=elapsed_ms)
    return EmbedResponse(
        vectors=[v.tolist() for v in vectors],
        model=EMBEDDING_MODEL,
        dim=vectors.shape[1],
        count=len(vectors),
        latency_ms=elapsed_ms,
    )


@app.post("/rerank", response_model=RerankResponse)
def rerank(req: RerankRequest):
    """
    Score (query, passage) pairs using the CrossEncoder.
    Returns one float score per pair (higher = more relevant).
    """
    if _reranker is None:
        raise HTTPException(status_code=503, detail="Reranker model not loaded yet")
    if not req.pairs:
        raise HTTPException(status_code=422, detail="pairs list is empty")

    t0 = time.monotonic()
    pairs = [[p.query, p.passage] for p in req.pairs]
    scores = _reranker.predict(pairs, show_progress_bar=False)
    elapsed_ms = int((time.monotonic() - t0) * 1000)

    logger.info("rerank", count=len(pairs), latency_ms=elapsed_ms)
    return RerankResponse(
        scores=scores.tolist(),
        model=RERANKER_MODEL,
        count=len(scores),
        latency_ms=elapsed_ms,
    )

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8080, workers=1)
