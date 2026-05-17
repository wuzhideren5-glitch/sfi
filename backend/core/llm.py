"""DeepSeek client — main agent for conversation and document parsing."""
from __future__ import annotations

from openai import OpenAI

from config import settings

_client: OpenAI | None = None


def get_client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI(
            api_key=settings.deepseek_api_key,
            base_url=settings.deepseek_base_url,
        )
    return _client


def chat(messages: list[dict], model: str = "deepseek-chat", **kwargs) -> str:
    """Send a chat completion request and return the text response."""
    client = get_client()
    response = client.chat.completions.create(
        model=model,
        messages=messages,
        **kwargs,
    )
    return response.choices[0].message.content or ""


def chat_stream(messages: list[dict], model: str = "deepseek-chat", **kwargs):
    """Stream a chat completion, yielding text chunks."""
    client = get_client()
    stream = client.chat.completions.create(
        model=model,
        messages=messages,
        stream=True,
        **kwargs,
    )
    for chunk in stream:
        if chunk.choices[0].delta.content:
            yield chunk.choices[0].delta.content
