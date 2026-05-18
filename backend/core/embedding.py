"""Alibaba Bailian (DashScope) — embedding and reranking."""
from __future__ import annotations

from openai import OpenAI

from config import settings

_client: OpenAI | None = None


def get_client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI(
            api_key=settings.dashscope_api_key,
            base_url=settings.dashscope_base_url,
        )
    return _client


def embed(texts: list[str], model: str = "text-embedding-v4") -> list[list[float]]:
    """Generate embeddings for a list of texts."""
    client = get_client()
    response = client.embeddings.create(model=model, input=texts)
    return [d.embedding for d in response.data]


def embed_single(text: str, model: str = "text-embedding-v4") -> list[float]:
    """Generate a single embedding."""
    return embed([text], model=model)[0]


def rerank(
    query: str,
    documents: list[str],
    model: str = "qwen3-rerank",
    top_n: int = 5,
) -> list[dict]:
    """Rerank documents by relevance to query.

    Returns list of {index, relevance_score, document} sorted by score descending.
    """
    get_client()  # ensure initialized

    # Bailian rerank uses a different endpoint structure
    import httpx

    resp = httpx.post(
        f"{settings.dashscope_base_url.rstrip('/compatible-mode/v1')}/compatible-api/v1/reranks",
        headers={"Authorization": f"Bearer {settings.dashscope_api_key}"},
        json={
            "model": model,
            "query": query,
            "documents": documents,
            "top_n": top_n,
        },
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    return data.get("results", [])
