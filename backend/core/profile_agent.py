"""
Profile Update Agent — 对话驱动自动更新学生档案。

工作方式：
1. 每轮对话后检查是否达到更新阈值（默认 2-3 轮）
2. 达到阈值时，调用 LLM 分析最近对话，提取关键洞察
3. 静默更新 MD 档案的「对话洞察」和 frontmatter 结构化字段
4. 更新计数器归零，开始下一轮周期
"""
from __future__ import annotations

import json
import re

from core.llm import chat as deepseek_chat
from core.profile_store import ProfileStore

UPDATE_INTERVAL = 3  # 每 N 轮对话触发一次更新

UPDATE_SYSTEM_PROMPT = """你是学生档案更新助手。根据最近的对话，更新学生个人档案。

你需要输出两部分：
1. **结构化更新**（JSON）：更新 frontmatter 字段
2. **洞察摘要**（Markdown）：对学生的关键认知，用于未来对话参考

## 结构化更新规则
- 只输出**有变化**的字段，不变的不输出
- 如果学生在对话中透露了新信息（学校、实习、目标行业等），写入对应字段
- 字段格式：
  education: [{school, degree, major, year}]
  internships: [{company, role, duration, description}]
  skills: ["技能1"]
  target_industry: ["行业1"]
  target_role: ["岗位1"]
  gaps: ["短板1"]

## 洞察摘要规则
- 用第三人称描述（"该学生……"）
- 记录：背景认知、目标方向、性格特点、关键诉求、需要跟进的事项
- 每条洞察一行，用 "- " 开头
- 不要重复已有洞察（参考下方「当前洞察」）
- 不要记录对话本身（"上一轮问了……"），只记录对学生的认知

## 输出格式（严格遵守）
```
<<<JSON>>>
{"name": "更新后的值", "target_industry": ["新增行业"]}
<<<INSIGHTS>>>
- 该学生……（新增洞察）
- 该学生……（补充认知）
```

规则：
- 没有变化就输出空的 JSON `{}` 和空的洞察
- 不编造信息，只从对话中提取
- 如果对话中没有新信息，不要强行输出"""


class ProfileAgent:
    """管理单个用户档案的自动更新。"""

    def __init__(self, user_id: str = "user_test_001"):
        self.user_id = user_id
        self.store = ProfileStore(user_id)
        self._turn_counter = 0
        self._recent_turns: list[str] = []  # 缓存最近几轮用于更新分析

    def tick(self, user_msg: str, ai_reply: str) -> dict | None:
        """每轮对话后调用。返回更新结果或 None。"""
        self._turn_counter += 1
        self._recent_turns.append(f"学生：{user_msg}\n小苗老师：{ai_reply}")

        # Keep only recent turns for analysis
        if len(self._recent_turns) > 10:
            self._recent_turns = self._recent_turns[-10:]

        if self._turn_counter < UPDATE_INTERVAL:
            return None

        # Trigger update
        result = self._run_update()
        self._turn_counter = 0
        self._recent_turns = []
        return result

    def _run_update(self) -> dict | None:
        """Call LLM to analyze recent conversation and update profile."""
        current_insights = self.store.get_insights()
        current_fm = self.store.get_frontmatter()

        # Build the update prompt
        turns_text = "\n\n---\n\n".join(self._recent_turns)
        fm_summary = json.dumps(current_fm, ensure_ascii=False, indent=2)

        prompt = f"""## 学生当前档案（frontmatter）
{fm_summary}

## 当前洞察
{current_insights or "（无）"}

## 最近对话
{turns_text}

请分析以上对话，提取学生的新信息和关键认知，按格式输出更新。"""

        try:
            result = deepseek_chat(
                messages=[
                    {"role": "system", "content": UPDATE_SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                model="deepseek-chat",
                temperature=0.3,
                max_tokens=1000,
            )

            # Parse the result
            fm_updates = self._parse_json_block(result)
            new_insights = self._parse_insights_block(result)

            changes = {}

            # Update frontmatter
            if fm_updates and fm_updates != {}:
                self._merge_frontmatter(fm_updates)
                changes["frontmatter"] = fm_updates

            # Update insights
            if new_insights and new_insights.strip():
                self.store.update_insights(new_insights)
                changes["insights"] = new_insights[:200]

            return changes if changes else None

        except Exception as e:
            import logging
            logging.getLogger(__name__).warning("ProfileAgent update failed: %s", e)
            return None

    def _parse_json_block(self, text: str) -> dict:
        """Extract JSON from <<<JSON>>> block."""
        m = re.search(r'<<<JSON>>>\s*\n?(.*?)(?=<<<INSIGHTS>>>|\Z)', text, re.DOTALL)
        if not m:
            return {}
        raw = m.group(1).strip()
        # Clean markdown code fences
        raw = re.sub(r'^```(?:json)?\s*', '', raw)
        raw = re.sub(r'\s*```$', '', raw)
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return {}

    def _parse_insights_block(self, text: str) -> str:
        """Extract insights from <<<INSIGHTS>>> block."""
        m = re.search(r'<<<INSIGHTS>>>\s*\n?(.*?)$', text, re.DOTALL)
        if not m:
            return ""
        return m.group(1).strip()

    def _merge_frontmatter(self, updates: dict):
        """Merge LLM updates into profile frontmatter.
        Smart merge: lists are extended (not replaced), scalars are replaced.
        """
        current = self.store.get_frontmatter()

        for key, value in updates.items():
            if key == "education" or key == "internships":
                # These are lists of dicts — extend if new items have unique schools/companies
                existing = current.get(key, [])
                existing_ids = set()
                if key == "education":
                    existing_ids = {e.get("school", "") + e.get("major", "") for e in existing}
                else:
                    existing_ids = {i.get("company", "") + i.get("role", "") for i in existing}

                for item in value:
                    item_id = ""
                    if key == "education":
                        item_id = item.get("school", "") + item.get("major", "")
                    else:
                        item_id = item.get("company", "") + item.get("role", "")
                    if item_id and item_id not in existing_ids:
                        existing.append(item)
                current[key] = existing

            elif isinstance(value, list):
                # skills, target_industry, target_role, certificates, gaps — extend lists
                existing_list = current.get(key, [])
                for item in value:
                    if item not in existing_list:
                        existing_list.append(item)
                current[key] = existing_list

            elif value is not None and value != "":
                # Scalar values: name, gender, age, city — only update if empty or explicitly changed
                if not current.get(key) or current.get(key) != value:
                    current[key] = value

        self.store.update_frontmatter(current)

    def force_update(self, user_msg: str, ai_reply: str) -> dict | None:
        """Force an immediate update regardless of counter."""
        self._recent_turns.append(f"学生：{user_msg}\n小苗老师：{ai_reply}")
        result = self._run_update()
        self._recent_turns = []
        self._turn_counter = 0
        return result
