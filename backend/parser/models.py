from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, model_validator


class ResumeProfile(BaseModel):
    """Structured resume data extracted by AI."""
    name: Optional[str] = ""
    gender: Optional[str] = ""
    age: Optional[int] = None
    city: Optional[str] = ""
    education: List[Dict[str, Any]] = Field(default_factory=list)
    internships: List[Dict[str, Any]] = Field(default_factory=list)
    skills: List[str] = Field(default_factory=list)
    certificates: List[str] = Field(default_factory=list)
    target_industry: List[str] = Field(default_factory=list)
    target_role: List[str] = Field(default_factory=list)
    gaps: List[str] = Field(default_factory=list)
    raw_text_preview: str = ""

    @model_validator(mode="before")
    @classmethod
    def coerce_nulls(cls, data: Any) -> Any:
        if isinstance(data, dict):
            for field in ("name", "gender", "city"):
                if data.get(field) is None:
                    data[field] = ""
            for field in ("education", "internships", "skills", "certificates", "target_industry", "target_role", "gaps"):
                if data.get(field) is None:
                    data[field] = []
        return data


class ParseResponse(BaseModel):
    filename: str
    status: str  # "ok" | "error"
    profile: Optional[ResumeProfile] = None
    error: Optional[str] = None
