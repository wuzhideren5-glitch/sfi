"""Resume data models."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class ResumeSection(BaseModel):
    """A single section of the resume (education, experience, etc.)."""
    title: str = ""
    items: List[Dict[str, Any]] = Field(default_factory=list)


class ResumeData(BaseModel):
    """Full structured resume."""
    name: str = ""
    contact: Dict[str, str] = Field(default_factory=dict)  # phone, email, city
    education: List[Dict[str, Any]] = Field(default_factory=list)
    internships: List[Dict[str, Any]] = Field(default_factory=list)
    projects: List[Dict[str, Any]] = Field(default_factory=list)
    skills: List[str] = Field(default_factory=list)
    certificates: List[str] = Field(default_factory=list)
    languages: List[str] = Field(default_factory=list)
    summary: str = ""  # personal summary / objective


class ResumeEditRequest(BaseModel):
    """Request to edit a specific section of the resume."""
    section: str = ""  # education, internships, projects, skills, summary
    instruction: str = ""  # natural language instruction: "把这段经历改得更量化"
    item_index: int | None = None  # which item to edit (for list sections)


class ResumeEditResponse(BaseModel):
    """Response after AI-driven resume edit."""
    success: bool = True
    section: str = ""
    before: str = ""
    after: str = ""
    changes: str = ""  # description of what changed


class ResumeExportRequest(BaseModel):
    """Request to export resume."""
    format: str = "docx"  # "docx" or "pdf"
