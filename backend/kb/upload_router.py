"""Vector upload API — 文档上传→解析→向量化→存入知识库."""
from __future__ import annotations

import json
import time
from pathlib import Path

from fastapi import APIRouter, UploadFile, File, HTTPException
from pydantic import BaseModel

from core.llm import chat
from core.embedding import embed_single

router = APIRouter(prefix="/api/kb", tags=["kb"])

KB_PATH = Path(__file__).parent.parent / "kb_data" / "alumni_records.json"
VECTOR_STORE_PATH = Path(__file__).parent.parent / "kb_data" / "kb_vectors.json"

EXTRACT_PROMPT = """你是求职数据处理助手。从港中深校友访谈文档中提取结构化信息。
返回严格的JSON格式，不要markdown包裹，不要注释。

JSON结构：
{
  "name": "姓名",
  "program": "硕士项目",
  "graduation_year": 毕业年份(数字),
  "undergrad": "本科学校 专业",
  "gpa": GPA(数字,没有则null),
  "internships": [{"company": "公司名", "role": "岗位", "duration": "时长"}],
  "certificates": ["证书1", "证书2"],
  "job_search": {
    "applications_count": "投递数量",
    "interviews_count": 面试次数,
    "offers": [{"company": "公司", "role": "岗位", "location": "城市", "salary": "薪资"}],
    "final_choice": "最终选择"
  },
  "career_path": [{"company": "公司", "role": "岗位", "period": "时间段"}],
  "insights": ["经验教训1", "经验教训2", "经验教训3"],
  "tags": ["标签1", "标签2"]
}

规则：
1. 从文档中尽可能提取信息，没有的字段填null或空数组
2. 姓名从文档开头或标题中提取
3. insights提取"建议""感悟""经验"相关内容
4. tags覆盖行业、公司类型、求职方式等关键词"""


class IngestResult(BaseModel):
    status: str
    name: str | None = None
    program: str | None = None
    embedding_dim: int | None = None
    kb_total: int = 0
    error: str | None = None


def _extract_text(file: UploadFile) -> str:
    """Extract text from uploaded file (PDF, DOCX, TXT)."""
    filename = (file.filename or "").lower()
    content = file.file.read()

    if filename.endswith(".txt") or filename.endswith(".md"):
        return content.decode("utf-8", errors="replace")

    if filename.endswith(".docx"):
        import io
        from docx import Document
        doc = Document(io.BytesIO(content))
        return "\n".join(p.text for p in doc.paragraphs if p.text.strip())

    if filename.endswith(".pdf"):
        import io
        import fitz  # PyMuPDF
        doc = fitz.open(stream=content, filetype="pdf")
        text = "\n".join(page.get_text() for page in doc)
        doc.close()
        return text

    raise HTTPException(400, f"不支持的文件格式: {filename}，仅支持 PDF/DOCX/TXT/MD")


@router.post("/ingest", response_model=IngestResult)
async def ingest_document(file: UploadFile = File(...)):
    """Upload a document → extract → vectorize → store in KB."""
    try:
        text = _extract_text(file)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(400, f"文件读取失败: {e}")

    if len(text) < 100:
        raise HTTPException(400, f"文档内容太短 ({len(text)} 字符)，无法解析")

    # Parse with LLM
    text_for_llm = text[:8000]
    try:
        result = chat(
            messages=[
                {"role": "system", "content": EXTRACT_PROMPT},
                {"role": "user", "content": f"请从以下文档中提取结构化信息：\n\n{text_for_llm}"},
            ],
            model="deepseek-chat",
            temperature=0.1,
            max_tokens=2000,
        )
        result = result.strip()
        if result.startswith("```"):
            result = result.split("\n", 1)[-1].rsplit("```", 1)[0]
        record = json.loads(result)
    except json.JSONDecodeError:
        raise HTTPException(500, "AI 解析返回格式错误，请重试")
    except Exception as e:
        raise HTTPException(500, f"AI 解析失败: {e}")

    # Generate embedding
    text_for_embed = json.dumps(record, ensure_ascii=False)[:4000]
    try:
        embedding = embed_single(text_for_embed)
    except Exception as e:
        raise HTTPException(500, f"向量化失败: {e}")

    # Append to KB
    KB_PATH.parent.mkdir(exist_ok=True)
    existing = []
    if KB_PATH.exists():
        existing = json.loads(KB_PATH.read_text(encoding="utf-8"))
    existing.append(record)
    KB_PATH.write_text(json.dumps(existing, ensure_ascii=False, indent=2), encoding="utf-8")

    # Append to vector store
    vectors = []
    if VECTOR_STORE_PATH.exists():
        vectors = json.loads(VECTOR_STORE_PATH.read_text(encoding="utf-8"))
    vectors.append({
        "name": record.get("name"),
        "embedding": embedding,
        "record": record,
        "ingested_at": time.time(),
    })
    VECTOR_STORE_PATH.write_text(json.dumps(vectors, ensure_ascii=False, indent=2), encoding="utf-8")

    return IngestResult(
        status="ok",
        name=record.get("name"),
        program=record.get("program"),
        embedding_dim=len(embedding),
        kb_total=len(existing),
    )


@router.get("/stats")
async def kb_stats():
    """Get KB statistics."""
    records = []
    if KB_PATH.exists():
        records = json.loads(KB_PATH.read_text(encoding="utf-8"))
    return {
        "total_records": len(records),
        "names": [r.get("name") for r in records],
        "programs": list(set(r.get("program", "") for r in records if r.get("program"))),
        "all_tags": sorted(set(t for r in records for t in r.get("tags", []))),
    }
