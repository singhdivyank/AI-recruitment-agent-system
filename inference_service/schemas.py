from typing import List
from pydantic import BaseModel


class EmbedRequest(BaseModel):
    texts: List[str]
    batch_size: int = 32


class EmbedResponse(BaseModel):
    vectors: List[List[float]]
    model: str
    dim: int
    count: int
    latency_ms: int


class RerankPair(BaseModel):
    query: str
    passage: str


class RerankRequest(BaseModel):
    pairs: List[RerankPair]


class RerankResponse(BaseModel):
    scores: List[float]
    model: str
    count: int
    latency_ms: int