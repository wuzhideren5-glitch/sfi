"""Resume parser — PDF text extraction + DeepSeek structuring."""
from __future__ import annotations

import json
import logging

import fitz  # PyMuPDF

from core.llm import chat as deepseek_chat
from core.profile_state import set_profile
from core.profile_store import ProfileStore
from core.session_store import TEST_USER_ID
from .models import ParseResponse, ResumeProfile

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """你是简历解析助手。从简历文本中提取结构化信息，返回严格JSON。

JSON结构：
{
  "name": "姓名",
  "gender": "性别（男/女）",
  "age": 年龄数字或null,
  "city": "当前城市",
  "education": [{"school": "学校", "degree": "学位", "major": "专业", "year": "年份"}],
  "internships": [{"company": "公司", "role": "岗位", "duration": "时间段", "description": "简述"}],
  "skills": ["技能1", "技能2"],
  "certificates": ["证书1"],
  "target_industry": ["目标行业"],
  "target_role": ["目标岗位"],
  "gaps": ["待提升的短板，如缺实习/缺证书/缺项目等"]
}

规则：
- 没有的字段填null或空数组
- 从简历内容中如实提取，不要编造
- 返回纯JSON，不要markdown包裹"""


async def parse_resume(file_bytes: bytes, filename: str) -> ParseResponse:
    """Parse a resume PDF and return structured profile."""

    # 1. Extract text from PDF
    try:
        doc = fitz.open(stream=file_bytes, filetype="pdf")
        text_parts = []
        for page in doc:
            text_parts.append(page.get_text())
        full_text = "\n".join(text_parts)
        doc.close()

        # Detect garbled text: check printable ratio + CJK presence
        if full_text.strip():
            printable = sum(1 for c in full_text if c.isprintable() or c in '\n\r\t')
            ratio = printable / len(full_text) if full_text else 0
            # Count CJK characters
            cjk = sum(1 for c in full_text if '\u4e00' <= c <= '\u9fff' or '\u3400' <= c <= '\u4dbf')
            cjk_ratio = cjk / len(full_text) if full_text else 0
            if ratio < 0.7 or (cjk_ratio < 0.05 and len(full_text) > 100):
                return ParseResponse(
                    filename=filename,
                    status="error",
                    error="PDF文本提取失败：文档可能为扫描件或字体不兼容。请用Word/LaTeX导出文字版PDF后重试。",
                )

        if len(full_text.strip()) < 50:
            return ParseResponse(
                filename=filename,
                status="error",
                error="简历文本太少（不足50字符），请确认PDF内容可读取。若非扫描件，建议用Word导出PDF后重试。",
            )
    except Exception as e:
        return ParseResponse(
            filename=filename,
            status="error",
            error=f"PDF解析失败: {e}",
        )

    # 2. Send to DeepSeek for structuring (truncate to ~6000 chars)
    text_for_ai = full_text[:6000]

    try:
        result = deepseek_chat(
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": f"请从以下简历中提取结构化信息：\n\n{text_for_ai}"},
            ],
            model="deepseek-chat",
            temperature=0.1,
            max_tokens=1500,
        )

        # Clean markdown wrapping
        result = result.strip()
        if result.startswith("```"):
            result = result.split("\n", 1)[-1].rsplit("```", 1)[0]

        profile_data = json.loads(result)
        profile = ResumeProfile(**profile_data)
        profile.raw_text_preview = full_text[:200]

        # Store in shared state for chat agent to use
        set_profile(profile.model_dump())

        # Also write to MD profile archive (long-term memory)
        try:
            store = ProfileStore(user_id=TEST_USER_ID)
            store.update_frontmatter(profile.model_dump())
            from resume.service import ResumeService
            ResumeService().build_from_profile(profile.model_dump())
        except Exception as e:
            logger.warning("Failed to write MD profile: %s", e)

        return ParseResponse(filename=filename, status="ok", profile=profile)

    except json.JSONDecodeError as e:
        logger.error("JSON parse failed: %s, raw: %s", e, result[:200])
        return ParseResponse(
            filename=filename,
            status="error",
            error="AI解析结果格式异常，请重试",
        )
    except Exception as e:
        logger.error("Parse error: %s", e)
        return ParseResponse(
            filename=filename,
            status="error",
            error=f"解析失败: {str(e)}",
        )
