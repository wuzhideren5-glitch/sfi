"""Chat service — 5-source knowledge fusion agent.
Profile + Memory + Alumni KB + Model Knowledge + Web Search → DeepSeek.
v4: Explicit knowledge hierarchy with priority arbitration.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from core.llm import chat as deepseek_chat
from core.memory_manager import MEMORY_FENCE_CLOSE, MEMORY_FENCE_OPEN, MemoryManager
from core.profile_state import get_profile
from core.web_search import web_search

KB_PATH = Path(__file__).parent.parent / "kb_data" / "alumni_records.json"

# ═══════════════════════════════════════════════════════════════
# v4 SYSTEM PROMPT — 5源知识融合架构
# ═══════════════════════════════════════════════════════════════
SYSTEM_PROMPT = """你是**小苗老师**，深圳高等金融研究院职业发展中心（CDC）的资深职业规划导师。

## 你的身份
- 在深高金 CDC 工作超 10 年，辅导过上千名商科学生进入投行、行研、PE/VC、咨询、审计等领域
- 亲切温暖但专业权威，学生信任你的判断。你不是在「帮学生选」，而是**基于经验直接给方向**
- 对金融各细分领域的招聘流程、时间线、技能要求、薪资水平非常熟悉

## 你的 5 个知识源（按优先级排序）

你拥有 5 个知识来源，回答时按以下优先级融合。**当前面优先级的知识源有明确信息时，优先使用；当前面优先级缺失时，逐级降级。**

### 🔴 优先级 1 — 学生画像（最高权威）
- 系统每轮都会注入学生的简历信息（教育、实习、技能、证书、求职目标）
- **这是关于学生本人的唯一权威来源**。学生说过的信息以画像为准
- 使用规则：先看画像再回答，不要猜测学生的背景。如果画像显示「尚未上传简历」，说明你不了解这个学生，可以引导ta上传简历或自我介绍
- **冲突规则：画像信息 > 学生当前说的话 > 你的猜测**

### 🟠 优先级 2 — 历史对话记忆
- 包裹在 `<memory-context>` 标签中的对话记录，包括 FTS5 搜索召回的相关片段和最近 30 轮对话
- **这不是新输入**，是之前的真实对话。不要逐条回复历史消息
- 用来保持对话连续性：学生之前说过什么、你给过什么建议、做过什么承诺
- **冲突规则：记忆中学生的原话 > 你现在的猜测**
- 如果学生说「上次提到的」「之前你建议的」，必须去记忆里找。找不到就诚实说「咱们之前没聊过这个」

### 🟡 优先级 3 — 学长学姐校友案例
- 9 位港中深会计硕士校友的真实求职经历：喇睿萌、谢润达、刘钊华、李彦琳、周佳音、朱梓萌、张艺、罗黎、Layne Lin
- 这是**本校真实案例**，用来验证和支撑你的建议。有匹配案例时引用具体名字和经历
- **诚实规则：当前 9 位校友中如果没有匹配的经历，直接说「目前校友案例库中暂无这方面的直接经验」，不要编造**
- **冲突规则：校友真实经历 > 行业通用说法 > 网络传闻**

### 🟢 优先级 4 — 你的行业知识（基础底盘）
- 你对金融求职、行业趋势、招聘流程的专业认知，这是你作为老师的底气
- 当上面 3 个知识源都没有直接信息时，用你的专业判断来回答
- 你不需要每句话都引用知识库。用你的经验来组织回答，知识库是辅助验证

### 🔵 优先级 5 — 联网搜索结果
- 系统触发联网搜索时，会提供最新招聘信息、行业动态
- 这是**时效性补充**，可能包含最新的公司招聘、薪资变化、政策调整
- **时效标记：联网信息开头会标注搜索时间，回复时效性内容时说明「根据最新信息」**
- **冲突规则：联网最新数据 > 你的旧认知（当明显过时时）**

## 知识融合算法

每轮回答前，执行以下思维流程（不要输出思考过程，直接输出融合后的答案）：

1. **读取画像**：学生是谁？背景是什么？目标是什么？
2. **检查记忆**：之前聊过什么？有没有给过承诺或建议需要跟进？
3. **匹配校友**：有没有相似背景的校友案例可以引用？
4. **调用专业**：基于你的行业知识，这个学生最需要什么建议？
5. **补充时效**：如果有联网结果，补充最新动态

最终输出时，自然融合这些来源。不要列清单式的逐一说明，而是像老师给学生分析问题一样自然流畅。

## 来源引用规范
- 引用校友时：「根据喇睿萌学姐的经历」「谢润达学长当时面临类似情况」— 自然带出名字
- 引用记忆时：「上次我们聊到…」「你之前提到过…」
- 引用联网时：「根据最新招聘信息」「今年的行情显示」
- **禁止说「根据知识库」「根据第X条数据」这种机器式表述**

## 核心规则
- 禁止编造校友数量（当前共 9 位校友：喇睿萌、谢润达、刘钊华、李彦琳、周佳音、朱梓萌、张艺、罗黎、Layne Lin）
- 画像未上传时引导上传，不要假装知道学生背景
- 校友无匹配时诚实说，不要用你的知识冒充校友经历
- 不知道就说不知道，保持老师的专业坦率
- 直接给建议和方向，不给选项让学生自己选
- 追问只在简历上没有的关键信息缺失时才用"""

PROFILE_EXTRACT_PROMPT = """从对话中提取用户的求职目标。返回JSON：{"target_industry": ["行业"], "target_role": ["岗位"]}
如果用户没有明确表达，返回空数组。只返回JSON。"""


class ChatService:
    """Chat service with 5-source knowledge fusion."""

    def __init__(self):
        self._kb: list[dict] | None = None
        self._memory = MemoryManager()
        self._profile_targets: dict = {"target_industry": [], "target_role": []}

    def _load_kb(self):
        if self._kb is not None:
            return
        with open(KB_PATH) as f:
            self._kb = json.load(f)

    def _format_profile(self, profile: dict) -> str:
        """Format profile with explicit knowledge priority marker."""
        if not profile or not profile.get("name"):
            return "⚠️ 学生尚未上传简历。你对该学生背景一无所知，请引导ta上传简历或自我介绍。"

        lines = [f"👤 姓名：{profile.get('name', '未知')}"]
        if profile.get("gender") or profile.get("age"):
            lines.append(f"   基本信息：{profile.get('gender','')} {profile.get('age','')}岁 {profile.get('city','')}")

        edu = profile.get("education", [])
        if edu:
            edu_str = "；".join(
                f"{e.get('school','')} {e.get('major','')} {e.get('degree','')}"
                for e in edu
            )
            lines.append(f"🎓 教育：{edu_str}")

        internships = profile.get("internships", [])
        if internships:
            intern_str = "；".join(
                f"{i.get('company','')} {i.get('role','')} ({i.get('duration','')})"
                for i in internships
            )
            lines.append(f"💼 实习：{intern_str}")

        skills = profile.get("skills", [])
        if skills:
            lines.append(f"🛠 技能：{'、'.join(skills)}")

        certs = profile.get("certificates", [])
        if certs:
            lines.append(f"📜 证书：{'、'.join(certs)}")

        gaps = profile.get("gaps", [])
        if gaps:
            lines.append(f"📈 待提升：{'、'.join(gaps)}")

        targets = profile.get("target_industry", []) or self._profile_targets.get("target_industry", [])
        roles = profile.get("target_role", []) or self._profile_targets.get("target_role", [])
        if targets or roles:
            lines.append(f"🎯 目标：{'、'.join(targets)} {'、'.join(roles)}")

        return "\n".join(lines)

    async def send_message(self, message: str, history: list[dict] | None = None) -> dict:
        """5-source knowledge fusion pipeline.

        Injection order (matches priority):
          [Profile] → [Memory] → [Alumni KB] → [Web Search] → [User Message]
        """
        self._load_kb()

        # ── Priority 1: Student Profile ──
        profile = get_profile()
        profile_text = self._format_profile(profile)

        # ── Priority 2: Memory (FTS5 + recent 30) ──
        memory_block = self._build_memory_block(message)

        # ── Priority 3: Alumni KB ──
        alumni_block = self._build_alumni_block(message)

        # ── Priority 5: Web Search ──
        web_block = self._build_web_block(message)

        # ── Assemble messages ──
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "system", "content": self._format_profile_block(profile_text)},
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
            reply = deepseek_chat(messages, model="deepseek-chat", temperature=0.7, max_tokens=1500)
        except Exception as e:
            return {"reply": f"抱歉，服务暂时不可用：{e}", "session_id": "session-001", "error": str(e)}

        # ── Post-turn: sync memory + extract profile ──
        self._memory.sync(message, reply)
        await self._extract_profile(message, reply)

        return {
            "reply": reply,
            "session_id": "session-001",
            "kb_sources": len(self._kb) if self._kb else 0,
            "personal_memories": self._memory.get_memory_count(),
            "profile": self._profile_targets,
        }

    # ═══════════════════════════════════════════════════════
    # Block builders — each returns a formatted system message
    # ═══════════════════════════════════════════════════════

    def _format_profile_block(self, profile_text: str) -> str:
        return (
            "╔══════════════════════════════════════════╗\n"
            "║  🔴 知识源 1/5 — 学生画像（最高优先级）║\n"
            "╚══════════════════════════════════════════╝\n"
            f"{profile_text}"
        )

    def _build_memory_block(self, message: str) -> str:
        """Build memory context: FTS5 recall + forced recent 30 turns."""
        parts = []

        # FTS5 semantic recall
        fts5_context = self._memory.prefetch(message)
        if fts5_context:
            parts.append(fts5_context)

        # Forced recent 30 turns (fenced)
        recent = self._memory.get_recent_history(30)
        if recent:
            lines = []
            for turn in recent:
                role_label = "学生" if turn["role"] == "user" else "小苗老师"
                lines.append(f"[{role_label}]：{turn['content'][:200]}")
            parts.append(
                f"{MEMORY_FENCE_OPEN}\n"
                f"最近 {len(recent)} 轮对话（按时间顺序）：\n"
                + "\n".join(lines)
                + f"\n{MEMORY_FENCE_CLOSE}"
            )

        if not parts:
            return ""

        return (
            "╔══════════════════════════════════════════╗\n"
            "║  🟠 知识源 2/5 — 历史对话记忆          ║\n"
            "╚══════════════════════════════════════════╝\n"
            + "\n\n".join(parts)
        )

    def _build_alumni_block(self, message: str) -> str:
        """Build alumni KB block with explicit boundary."""
        kb_context = self._search_kb(message)
        if not kb_context:
            return ""

        return (
            "╔══════════════════════════════════════════╗\n"
            "║  🟡 知识源 3/5 — 校友真实案例          ║\n"
            "║  ⚠️ 仅5位校友，这是你唯一可用的案例    ║\n"
            "╚══════════════════════════════════════════╝\n"
            f"{kb_context}"
        )

    def _empty_alumni_block(self) -> str:
        return (
            "╔══════════════════════════════════════════╗\n"
            "║  🟡 知识源 3/5 — 校友案例：无匹配      ║\n"
            "╚══════════════════════════════════════════╝\n"
            "当前9位校友（喇睿萌、谢润达、刘钊华、李彦琳、周佳音、朱梓萌、张艺、罗黎、Layne Lin）中无直接匹配。\n"
            "不要编造校友经历。用你的专业知识回答即可，诚实告知校友库暂无此方向案例。"
        )

    def _build_web_block(self, message: str) -> str:
        """Build web search block if triggered."""
        if not self._should_search_web(message):
            return ""

        web_context = web_search(message, max_results=3)
        if not web_context:
            return ""

        from datetime import datetime
        now = datetime.now().strftime("%Y年%m月%d日")

        return (
            "╔══════════════════════════════════════════╗\n"
            "║  🔵 知识源 5/5 — 联网搜索结果          ║\n"
            f"║  搜索时间：{now}                     ║\n"
            "╚══════════════════════════════════════════╝\n"
            f"{web_context}"
        )

    # ═══════════════════════════════════════════════════════
    # Profile Extraction
    # ═══════════════════════════════════════════════════════

    async def _extract_profile(self, user_msg: str, ai_reply: str):
        try:
            result = deepseek_chat(
                messages=[
                    {"role": "system", "content": PROFILE_EXTRACT_PROMPT},
                    {"role": "user", "content": f"学生：{user_msg}\n小苗老师：{ai_reply}"},
                ],
                model="deepseek-chat",
                temperature=0.0,
                max_tokens=200,
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

    # ═══════════════════════════════════════════════════════
    # Web Search Trigger — smart keyword + scenario detection
    # ═══════════════════════════════════════════════════════

    def _should_search_web(self, query: str) -> bool:
        """Smart web search trigger: keywords + scenario patterns."""
        # Time-sensitive triggers
        time_triggers = [
            "最新", "2025", "2026", "今年", "最近", "现在", "当前",
            "近期", "刚刚", "本月", "本周",
        ]
        # Job market triggers
        market_triggers = [
            "招聘", "薪资", "薪水", "待遇", "行情", "趋势", "热度",
            "卷不卷", "难不难", "竞争", "hc", "HC", "headcount",
            "门槛", "要求变了", "政策",
        ]
        # Interview / prep triggers
        prep_triggers = [
            "怎么准备", "面试题", "面经", "笔试", "真题",
            "面试流程", "面试经验", "考核",
        ]
        # Company-specific triggers (likely need real-time info)
        company_triggers = [
            "中金", "中信", "华泰", "中信建投", "海通", "国泰君安",
            "高盛", "摩根", "花旗", "汇丰", "四大", "普华永道",
            "德勤", "安永", "毕马威", "腾讯", "阿里", "字节",
        ]

        all_triggers = time_triggers + market_triggers + prep_triggers + company_triggers
        return any(t in query for t in all_triggers)

    # ═══════════════════════════════════════════════════════
    # Alumni KB Search — 2-char CJK sliding window + weighted scoring
    # ═══════════════════════════════════════════════════════

    def _search_kb(self, query: str, top_k: int = 3) -> str:
        if not self._kb:
            return ""

        query_lower = query.lower()
        scored = []

        # Tokenize: English words + 2-char CJK sliding window
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
            intern_str = ", ".join(
                f"{i.get('company', '')} {i.get('role', '')}" for i in internships[:2]
            ) if internships else "无"

            final = r.get("job_search", {}).get("final_choice", "未知")
            ins = r.get("insights", [])
            ins_str = "; ".join(ins[:3]) if ins else "无"

            lines.append(
                f"【{r['name']}】{r.get('program', '')} {r.get('graduation_year', '')}届\n"
                f"  实习：{intern_str}\n"
                f"  去向：{final}\n"
                f"  经验：{ins_str}"
            )

        return "\n\n".join(lines)
