"""Knowledge base ingestion: parse alumni docs → JSON → embed → store.

Usage: python ingest_kb.py
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent))

from docx import Document
from core.llm import chat
from core.embedding import embed_single

DOC_DIR = Path("/Users/penghui/Documents/求职AI系统开发/学长学姐的求职分享")
OUTPUT_DIR = Path(__file__).parent / "kb_data"
OUTPUT_DIR.mkdir(exist_ok=True)

SYSTEM_PROMPT = """你是求职数据处理助手。从港中深校友访谈Word文档中提取结构化信息。
返回严格的JSON格式，不要markdown包裹，不要注释。

JSON结构：
{
  "name": "姓名",
  "program": "硕士项目（如：会计理学硕士/金融学硕士/商业分析硕士）",
  "graduation_year": 毕业年份(数字),
  "undergrad": "本科学校 专业",
  "gpa": GPA(数字,没有则null),
  "internships": [{"company": "公司名", "role": "岗位", "duration": "时长"}],
  "certificates": ["证书1", "证书2"],
  "job_search": {
    "applications_count": "投递数量(如'50+',没有则null)",
    "interviews_count": 面试次数(数字,没有则null),
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


def parse_docx(path: Path) -> dict | None:
    """Parse a single docx into structured alumni record."""
    print(f"  📄 解析: {path.name[:50]}...")

    doc = Document(str(path))
    full_text = "\n".join(p.text for p in doc.paragraphs if p.text.strip())

    if len(full_text) < 100:
        print(f"    ⚠ 文档内容太短，跳过")
        return None

    # Truncate to avoid token limits (~8000 chars)
    text = full_text[:8000]

    try:
        result = chat(
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": f"请从以下校友访谈中提取结构化信息：\n\n{text}"},
            ],
            model="deepseek-chat",
            temperature=0.1,
            max_tokens=2000,
        )

        # Clean up response
        result = result.strip()
        if result.startswith("```"):
            result = result.split("\n", 1)[-1].rsplit("```", 1)[0]

        record = json.loads(result)
        record["source_doc"] = path.name
        print(f"    ✅ {record.get('name', '?')} | {record.get('program', '?')}")
        return record

    except json.JSONDecodeError as e:
        print(f"    ❌ JSON 解析失败: {e}")
        print(f"    Raw: {result[:200]}...")
        return None
    except Exception as e:
        print(f"    ❌ 错误: {e}")
        return None


def main():
    docx_files = sorted(DOC_DIR.glob("*.docx"))
    print(f"🔍 找到 {len(docx_files)} 篇文档\n")

    records = []
    for f in docx_files:
        record = parse_docx(f)
        if record:
            # Generate embedding
            try:
                text_for_embed = json.dumps(record, ensure_ascii=False)[:4000]
                emb = embed_single(text_for_embed)
                record["_embedding_dim"] = len(emb)
                print(f"    🧬 embedding: {len(emb)}维")
            except Exception as e:
                print(f"    ⚠ embedding 失败: {e}")
                record["_embedding_error"] = str(e)

            records.append(record)

    # Save to JSON
    output_path = OUTPUT_DIR / "alumni_records.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2)

    print(f"\n{'='*50}")
    print(f"✅ 完成！{len(records)}/{len(docx_files)} 篇解析成功")
    print(f"📁 输出: {output_path}")

    # Summary
    for r in records:
        print(f"  - {r.get('name', '?')} | {r.get('program', '?')} | tags: {r.get('tags', [])}")


if __name__ == "__main__":
    main()
