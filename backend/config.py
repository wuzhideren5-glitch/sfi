from __future__ import annotations

import json
import os
from typing import List

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables and .env."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Database — Zeabur provides POSTGRES_DATABASE_URL
    database_url: str = Field(
        "postgresql+asyncpg://postgres:postgres@localhost:5432/career_ai",
        alias="DATABASE_URL",
    )

    @field_validator("database_url", mode="before")
    @classmethod
    def resolve_database_url(cls, v: str | None) -> str:
        """Accept either DATABASE_URL or Zeabur's POSTGRES_DATABASE_URL."""
        if v and v != "postgresql+asyncpg://postgres:postgres@localhost:5432/career_ai":
            return v
        # Fallback: check Zeabur's PostgreSQL service env var
        zeabur_url = os.getenv("POSTGRES_DATABASE_URL", "")
        if zeabur_url:
            # Convert postgres:// → postgresql+asyncpg://
            if zeabur_url.startswith("postgres://"):
                zeabur_url = "postgresql+asyncpg://" + zeabur_url[len("postgres://"):]
            elif zeabur_url.startswith("postgresql://"):
                zeabur_url = "postgresql+asyncpg://" + zeabur_url[len("postgresql://"):]
            return zeabur_url
        return v or ""

    # DeepSeek — 主 Agent（对话/解析）
    deepseek_api_key: str = Field("", alias="DEEPSEEK_API_KEY")
    deepseek_base_url: str = Field("https://api.deepseek.com/v1", alias="DEEPSEEK_BASE_URL")

    # 阿里云百炼 — Embedding + Rerank
    dashscope_api_key: str = Field("", alias="DASHSCOPE_API_KEY")
    dashscope_base_url: str = Field(
        "https://dashscope.aliyuncs.com/compatible-mode/v1",
        alias="DASHSCOPE_BASE_URL",
    )

    # Serper — Web search
    serper_api_key: str = Field("", alias="SERPER_API_KEY")

    # JWT
    jwt_secret: str = Field("", alias="JWT_SECRET")

    # CORS — accepts JSON list string or comma-separated
    cors_origins: List[str] = Field(
        default_factory=lambda: ["http://localhost:3000"],
        alias="CORS_ORIGINS",
    )

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, v: str | list | None) -> list[str]:
        """Parse CORS_ORIGINS from env (JSON list or comma-separated string)."""
        if v is None:
            return ["http://localhost:3000"]
        if isinstance(v, list):
            return v
        if isinstance(v, str):
            v = v.strip()
            if v.startswith("["):
                try:
                    return json.loads(v)
                except json.JSONDecodeError:
                    pass
            return [u.strip() for u in v.split(",") if u.strip()]
        return [str(v)]


settings = Settings()
