"""
MD Profile Store — 学生个人档案（Markdown + YAML frontmatter）。

替代旧的 JSON personal_kb + 内存 profile_state。
每个用户一个 .md 文件，结构化数据用 frontmatter，自由文本用 markdown 小节。

特性：
- 跨会话持久化（文件系统）
- YAML frontmatter: 基本信息、教育、实习、技能、目标
- Markdown 小节: 对话洞察、简历原文、AI 修改记录
- 自动创建、增量更新、版本记录
"""
from __future__ import annotations

import os
import re
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

PROFILES_DIR = Path(__file__).parent.parent / "profiles"
PROFILES_DIR.mkdir(exist_ok=True)

# Frontmatter section names
SECTION_INSIGHTS = "## 对话洞察"
SECTION_RESUME = "## 简历"
SECTION_CHANGELOG = "## 更新记录"


class ProfileStore:
    """管理单个用户的 MD 档案文件。"""

    def __init__(self, user_id: str):
        self.user_id = user_id
        self.file_path = PROFILES_DIR / f"{user_id}.md"
        self._ensure_exists()

    # ═══════════════════════════════════════════════════════════
    # File I/O
    # ═══════════════════════════════════════════════════════════

    def _ensure_exists(self):
        """Create profile file with template if missing."""
        if self.file_path.exists():
            return
        template = f"""---
name: ""
gender: ""
age: null
city: ""
education: []
internships: []
skills: []
certificates: []
target_industry: []
target_role: []
gaps: []
update_count: 0
created_at: "{time.strftime('%Y-%m-%d %H:%M:%S')}"
---

# {self.user_id} 的个人档案

{SECTION_INSIGHTS}
<!-- 此处由 AI 自动记录对话中的关键洞察，每 2-3 轮更新 -->

{SECTION_RESUME}
<!-- 简历结构化内容 -->

{SECTION_CHANGELOG}
<!-- 每次更新的时间戳和摘要 -->
"""
        self.file_path.write_text(template, encoding="utf-8")

    def read(self) -> tuple[dict, str]:
        """Read profile. Returns (frontmatter_dict, markdown_body)."""
        raw = self.file_path.read_text(encoding="utf-8")
        fm = {}
        body = raw
        # Parse YAML frontmatter
        m = re.match(r'^---\s*\n(.*?)\n---\s*\n', raw, re.DOTALL)
        if m:
            try:
                fm = yaml.safe_load(m.group(1)) or {}
            except yaml.YAMLError:
                pass
            body = raw[m.end():]
        return fm, body

    def write(self, frontmatter: dict, body: str):
        """Write full profile, merging frontmatter."""
        existing_fm, _ = self.read()
        merged_fm = {**existing_fm, **frontmatter}
        yaml_block = yaml.dump(merged_fm, allow_unicode=True, default_flow_style=False)
        content = f"---\n{yaml_block}---\n\n{body}"
        self.file_path.write_text(content, encoding="utf-8")

    # ═══════════════════════════════════════════════════════════
    # High-level API
    # ═══════════════════════════════════════════════════════════

    def get_frontmatter(self) -> dict:
        """Get structured profile data."""
        fm, _ = self.read()
        return fm

    def update_frontmatter(self, updates: dict):
        """Merge updates into frontmatter."""
        fm, body = self.read()
        fm.update(updates)
        self.write(fm, body)

    def get_full_text(self) -> str:
        """Return full MD content as a string (for injection into prompts)."""
        return self.file_path.read_text(encoding="utf-8")

    def get_summary_for_prompt(self, max_chars: int = 1500) -> str:
        """Return a compact summary suitable for system prompt injection."""
        fm, body = self.read()
        lines = []

        # Basic info
        name = fm.get("name", "") or "未设置"
        gender = fm.get("gender", "")
        age = fm.get("age", "")
        city = fm.get("city", "")
        header = f"👤 {name}"
        extras = []
        if gender:
            extras.append(gender)
        if age:
            extras.append(f"{age}岁")
        if city:
            extras.append(city)
        if extras:
            header += f"（{' · '.join(extras)}）"
        lines.append(header)

        # Education
        edu = fm.get("education", [])
        if edu:
            edu_strs = []
            for e in edu:
                parts = [e.get("school", ""), e.get("major", ""), e.get("degree", "")]
                edu_strs.append(" ".join(p for p in parts if p))
            lines.append(f"🎓 {'；'.join(edu_strs)}")

        # Internships
        internships = fm.get("internships", [])
        if internships:
            intern_strs = []
            for i in internships:
                parts = [i.get("company", ""), i.get("role", ""), i.get("duration", "")]
                intern_strs.append(" ".join(p for p in parts if p))
            lines.append(f"💼 {'；'.join(intern_strs)}")

        # Skills
        skills = fm.get("skills", [])
        if skills:
            lines.append(f"🛠 {'、'.join(skills)}")

        # Certificates
        certs = fm.get("certificates", [])
        if certs:
            lines.append(f"📜 {'、'.join(certs)}")

        # Targets
        targets = fm.get("target_industry", [])
        roles = fm.get("target_role", [])
        if targets or roles:
            lines.append(f"🎯 行业：{'、'.join(targets)} | 岗位：{'、'.join(roles)}")

        # Gaps
        gaps = fm.get("gaps", [])
        if gaps:
            lines.append(f"📈 待提升：{'、'.join(gaps)}")

        # Insights section (truncated)
        insights_text = self._extract_section(body, SECTION_INSIGHTS)
        if insights_text and "<!--" not in insights_text[:5]:
            lines.append(f"\n📝 对话洞察摘要：")
            lines.append(insights_text[:500])

        result = "\n".join(lines)
        if len(result) > max_chars:
            result = result[:max_chars] + "\n…（已截断）"
        return result

    _PROFILE_SECTIONS = {SECTION_INSIGHTS, SECTION_RESUME, SECTION_CHANGELOG}

    def _extract_section(self, body: str, heading: str) -> str:
        """Extract content under a heading until next profile section heading or EOF."""
        # Get all profile section headings (excluding current one)
        stop_set = self._PROFILE_SECTIONS - {heading}
        if not stop_set:
            return ""

        # Build alternation pattern for stop headings
        stops = '|'.join(re.escape(h) for h in stop_set)
        pattern = re.escape(heading) + r'\s*\n(.*?)(?=\n(?:' + stops + r')|\Z)'
        m = re.search(pattern, body, re.DOTALL)
        return m.group(1).strip() if m else ""

    # ═══════════════════════════════════════════════════════════
    # Insight management (for auto-update agent)
    # ═══════════════════════════════════════════════════════════

    def get_insights(self) -> str:
        """Get current conversation insights text."""
        _, body = self.read()
        text = self._extract_section(body, SECTION_INSIGHTS)
        # Filter out HTML comments
        text = re.sub(r'<!--.*?-->', '', text, flags=re.DOTALL).strip()
        return text

    def update_insights(self, new_insights: str):
        """Replace the conversation insights section."""
        fm, body = self.read()
        # Use same stop-heading logic as _extract_section
        stop_set = self._PROFILE_SECTIONS - {SECTION_INSIGHTS}
        stops = '|'.join(re.escape(h) for h in stop_set)
        pattern = re.escape(SECTION_INSIGHTS) + r'\s*\n(.*?)(?=\n(?:' + stops + r')|\Z)'
        replacement = SECTION_INSIGHTS + "\n" + new_insights.strip()
        if re.search(SECTION_INSIGHTS, body):
            body = re.sub(pattern, replacement, body, count=1, flags=re.DOTALL)
        else:
            body += f"\n\n{replacement}"

        fm["update_count"] = fm.get("update_count", 0) + 1
        self.write(fm, body)
        self._add_changelog("更新对话洞察")

    # ═══════════════════════════════════════════════════════════
    # Resume management
    # ═══════════════════════════════════════════════════════════

    def get_resume_section(self) -> str:
        """Get the resume markdown section."""
        _, body = self.read()
        return self._extract_section(body, SECTION_RESUME)

    def set_resume_section(self, content: str):
        """Set/replace the resume section."""
        fm, body = self.read()
        # Use same stop-heading logic as _extract_section
        stop_set = self._PROFILE_SECTIONS - {SECTION_RESUME}
        stops = '|'.join(re.escape(h) for h in stop_set)
        pattern = re.escape(SECTION_RESUME) + r'\s*\n(.*?)(?=\n(?:' + stops + r')|\Z)'
        replacement = SECTION_RESUME + "\n" + content.strip()
        if re.search(SECTION_RESUME, body):
            body = re.sub(pattern, replacement, body, count=1, flags=re.DOTALL)
        else:
            body += f"\n\n{replacement}"
        self.write(fm, body)

    def _add_changelog(self, summary: str):
        """Append a changelog entry."""
        _, body = self.read()
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        entry = f"- [{timestamp}] {summary}"
        if SECTION_CHANGELOG in body:
            # Insert after changelog heading
            idx = body.index(SECTION_CHANGELOG) + len(SECTION_CHANGELOG)
            body = body[:idx] + "\n" + entry + body[idx:]
        else:
            body += f"\n\n{SECTION_CHANGELOG}\n{entry}"
        # Write without touching frontmatter
        fm, _ = self.read()
        self.write(fm, body)
