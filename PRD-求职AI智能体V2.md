# 港中深求职AI智能体 - PRD V2.0

> **版本**：V2.0 — 知识融合 + 记忆系统升级
> **日期**：2026-05-18
> **产品定位**：面向港中深商科研究生的 AI 求职导师，基于 9 位校友真实经历 + 5 源知识融合 + 跨 Session 长效记忆

---

## 一、产品概述

### 1.1 一句话定位
**用校友的真实路径 + 5 源知识融合 + 永不遗忘的 AI 导师，帮学生拍板求职方向。**

### 1.2 目标用户

| 维度 | 描述 |
|------|------|
| 学校 | 香港中文大学（深圳） |
| 学历 | 硕士研究生 |
| 专业 | 商科为主（会计 / 金融 / 商业分析） |
| 痛点 | 方向迷茫、不知如何准备、不知道同背景校友去了哪 |

### 1.3 产品形态
- **前端**：Next.js 14 Web 应用（紫色学院风 + 移动端适配）
- **交互**：对话式 AI（小苗老师 Persona）
- **后端**：FastAPI + DeepSeek + 阿里百炼 Embedding + Serper 联网搜索

### 1.4 V2 核心差异化

| V1 | V2 升级 |
|----|---------|
| 5 位校友 KB | **9 位**校友全部向量化 |
| 简单 RAG | **5 源知识融合**（画像 > 记忆 > 校友 > 模型 > 联网），显式优先级 + 冲突仲裁 |
| JSON + npy 记忆 | **SQLite FTS5 trigram** + MemoryManager（Hermes 风格） |
| 单 session | **独立 Session 管理**，跨 session 同用户记忆，用户间记忆隔离 |
| 温和顾问型 | **犀利拍板型**："你应该去投行，原因有三" |
| 桌面端 | 桌面 + **移动端适配** |

---

## 二、分阶段实施计划

```
Phase 1 (✅ 完成)    Phase 2 (✅ 完成)    Phase 3 (🔄 进行中)
基础对话 + KB RAG    记忆系统 + 多源融合    Session + 部署
```

### Phase 1：基础对话引擎（已完成）
**目标**：简历解析 → 画像构建 → 校友 KB RAG → DeepSeek 对话

- ✅ 简历 PDF 上传解析（PyMuPDF）
- ✅ 5 位校友 KB 摄入
- ✅ 前端聊天界面
- ✅ DeepSeek 对接

### Phase 2：记忆系统 + 知识融合（已完成）
**目标**：Hermes 风格记忆 + 5 源知识优先级

- ✅ SQLite FTS5 trigram 全文搜索
- ✅ MemoryManager（prefetch → sync 生命周期）
- ✅ Memory Fencing（`<memory-context>` 标签）
- ✅ 5 源知识融合架构（画像→记忆→校友→模型→联网）
- ✅ 9 位校友全部向量化入库
- ✅ 向量上传 API
- ✅ 30 轮防幻觉测试（通过）
- ✅ v5 犀利人设

### Phase 3：Session + 部署（进行中）
**目标**：独立 Session + GitHub 部署

- ✅ 独立 Session 管理 API（创建/列表/删除/历史）
- ✅ 前端侧边栏 Session 列表 + 切换
- ✅ 移动端适配
- ✅ 代码审查 + Ruff Lint 清零
- ✅ 16 项 TDD 测试覆盖
- ⬜ GitHub Push + 线上部署

### Phase 4：多用户 + 画像持久化（规划）
- ⬜ 多用户登录
- ⬜ 画像持久化到 DB
- ⬜ 后台管理面板

---

## 三、系统架构与解耦规则

### 3.0 核心原则
> **铁律：功能模块间通过标准化 API 通信，严禁跨模块直接访问对方数据库。**

```
┌─────────────────────────────────────────────────┐
│              Next.js Frontend (:3000)             │
│   Chat UI + Profile Sidebar + Session List       │
└─────────────────┬───────────────────────────────┘
                  │ HTTP REST
┌─────────────────▼───────────────────────────────┐
│           FastAPI Gateway (:8000)                 │
│  /api/chat/send  /api/session/*  /api/kb/*       │
└──┬────────┬────────┬────────┬────────┬──────────┘
   │        │        │        │        │
   ▼        ▼        ▼        ▼        ▼
┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐ ┌──────────┐
│ Chat │ │Session│ │  KB  │ │Parser│ │ Profile  │
│Service│ │Store │ │  RAG │ │      │ │  State   │
└──┬───┘ └──┬───┘ └──┬───┘ └──┬───┘ └────┬─────┘
   │        │        │        │           │
   ▼        ▼        ▼        ▼           ▼
┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐ ┌──────────┐
│FTS5  │ │SQLite│ │JSON  │ │ PyMu │ │ In-Memory│
│Memory│ │Session│ │Alumni│ │ PDF  │ │  Dict    │
└──────┘ └──────┘ └──────┘ └──────┘ └──────────┘
```

### 3.2 模块边界与接口契约

| 模块 | 职责 | 自有数据 | 对外 API | 禁止 |
|------|------|---------|----------|------|
| **Chat Service** | 5 源知识融合 + LLM 调用 | MemoryManager 映射 | `POST /api/chat/send` | ❌ 直写 KB JSON |
| **Session Store** | Session CRUD + FTS5 记忆 | SQLite sessions.db | `POST/GET /api/session/*` | ❌ 跨用户查询 |
| **MemoryManager** | prefetch/sync 生命周期 | 通过 SessionStore | 内部接口 | ❌ 跨用户 sync |
| **KB Service** | 校友案例 RAG + 向量化 | alumni_records.json | `POST /api/kb/ingest` `GET /api/kb/stats` | ❌ 修改 Chat 提示词 |
| **Parser** | PDF 简历解析 | — | `POST /api/parse/resume` | ❌ 写 KB |
| **Profile State** | 内存画像 | In-Memory Dict | 模块级 `get_profile()` | ❌ 持久化（待迁移 DB） |

### 3.3 跨模块调用规则

```
✅ 允许                         ❌ 禁止
Chat → KB (API 查询)            Chat → 直写 alumni_records.json
Chat → SessionStore (RAG)       Chat → 跨模块写 Profile
Chat → Profile (只读)           Session → 读 KB
KB → Embedding (生成向量)       KB → 写 Session
Session → SQLite (读写)         Session → 跨用户查 turns
```

### 3.4 数据隔离规范

| 规则 | 实现 |
|------|------|
| 每模块独立存储 | sessions.db / alumni_records.json / kb_vectors.json 各自独立 |
| 用户隔离 | turns 表通过 session_id → user_id 双层隔离，FTS5 查询带 user_id 过滤 |
| Session 隔离 | 每 session 独立 MemoryManager 实例，get_recent_turns 按 session_id 过滤 |
| 接口即边界 | Chat 只通过 API 获取 KB，不知道 KB 内部结构 |

---

## 四、开发路径规划

### 4.1 总览

```
Week 1-2          Week 3            Week 4
Sprint 1 (✅)      Sprint 2 (✅)     Sprint 3 (🔄)
基础对话引擎       记忆+知识融合      Session+部署
```

### 4.2 Sprint 1：基础对话引擎（✅ 完成）

| 任务 | 产出 | 验证 |
|------|------|------|
| FastAPI 骨架 | main.py + 路由注册 | `curl /health` → 200 |
| DeepSeek 对接 | core/llm.py | 对话返回 |
| KB 摄入脚本 | ingest_kb.py, 5 篇校友 | 9 篇文档全部解析 |
| 简历解析 | parser/service.py | `POST /api/parse/resume` |
| 前端聊天 UI | page.tsx | 浏览器对话 |

### 4.3 Sprint 2：记忆系统 + 知识融合（✅ 完成）

| 任务 | 产出 | 验证 |
|------|------|------|
| SQLite FTS5 记忆 | session_store.py | 16 项 TDD 测试全绿 |
| MemoryManager | memory_manager.py | prefetch/sync 工作 |
| 5 源融合 Prompt | service.py v5 | 30 轮测试 80%+ |
| KB 扩容 5→9 位 | ingest_kb.py 重跑 | `/api/kb/stats` → 9 |
| 向量上传 API | kb/upload_router.py | `POST /api/kb/ingest` |
| v5 犀利人设 | System Prompt 重写 | "直接拍板" 风格验证 |

### 4.4 Sprint 3：Session + 部署（🔄 进行中）

| 任务 | 产出 | 验证 |
|------|------|------|
| Session API | session_router.py | 创建/列表/删除/历史 |
| 前端 Session 列表 | page.tsx 重构 | 侧边栏切换 |
| 移动端适配 | 响应式 + 汉堡菜单 | 手机浏览器 |
| 代码审查 | Ruff 清零 + Reviewer | 16 tests pass |
| ⬜ GitHub Push | Git 已 commit | 待 `gh auth login` |
| ⬜ 线上部署 | Vercel + Railway | 公网可访问 |

---

## 五、核心功能详解

### 5.1 5 源知识融合

每次对话，按以下优先级注入知识：

```
🔴 Profile  →  🟠 Memory  →  🟡 Alumni KB  →  🟢 Model  →  🔵 Web
(最高权威)    (跨session)    (9位真实案例)    (DeepSeek)   (Serper)
```

**冲突仲裁规则**：
- 画像 > 学生当前说的话（学生可能记错）
- 记忆中学生原话 > Agent 猜测
- 校友真实经历 > 行业通用说法
- 联网最新数据 > 模型旧认知
- 无匹配时诚实降级，不编造

### 5.2 记忆系统架构

```
用户提问
  ├─→ MemoryManager.prefetch(query)
  │     └─→ SessionStore.search() (FTS5 trigram, 跨 session, 同用户)
  │           └─→ <memory-context> 包裹的历史片段
  ├─→ 注入 Agent messages（5 层）
  ├─→ DeepSeek 生成回复
  └─→ MemoryManager.sync(user_msg, assistant_reply)
        └─→ SessionStore.add_turn() × 2
              ├─→ 写入 turns 表
              └─→ 写入 turns_fts 虚拟表（trigram 索引）
```

**Memory Fencing**：历史记忆用 `<memory-context>` 标签包裹，防止 LLM 将记忆内容误认为新指令。

**自动截断**：单 session 超过 200 轮自动清理最旧记录，仅删除当前 session 的 turns 和 FTS5 索引。

### 5.3 Session 管理

```
POST /api/session/create     → 创建新 session
GET  /api/session/list       → 当前用户所有 session
GET  /api/session/{id}/history → session 全部对话
DELETE /api/session/{id}     → 删除（需所有权验证）
```

- 每个用户独立 session 列表
- 前端侧边栏实时展示 + 一键切换
- 切换时从 API 加载完整历史
- 新对话自动创建 session，标题取自首条消息

### 5.4 知识库向量化上传

```
POST /api/kb/ingest
  ← multipart/form-data (PDF/DOCX/TXT)
  → { name, program, embedding_dim, kb_total }
```

流程：文件上传 → 文本提取 → DeepSeek 结构化解析 → 阿里百炼 1024 维 Embedding → 存入 JSON + 向量库

---

## 六、AI 能力矩阵

| 能力 | 技术 | 阶段 |
|------|------|------|
| 简历解析 | PyMuPDF + DeepSeek 结构化 | ✅ |
| 校友 KB RAG | 2-char CJK 滑动窗口 + 加权评分 | ✅ |
| 长期记忆 | SQLite FTS5 trigram | ✅ |
| 5 源知识融合 | 显式优先级 + 冲突仲裁 | ✅ |
| Memory Fencing | `<memory-context>` 标签 | ✅ |
| Session 管理 | 独立 session + 用户隔离 | ✅ |
| 联网搜索 | Serper.dev 35+ 触发词 | ✅ |
| 向量化 KB | 阿里百炼 DashScope 1024d | ✅ |
| 防幻觉 | 3 层防御（强约束 KB Header + 空 KB 降级 + 诚实规则） | ✅ |
| 代码质量 | Ruff Lint + TDD 16 tests | ✅ |

---

## 七、对话策略设计

### 7.1 无画像场景
> 学生："老师好，我想找工作"
> Agent："没简历我等于盲人摸象。上传简历，或者告诉我你的学校、专业、实习经历。"

### 7.2 有画像 + 有 KB 匹配
> 学生："想了解投行方向"
> Agent：先看画像 → 匹配周佳音学姐经历 → 引用经验："周佳音学姐当时和你背景相似，她是从四大IPO实习切入投行。她有三点经验你直接用..."

### 7.3 有画像 + 无 KB 匹配
> Agent："9 位校友中暂无此方向直接经验。基于你的背景（安永审计 + CPA三门），我建议..."

### 7.4 跨 Session 记忆
> 学生："上次你建议我补CPA，我已经开始准备了"
> Agent：FTS5 搜索 "CPA" → 召回历史 → "对，上次我和你分析过..." — 不重复问已知道的信息

---

## 八、AI 角色人格定义（小苗老师 v5）

> **Persona**：小苗老师
> **定位**：深高金 CDC 10 年+ 资深导师，犀利直接，不废话

### 8.1 核心人格特质

| 特质 | 描述 | 正例 | 反例 |
|------|------|------|------|
| 直接拍板 | 不给选项让学生选 | "投行更适合你，原因有三" | "你可以选投行也可以选咨询" |
| 反常识 | 打破学生幻想 | "CPA三门只是入场券，不是优势" | "CPA三门很不错，继续加油" |
| 给启发 | 让学生想通没想到的 | "你Python+财务的组合最适合量化基本面研究—想过吗？" | "你可以多了解一些方向" |
| 不反问 | 画像有的直接用 | 看完画像直接分析 | "你是什么专业来着？" |
| 行动导向 | 每轮给具体行动 | "现在就去投中金2026暑期实习" | "你要好好准备" |
| 不说鸡汤 | 不讲空话 | 给数据、给路径、给时间线 | "相信自己，你一定能行" |

### 8.2 禁止行为

| 类别 | 禁止内容 |
|------|---------|
| 🚫 编造数据 | 编造校友数量、伪造校友经历 |
| 🚫 替人决策 | "你必须去XX公司" |
| 🚫 贩卖焦虑 | "你这个背景找不到工作的" |
| 🚫 过度承诺 | "按我说的做一定能进中金" |
| 🚫 泄露隐私 | 暴露其他学生的简历/对话信息 |
| 🚫 鸡汤废话 | "加油""相信自己""你很棒" |

### 8.3 System Prompt 结构

```
[角色] 你是小苗老师，深高金CDC资深导师...
[画像] {每轮注入学生简历}
[记忆] <memory-context> {FTS5召回 + 最近30轮} </memory-context>
[校友] {KB RAG 匹配结果，或"无匹配"}
[联网] {Serper 搜索结果，触发时注入}
[核心规则] 直接拍板、不编造、不反问...
[用户消息]
```

---

## 九、技术栈

| 层 | 选型 | 说明 |
|----|------|------|
| 前端 | Next.js 14 (App Router) + Tailwind | 紫色金色学院风，移动端适配 |
| 后端 | FastAPI + Python 3.12 | 5 模块解耦 |
| 主模型 | DeepSeek (deepseek-chat) | OpenAI 兼容 API |
| Embedding | 阿里百炼 DashScope (text-embedding-v4) | 1024 维 |
| 记忆库 | SQLite + FTS5 trigram | WAL 模式，跨 session 搜索 |
| 校友 KB | JSON + 2-char 滑动窗口 RAG | 9 位校友，向量化存储 |
| 联网搜索 | Serper.dev (Google Search API) | 35+ 触发词 |
| 测试 | pytest 16 tests | Session 隔离 + FTS5 验证 |
| Lint | Ruff (all checks passed) | 自动化修复 |
| 部署 | Vercel (前端) + Railway (后端) | 待 push |

---

## 十、效果评估指标

| 指标 | 目标 | 评估方式 |
|------|------|---------|
| 对话通过率 | ≥ 90% 功能正常 | API 自动化测试 |
| 防幻觉准确率 | 无匹配方向 100% 诚实 | 测试集验证 |
| 记忆召回准确率 | 跨轮引用 ≥ 95% | 30 轮测试 |
| 校友引用准确率 | 100% 引用真实校友名 | 人工抽查 |
| Session 切换 | < 1s 加载历史 | 前端性能测试 |
| Ruff Lint | 0 errors | CI 自动化 |
| 测试覆盖率 | Session 模块 100% | 16/16 tests |

---

## 十一、对话质量评估

| 维度 | 权重 | 说明 |
|------|------|------|
| 准确性 | 30% | 校友引用正确、建议符合行业实际 |
| 相关性 | 25% | 回复紧扣学生背景和目标 |
| 记忆有效性 | 20% | 正确引用历史对话，不重复问 |
| 引导能力 | 15% | 给具体行动建议，不是泛泛而谈 |
| 语气得体 | 10% | 犀利但不伤人，专业但不傲慢 |

**评估方式**：每周随机抽检 20 轮，LLM-as-Judge 评分 + 人工复审抽检 20%

---

## 十二、风险与应对

| 风险 | 影响 | 应对 |
|------|------|------|
| DeepSeek 服务中断 | 对话不可用 | 已有错误脱敏 + 提示重试 |
| SQLite 锁竞争 | 写入失败 | 单 worker + WAL 模式 |
| 幻觉编织校友数据 | 误导学生 | 3 层防御 + 诚实规则 |
| KB 膨胀 | 检索变慢 | JSON RAG 轻量级，暂无需优化 |
| 联网搜索费用 | 成本上升 | 触发词精准控制 |

---

## 十三、下一步行动

1. ⬜ `gh auth login` → GitHub Push
2. ⬜ Vercel 部署前端（设置 `NEXT_PUBLIC_API_URL`）
3. ⬜ Railway 部署后端（设置环境变量）
4. ⬜ 画像从内存迁移到 SQLite 持久化
5. ⬜ 多用户登录系统
6. ⬜ 后台管理面板（KB 管理 + 对话日志）

---

> **当前状态**：V2 核心功能全部完成 ✅ | 16 项 TDD 测试全绿 | 代码审查通过 | Session 系统上线 | 待 GitHub 部署
