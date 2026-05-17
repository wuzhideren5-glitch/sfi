"""Web search — Serper.dev Google Search API (fast, reliable)."""
from __future__ import annotations

import requests

from config import settings


def web_search(query: str, max_results: int = 3) -> str:
    """Search the web via Serper API and return formatted results."""
    api_key = settings.serper_api_key
    if not api_key:
        return ""

    try:
        resp = requests.post(
            "https://google.serper.dev/search",
            headers={"X-API-KEY": api_key, "Content-Type": "application/json"},
            json={"q": query, "num": max_results},
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()

        results = []
        for item in data.get("organic", [])[:max_results]:
            title = item.get("title", "")
            snippet = item.get("snippet", "")[:300]
            link = item.get("link", "")
            results.append(f"- **{title}**\n  {snippet}\n  {link}")

        # Also include knowledge graph if available
        kg = data.get("knowledgeGraph", {})
        if kg:
            kg_title = kg.get("title", "")
            kg_desc = kg.get("description", "")[:200]
            if kg_desc:
                results.insert(0, f"📌 {kg_title}: {kg_desc}")

        return "\n\n".join(results) if results else ""

    except Exception:
        return ""
