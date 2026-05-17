from __future__ import annotations

from typing import List

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables and .env."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Database
    database_url: str = Field(
        "postgresql+asyncpg://postgres:postgres@localhost:5432/career_ai",
        alias="DATABASE_URL",
    )

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

    # CORS
    cors_origins: List[str] = Field(
        default_factory=lambda: ["http://localhost:3000"],
        alias="CORS_ORIGINS",
    )


settings = Settings()
