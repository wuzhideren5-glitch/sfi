"""Resume API routes."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, UploadFile
from fastapi.responses import Response

from .models import ResumeEditRequest
from .service import ResumeService

router = APIRouter(prefix="/resume", tags=["resume"])
service = ResumeService()


@router.get("/")
async def get_resume():
    """Get current resume as markdown."""
    resume = service.get_resume_text()
    return {"resume": resume, "has_resume": service.has_resume()}


@router.post("/build")
async def build_resume():
    """Build resume from parsed profile data (stored in MD archive)."""
    from core.profile_store import ProfileStore
    from core.session_store import TEST_USER_ID

    store = ProfileStore(user_id=TEST_USER_ID)
    fm = store.get_frontmatter()
    if not fm.get("name"):
        raise HTTPException(status_code=400, detail="请先上传简历")

    content = service.build_from_profile(fm)
    return {"resume": content, "message": "简历已从档案生成"}


@router.post("/edit")
async def edit_resume(req: ResumeEditRequest):
    """Edit a specific section of the resume using AI."""
    result = await service.edit_section(
        section=req.section,
        instruction=req.instruction,
        item_index=req.item_index,
    )
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error", "编辑失败"))
    return result


@router.get("/export/{format}")
async def export_resume(format: str):
    """Export resume as DOCX or PDF."""
    if not service.has_resume():
        raise HTTPException(status_code=400, detail="简历为空，请先上传简历或从档案生成")

    if format == "docx":
        content = service.export_docx()
        return Response(
            content=content,
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            headers={"Content-Disposition": "attachment; filename=resume.docx"},
        )
    elif format == "pdf":
        content = service.export_pdf()
        return Response(
            content=content,
            media_type="application/pdf",
            headers={"Content-Disposition": "attachment; filename=resume.pdf"},
        )
    else:
        raise HTTPException(status_code=400, detail=f"不支持的格式: {format}。可选: docx, pdf")
