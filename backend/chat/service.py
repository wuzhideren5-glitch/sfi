"""Chat service — 5-source knowledge fusion agent.
v5: Session-scoped memory + sharper persona.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from core.llm import chat as deepseek_chat
from core.memory_manager import MEMORY_FENCE_CLOSE, MEMORY_FENCE_OPEN, MemoryManager
from core.profile_state import get_profile
from core.session_store import SessionManager, TEST_USER_ID
from core.web_search import web_search

KB_PATH = Path(__file__).parent.parent / "kb_data" / "alumni_records.json"

# ═══════════════════════════════════════════════════════════════
# v5 SYSTEM PROMPT — 犀利启发式小苗老师
# ═══════════════════════════════════════════════════════════════
SYSTEM_PROMPT = """你是**小苗老师**，深圳高等金融研究院CDC的资深职业规划导师。

## 你是谁
- 在深高金CDC工作超10年，看过的简历比学生吃过的饭还多
- 你**不说废话**，**不绕弯子**，**直接给结论**
- 你的风格：犀利、实战、一针见血。学生来找你是要答案的，不是来听鸡汤的

## 你的5个知识源（按优先级）
🔴 **画像**（最高权威）→ 🟠 **记忆**（历史对话）→ 🟡 **校友案例**（9位真实案例）→ 🟢 **你的专业**（基础底盘）→ 🔵 **联网搜索**（时效补充）

## 说话方式
- **直接拍板**："你应该去投行，原因有三"——不要让学生选
- **反常识**：打破学生幻想。"你以为四大好进？CPA三门只是入场券"
- **给启发**：让学生想通自己没想到的。"你Python+财务的组合，最适合的不是投行而是量化基本面研究——想过吗？"
- **不反问**：简历有的信息直接用，不要假装不知道去反问
- **每轮必有行动建议**：说完道理要给"现在就去做什么"

## 禁止
- 编造校友数据（当前9位）
- 说"你可以选A也可以选B"
- 鸡汤式鼓励
- 不知道装知道

## 校友案例如有匹配，用名字自然引用（如"喇睿萌学姐当时..."）"""

PROFILE_EXTRACT_PROMPT = """从对话中提取用户的求职目标。返回JSON：{"target_industry": ["行业"], "target_role": ["岗位"]}
如果用户没有明确表达，返回空数组。只返回JSON。"""


class ChatService:
    def __init__(self):
        self._kb: list[dict] | None = None
        self._profile_targets: dict = {"target_industry": [], "target_role": []}
        # Session → MemoryManager mapping
        self._managers: dict[int, MemoryManager] = {}

    def _load_kb(self):
        if self._kb is not None:
            return
        with open(KB_PATH) as f:
            self._kb = json.load(f)

    def _get_manager(self, session_id: int) -> MemoryManager:
        if session_id not in self._managers:
            # Evict oldest if over capacity
            if len(self._managers) >= 50:
                oldest = sorted(self._managers.keys())[:10]
                for sid in oldest:
                    del self._managers[sid]
            self._managers[session_id] = MemoryManager(session_id=session_id, user_id=TEST_USER_ID)
        return self._managers[session_id]

    def _format_profile(self, profile: dict) -> str:
        if not profile or not profile.get("name"):
            return "⚠️ 尚未上传简历。对该学生背景一无所知，引导ta上传或自我介绍。"

        lines = [f"👤 {profile.get('name', '未知')}"]
        if profile.get("gender") or profile.get("age"):
            lines.append(f"   {profile.get('gender','')} {profile.get('age','')}岁 {profile.get('city','')}")

        edu = profile.get("education", [])
        if edu:
            edu_str = "；".join(f"{e.get('school','')} {e.get('major','')} {e.get('degree','')}" for e in edu)
            lines.append(f"🎓 {edu_str}")

        internships = profile.get("internships", [])
        if internships:
            intern_str = "；".join(f"{i.get('company','')} {i.get('role','')} ({i.get('duration','')})" for i in internships)
            lines.append(f"💼 {intern_str}")

        skills = profile.get("skills", [])
        if skills:
            lines.append(f"🛠 {'、'.join(skills)}")

        certs = profile.get("certificates", [])
        if certs:
            lines.append(f"📜 {'、'.join(certs)}")

        gaps = profile.get("gaps", [])
        if gaps:
            lines.append(f"📈 待提升：{'、'.join(gaps)}")

        targets = profile.get("target_industry", []) or self._profile_targets.get("target_industry", [])
        roles = profile.get("target_role", []) or self._profile_targets.get("target_role", [])
        if targets or roles:
            lines.append(f"🎯 {'、'.join(targets)} {'、'.join(roles)}")

        return "\n".join(lines)

    async def send_message(self, message: str, session_id: int | None = None, history: list[dict] | None = None) -> dict:
        """Send message, auto-creating session if none provided."""
        self._load_kb()

        # Create session if needed
        if session_id is None:
            sess = SessionManager.create(user_id=TEST_USER_ID)
            session_id = sess["session_id"]

        memory = self._get_manager(session_id)

        # ── Priority 1: Profile ──
        profile = get_profile()
        profile_text = self._format_profile(profile)

        # ── Priority 2: Memory ──
        memory_block = self._build_memory_block(message, memory)

        # ── Priority 3: Alumni KB ──
        alumni_block = self._build_alumni_block(message)

        # ── Priority 5: Web Search ──
        web_block = self._build_web_block(message)

        # ── Build messages ──
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "system", "content": f"🔴 学生画像\n{profile_text}"},
        ]

        if memory_block:
            messages.append({"role": "system", "content": memory_block})

        if alumni_block:
            messages.append({"role": "system", "content": alumni_block})
        else:
            messages.append({"role": "system", "content": self._empty_alumni_block()})

        if web_block:
            messages.append({"role": "system", "content": web_block})

        messages.append({"role": "user", "content": message})

        # ── Call LLM ──
        try:
            reply = deepseek_chat(messages, model="deepseek-chat", temperature=0.8, max_tokens=1500)
        except Exception:
            import logging
            logging.getLogger(__name__).exception("Chat failed")
            return {"reply": "抱歉，服务暂时不可用，请稍后重试", "session_id": session_id, "error": "internal_error"}

        # ── Post-turn ──
        memory.sync(message, reply)
        await self._extract_profile(message, reply)

        return {
            "reply": reply,
            "session_id": session_id,
            "kb_sources": len(self._kb) if self._kb else 0,
            "personal_memories": memory.get_memory_count(),
            "profile": self._profile_targets,
        }

    def _build_memory_block(self, message: str, memory: MemoryManager) -> str:
        parts = []
        fts5_context = memory.prefetch(message)
        if fts5_context:
            parts.append(fts5_context)

        recent = memory.get_recent_history(30)
        if recent:
            lines = []
            for turn in recent:
                role_label = "学生" if turn["role"] == "user" else "小苗老师"
                lines.append(f"[{role_label}]：{turn['content'][:200]}")
            parts.append(
                f"{MEMORY_FENCE_OPEN}\n最近 {len(recent)} 轮对话：\n" + "\n".join(lines) + f"\n{MEMORY_FENCE_CLOSE}"
            )

        if not parts:
            return ""
        return "🟠 历史记忆\n" + "\n\n".join(parts)

    def _build_alumni_block(self, message: str) -> str:
        kb_context = self._search_kb(message)
        if not kb_context:
            return ""
        return "🟡 校友案例\n⚠️ 共9位校友，只引用下面出现的\n" + kb_context

    def _empty_alumni_block(self) -> str:
        return "🟡 校友案例：无匹配\n9位校友中无此方向。诚实告知，不编造。"

    def _build_web_block(self, message: str) -> str:
        if not self._should_search_web(message):
            return ""
        web_context = web_search(message, max_results=3)
        if not web_context:
            return ""
        from datetime import datetime
        return f"🔵 联网搜索 ({datetime.now().strftime('%m/%d')})\n{web_context}"

    async def _extract_profile(self, user_msg: str, ai_reply: str):
        try:
            result = deepseek_chat(
                messages=[
                    {"role": "system", "content": PROFILE_EXTRACT_PROMPT},
                    {"role": "user", "content": f"学生：{user_msg}\n小苗老师：{ai_reply}"},
                ],
                model="deepseek-chat", temperature=0.0, max_tokens=200,
            )
            result = result.strip()
            if result.startswith("```"):
                result = result.split("\n", 1)[-1].rsplit("```", 1)[0]
            data = json.loads(result)
            if data.get("target_industry"):
                self._profile_targets["target_industry"] = data["target_industry"]
            if data.get("target_role"):
                self._profile_targets["target_role"] = data["target_role"]
        except Exception:
            pass

    def _should_search_web(self, query: str) -> bool:
        triggers = ["最新", "2025", "2026", "今年", "最近", "现在", "当前", "招聘", "薪资", "行情", "趋势",
                     "面试题", "面经", "笔试", "怎么准备", "中金", "中信", "华泰", "高盛", "摩根"]
        return any(t in query for t in triggers)

    def _search_kb(self, query: str, top_k: int = 3) -> str:
        if not self._kb:
            return ""
        query_lower = query.lower()
        scored = []
        tokens = re.findall(r'[a-zA-Z]+', query_lower)
        chinese = re.sub(r'[a-zA-Z\s\d]+', '', query_lower)
        for i in range(len(chinese) - 1):
            tokens.append(chinese[i:i + 2])
        if len(chinese) == 1:
            tokens.append(chinese)

        for record in self._kb:
            name = record.get("name", "")
            tags = [t.lower() for t in record.get("tags", [])]
            insights = " ".join(record.get("insights", [])).lower()
            career = " ".join(str(c) for c in record.get("career_path", [])).lower()
            job = str(record.get("job_search", {})).lower()
            all_text = f"{name.lower()} {' '.join(tags)} {insights} {career} {job}".lower()
            score = 0
            for token in tokens:
                if any(token in t for t in tags):
                    score += 5
                if token in name.lower():
                    score += 4
                if token in record.get("program", "").lower():
                    score += 3
                if token in insights:
                    score += 2
                if token in all_text:
                    score += 1
            if score > 0:
                scored.append((score, record))

        scored.sort(key=lambda x: x[0], reverse=True)
        if not scored:
            return ""

        lines = []
        for _, r in scored[:top_k]:
            internships = r.get("internships", [])
            intern_str = ", ".join(f"{i.get('company','')} {i.get('role','')}" for i in internships[:2]) if internships else "无"
            final = r.get("job_search", {}).get("final_choice", "未知")
            ins = r.get("insights", [])
            ins_str = "; ".join(ins[:3]) if ins else "无"
            lines.append(f"【{r['name']}】{r.get('program','')} {r.get('graduation_year','')}届\n  实习：{intern_str}\n  去向：{final}\n  经验：{ins_str}")
        return "\n\n".join(lines)
