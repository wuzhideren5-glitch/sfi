"use client";
import { useState, useRef, useEffect } from "react";

interface Message {
  role: "ai" | "user";
  content: string;
}

interface Profile {
  name: string;
  gender: string;
  age: number | null;
  city: string;
  education: { school: string; degree: string; major: string; year: string }[];
  internships: { company: string; role: string; duration: string; description: string }[];
  skills: string[];
  certificates: string[];
  target_industry: string[];
  target_role: string[];
  gaps: string[];
}

const defaultProfile: Profile = {
  name: "", gender: "", age: null, city: "",
  education: [], internships: [], skills: [], certificates: [],
  target_industry: [], target_role: [], gaps: [],
};

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export default function Home() {
  const [profile, setProfile] = useState<Profile>(defaultProfile);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [messages, setMessages] = useState<Message[]>([
    {
      role: "ai",
      content: "你好！我是深高金CDC的小苗老师 🎓\n\n在职业发展中心工作了十多年，辅导过很多像你一样的同学。\n\n上传简历让我了解你的背景，或者直接告诉我你想聊什么方向——投行、行研、咨询、审计，都可以。",
    },
  ]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [memories, setMemories] = useState(0);
  const msgEnd = useRef<HTMLDivElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => { msgEnd.current?.scrollIntoView({ behavior: "smooth" }); }, [messages]);

  const handleUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploading(true);
    const formData = new FormData();
    formData.append("file", file);
    try {
      const res = await fetch(`${API_BASE}/api/parse/resume`, { method: "POST", body: formData });
      const data = await res.json();
      if (data.status === "ok" && data.profile) {
        setProfile(data.profile);
        const name = data.profile.name || "同学";
        const industry = data.profile.target_industry?.join("、") || "未设置";
        setMessages((prev) => [
          ...prev,
          { role: "ai", content: `${name}你好！简历已解析 👋\n\n目标方向：${industry}\n实习：${data.profile.internships?.map((i:any) => i.company).join("、") || "暂无"}\n\n接下来想聊什么？投行、咨询、审计、还是其他方向？` },
        ]);
        setSidebarOpen(false);
      } else {
        setMessages((prev) => [...prev, { role: "ai", content: `⚠️ ${data.error || "解析失败，请重试"}` }]);
      }
    } catch {
      setMessages((prev) => [...prev, { role: "ai", content: "⚠️ 上传失败，请确认后端已启动" }]);
    }
    setUploading(false);
    if (fileInputRef.current) fileInputRef.current.value = "";
  };

  const send = async (text: string) => {
    if (!text.trim() || loading) return;
    const userMsg: Message = { role: "user", content: text };
    const loadingMsg: Message = { role: "ai", content: "" };
    setMessages((prev) => [...prev, userMsg, loadingMsg]);
    setInput("");
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/api/chat/send`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: text, history: [] }),
      });
      const data = await res.json();
      setMessages((prev) => {
        const updated = [...prev];
        updated[updated.length - 1] = { role: "ai", content: data.reply || "出了点问题" };
        return updated;
      });
      if (data.profile?.target_industry?.length || data.profile?.target_role?.length) {
        setProfile((p) => ({
          ...p,
          target_industry: data.profile.target_industry || p.target_industry,
          target_role: data.profile.target_role || p.target_role,
        }));
      }
      setMemories(data.personal_memories || 0);
    } catch {
      setMessages((prev) => {
        const updated = [...prev];
        updated[updated.length - 1] = { role: "ai", content: "⚠️ 后端服务未连接" };
        return updated;
      });
    }
    setLoading(false);
  };

  const SidebarContent = () => (
    <>
      {/* Logo area — enlarged */}
      <div className="p-4 border-b border-[#E8E0F0] flex items-center gap-3">
        <img src="/sfi-logo.jpg" alt="深高金" className="h-10 w-auto object-contain" />
        <div className="w-px h-6 bg-[#C8962E]/40" />
        <img src="/career-center-logo.jpg" alt="职业发展中心" className="h-9 w-auto object-contain" />
      </div>

      {/* Student card */}
      <div className="p-4 flex gap-3 items-center border-b border-[#E8E0F0]">
        <div className="w-12 h-12 rounded-full bg-gradient-to-br from-[#8B5CAA] to-[#6B2D8E] text-white text-lg flex items-center justify-center shrink-0 shadow-md">
          {profile.name?.[0] || "?"}
        </div>
        <div className="min-w-0">
          <div className="font-bold text-sm truncate">{profile.name || "未上传简历"}</div>
          {profile.name && <div className="text-[10px] text-[#6B6080]">{profile.gender} · {profile.age || "?"}岁 · {profile.city}</div>}
          <span className="text-[9px] bg-[#F7F2FA] text-[#6B2D8E] px-1.5 py-0.5 rounded-full mt-0.5 inline-block">
            {profile.education?.[0]?.major || profile.education?.[0]?.school || "未解析"}
          </span>
        </div>
      </div>

      {/* Scrollable profile details */}
      <div className="flex-1 overflow-y-auto p-4 space-y-3 text-xs">
        {profile.education?.length > 0 && (
          <Section label="教育">
            {profile.education.map((e, i) => (
              <div key={i} className="text-[11px] leading-snug">{e.school}<br/>{e.major} {e.degree} {e.year}</div>
            ))}
          </Section>
        )}
        {profile.internships?.length > 0 && (
          <Section label="实习">
            {profile.internships.map((i, j) => (
              <div key={j} className="text-[11px] leading-snug"><strong>{i.company}</strong> {i.role}<span className="text-[#6B6080] text-[10px] block">{i.duration}</span></div>
            ))}
          </Section>
        )}
        {(profile.skills?.length > 0 || profile.certificates?.length > 0) && (
          <Section label="技能 & 证书">
            <Tags items={profile.skills || []} color="purple" />
            <Tags items={profile.certificates || []} color="gold" />
          </Section>
        )}
        <Section label="求职目标">
          {(profile.target_industry || []).map((t, i) => (
            <span key={i} className="text-[10px] font-semibold px-2 py-0.5 rounded bg-[#6B2D8E] text-white mr-1">{t}</span>
          ))}
          {(profile.target_role || []).map((t, i) => (
            <span key={i} className="text-[10px] px-2 py-0.5 rounded bg-[#F5E6C8] text-[#8B6914] mr-1">{t}</span>
          ))}
          {(!profile.target_industry?.length && !profile.target_role?.length) && (
            <span className="text-[#6B6080] text-[10px]">聊天中自动提取</span>
          )}
        </Section>
        {profile.gaps?.length > 0 && (
          <Section label="待提升">
            {profile.gaps.map((g, i) => <div key={i} className="text-[10px] text-[#6B6080]">⚠ {g}</div>)}
          </Section>
        )}
      </div>

      {/* Upload + memory count */}
      <div className="p-4 border-t border-[#E8E0F0] space-y-2">
        <input ref={fileInputRef} type="file" accept=".pdf" onChange={handleUpload} className="hidden" />
        <button
          onClick={() => fileInputRef.current?.click()}
          disabled={uploading}
          className="w-full px-3 py-2.5 border-2 border-dashed border-[#8B5CAA] bg-[#F7F2FA] text-[#6B2D8E] rounded-lg text-xs font-semibold hover:bg-[#6B2D8E] hover:text-white transition-all flex items-center justify-center gap-1 disabled:opacity-50"
        >
          {uploading ? "⏳ 解析中..." : <><UploadIcon /> 上传简历</>}
        </button>
        {memories > 0 && (
          <div className="text-[10px] text-[#6B6080] text-center">🧠 已记忆 {memories} 轮对话</div>
        )}
      </div>
    </>
  );

  return (
    <div className="flex h-screen bg-[#FAF8FC] font-sans text-[#1a1a2e]">
      {/* Desktop Sidebar */}
      <aside className="hidden md:flex w-[280px] min-w-[280px] bg-white border-r border-[#E8E0F0] flex-col">
        <SidebarContent />
      </aside>

      {/* Mobile Sidebar Overlay */}
      {sidebarOpen && (
        <div className="md:hidden fixed inset-0 z-50 flex">
          <div className="absolute inset-0 bg-black/40" onClick={() => setSidebarOpen(false)} />
          <aside className="relative w-[280px] bg-white h-full flex flex-col shadow-xl animate-slide-in">
            <SidebarContent />
          </aside>
        </div>
      )}

      {/* Chat Area */}
      <main className="flex-1 flex flex-col min-w-0">
        <header className="px-3 md:px-4 py-3 border-b border-[#E8E0F0] bg-white flex items-center gap-2">
          {/* Mobile hamburger */}
          <button
            className="md:hidden w-8 h-8 rounded-lg bg-[#F7F2FA] flex items-center justify-center mr-1"
            onClick={() => setSidebarOpen(true)}
          >
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#6B2D8E" strokeWidth="2.5">
              <line x1="3" y1="6" x2="21" y2="6"/><line x1="3" y1="12" x2="21" y2="12"/><line x1="3" y1="18" x2="21" y2="18"/>
            </svg>
          </button>
          <div className="w-7 h-7 rounded-full bg-gradient-to-br from-[#6B2D8E] to-[#C8962E] flex items-center justify-center text-sm">🎓</div>
          <div><div className="font-semibold text-sm md:text-xs">小苗老师</div><div className="text-[10px] text-[#6B6080]">CDC资深导师 · 在线</div></div>
        </header>

        <div className="flex-1 overflow-y-auto px-3 md:px-4 py-3 space-y-3 bg-gradient-to-b from-[#FAF8FC] to-[#F3EFF7]">
          {messages.map((msg, i) => (
            <div key={i} className={`flex gap-2 ${msg.role === "user" ? "justify-end" : "justify-start"}`}>
              {msg.role === "ai" && (
                <div className="w-6 h-6 rounded-full bg-gradient-to-br from-[#6B2D8E] to-[#C8962E] text-white flex items-center justify-center text-[10px] shrink-0 mt-0.5">🎓</div>
              )}
              <div className={`px-3 py-2 rounded-2xl text-[13px] leading-relaxed max-w-[85%] md:max-w-[80%] ${
                msg.role === "user"
                  ? "bg-[#6B2D8E] text-white rounded-tr-sm"
                  : "bg-white border border-[#E8E0F0] rounded-tl-sm"
              }`}>
                {msg.content ? (
                  <div className="whitespace-pre-line">{msg.content}</div>
                ) : (
                  <div className="flex gap-1 py-1">
                    <span className="w-1.5 h-1.5 rounded-full bg-[#C8962E] animate-bounce" />
                    <span className="w-1.5 h-1.5 rounded-full bg-[#C8962E] animate-bounce" style={{ animationDelay: "0.1s" }} />
                    <span className="w-1.5 h-1.5 rounded-full bg-[#C8962E] animate-bounce" style={{ animationDelay: "0.2s" }} />
                  </div>
                )}
              </div>
              {msg.role === "user" && (
                <div className="w-6 h-6 rounded-full bg-[#F7F2FA] text-[#6B2D8E] flex items-center justify-center text-[10px] font-bold shrink-0 mt-0.5">
                  {profile.name?.[0] || "?"}
                </div>
              )}
            </div>
          ))}
          <div ref={msgEnd} />
        </div>

        <div className="px-3 md:px-4 py-3 bg-white border-t border-[#E8E0F0]">
          <div className="flex gap-2 items-end">
            <textarea
              className="flex-1 border-2 border-[#E8E0F0] rounded-xl px-3 py-2 text-[14px] md:text-[13px] resize-none outline-none bg-[#FAF8FC] focus:border-[#6B2D8E] max-h-[100px] font-sans"
              rows={1}
              placeholder="输入你的问题..."
              value={input}
              onChange={(e) => { setInput(e.target.value); e.target.style.height = "auto"; e.target.style.height = Math.min(e.target.scrollHeight, 100) + "px"; }}
              onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(input); } }}
            />
            <button
              className="w-10 h-10 rounded-full bg-[#6B2D8E] text-white flex items-center justify-center hover:bg-[#8B5CAA] transition-all shrink-0 shadow-md"
              onClick={() => send(input)}
            >
              <SendIcon />
            </button>
          </div>
        </div>
      </main>
    </div>
  );
}

function Section({ label, children }: { label: string; children?: React.ReactNode }) {
  return (
    <div>
      <div className="text-[9px] uppercase tracking-wider text-[#6B6080] font-semibold mb-0.5">{label}</div>
      {children}
    </div>
  );
}

function Tags({ items, color }: { items: string[]; color: "purple" | "gold" }) {
  const cls = color === "purple" ? "bg-[#F7F2FA] text-[#6B2D8E]" : "bg-[#F5E6C8] text-[#8B6914]";
  return <div className="flex flex-wrap gap-1 mt-0.5">{(items || []).map((t) => <span key={t} className={`text-[10px] px-1.5 py-0.5 rounded font-medium ${cls}`}>{t}</span>)}</div>;
}

function UploadIcon() {
  return <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/></svg>;
}

function SendIcon() {
  return <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><line x1="22" y1="2" x2="11" y2="13"/><polygon points="22 2 15 22 11 13 2 9"/></svg>;
}
