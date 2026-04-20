"use client";

import { useState, useEffect, useCallback, memo, useRef } from "react";
import useSWR, { mutate } from "swr";
import { IconPlay, IconSettings, IconBack } from "@/ui/icons";
import { API } from "@/core/lib/api";

interface Comment {
  id: number;
  user_id: string;
  username: string;
  avatar?: string;
  text: string;
  timestamp_sec: number | null;
  created_at: string;
  reactions: number;
  reply_count: number;
  parent_id: number | null;
  is_liked?: boolean;
}

interface Props {
  anilistId: string;
  episode: string;
  currentTime: number;
  onSeek: (time: number) => void;
  user?: { id: string; name: string; image?: string | null } | null;
}

const IconClose = () => (
  <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" strokeWidth="2.5"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg>
);
const IconHeart = ({ filled }: { filled?: boolean }) => (
  <svg viewBox="0 0 24 24" width="16" height="16" fill={filled ? "#FF2D55" : "none"} stroke={filled ? "#FF2D55" : "currentColor"} strokeWidth="2.5"><path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z"></path></svg>
);

const fetcher = (url: string) => fetch(url).then(res => res.json());

export function CommentSection({ anilistId, episode, currentTime, onSeek, user }: Props) {
  const [sortBy, setSortBy] = useState<"top" | "newest">("top");
  const [isMainModalOpen, setIsMainModalOpen] = useState(false);
  const [activeThread, setActiveThread] = useState<Comment | null>(null);
  const [mounted, setMounted] = useState(false);

  const userId = user?.id;

  // Use SWR for real-time sync (auto-revalidate every 15s)
  const { data: allComments = [], isLoading } = useSWR(
    `${API}/api/v2/comments?anilistId=${anilistId}&episodeNumber=${episode}&sort_by=${sortBy}`,
    fetcher,
    { refreshInterval: 15000, revalidateOnFocus: true }
  );

  useEffect(() => { setMounted(true); }, []);

  const comments = Array.isArray(allComments) ? allComments.filter((c: any) => !c.parent_id) : [];

  const handleSubmit = async (text: string, parentId?: number) => {
    if (!text.trim() || !userId) return;
    try {
      const res = await fetch(`${API}/api/v2/comments`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ user_id: userId, anilistId: parseInt(anilistId), episodeNumber: parseFloat(episode), text, parent_id: parentId, timestamp_sec: parentId ? null : Math.floor(currentTime) })
      });
      if (res.ok) {
        mutate(`${API}/api/v2/comments?anilistId=${anilistId}&episodeNumber=${episode}&sort_by=${sortBy}${userId ? `&user_id=${userId}` : ''}`);
        if (parentId) mutate(`${API}/api/v2/comments?anilistId=${anilistId}&episodeNumber=${episode}&parent_id=${parentId}&sort_by=newest${userId ? `&user_id=${userId}` : ''}`);
      }
    } catch (e) {}
  };

  const handleLike = async (commentId: number) => {
    if (!userId) {
      alert("Silakan login untuk menyukai komentar.");
      return;
    }
    try {
      await fetch(`${API}/api/v2/comments/reaction`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ comment_id: commentId, user_id: userId, emoji: "🔥" })
      });
      mutate(`${API}/api/v2/comments?anilistId=${anilistId}&episodeNumber=${episode}&sort_by=${sortBy}`);
    } catch (e) {}
  };

  if (!mounted) return null;

  const SortTabs = () => (
    <div className="flex gap-2 bg-white/5 p-1 rounded-full border border-white/5 w-fit">
      {["top", "newest"].map(s => (
        <button key={s} onClick={() => setSortBy(s as any)} className={`px-4 py-1.5 rounded-full text-[10px] font-black uppercase tracking-wider transition-all ${sortBy === s ? 'bg-white text-black shadow-lg' : 'text-[#8e8e93] hover:text-white'}`}>
          {s === "top" ? "Populer" : "Terbaru"}
        </button>
      ))}
    </div>
  );

  return (
    <div className="w-full">
      <style jsx global>{`
        @keyframes slideUp { from { transform: translateY(100%); } to { transform: translateY(0); } }
        .anim-slide-up { animation: slideUp 0.3s cubic-bezier(0.32, 0.72, 0, 1); }
      `}</style>

      {/* Preview area */}
      <div className="md:hidden bg-[#1c1c1e] rounded-2xl p-4 mb-6 cursor-pointer border border-white/5" onClick={() => setIsMainModalOpen(true)}>
        <div className="flex items-center justify-between mb-3">
          <span className="text-white font-black text-sm">Komentar <span className="text-[#8e8e93] ml-1">{comments.length}</span></span>
          <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="#8e8e93" strokeWidth="2.5"><path d="M7 13l5 5 5-5M7 6l5 5 5-5"></path></svg>
        </div>
        {comments.length > 0 ? (
          <div className="flex gap-3 items-center">
            <div className="w-6 h-6 rounded-full bg-[#3a3a3c] flex items-center justify-center text-[10px] font-black shrink-0 text-white border border-white/10">{(comments[0].username || "U").charAt(0).toUpperCase()}</div>
            <p className="text-[#e5e5ea] text-xs line-clamp-1">{comments[0].text}</p>
          </div>
        ) : <p className="text-[#8e8e93] text-xs font-medium">Mulai diskusi...</p>}
      </div>

      {/* Desktop view */}
      <div className="hidden md:block space-y-8">
        <div className="flex items-center justify-between">
          <h3 className="text-xl font-black text-white">{comments.length} Komentar</h3>
          <SortTabs />
        </div>
        <CommentComposer userId={userId} onSubmit={handleSubmit} />
        <div className="space-y-1">
          {comments.map(c => <CommentItem key={c.id} comment={c} onReply={() => setActiveThread(c)} onLike={() => handleLike(c.id)} onSeek={onSeek} userId={userId} />)}
        </div>
      </div>

      {/* Main Modal Layer */}
      {isMainModalOpen && (
        <div className="fixed top-[56.25vw] bottom-0 left-0 right-0 z-[200] md:hidden flex flex-col bg-black anim-slide-up border-t border-white/10">
          <div className="h-14 flex items-center justify-between px-4 border-b border-white/10 shrink-0">
            <div className="flex items-center gap-4"><span className="text-white font-black text-sm">Komentar</span><SortTabs /></div>
            <button onClick={() => setIsMainModalOpen(false)} className="p-2 text-[#8e8e93]"><IconClose /></button>
          </div>
          <div className="flex-1 overflow-y-auto p-4 no-scrollbar space-y-1">
            {comments.map(c => <CommentItem key={c.id} comment={c} onReply={() => setActiveThread(c)} onLike={() => handleLike(c.id)} onSeek={onSeek} userId={userId} />)}
          </div>
          <div className="p-3 border-t border-white/10 bg-[#1c1c1e]">
            <CommentComposer userId={userId} compact onSubmit={handleSubmit} />
          </div>
        </div>
      )}

      {/* Thread Modal Layer */}
      {activeThread && (() => {
        const currentActiveThread = Array.isArray(allComments) ? allComments.find((c: any) => c.id === activeThread.id) || activeThread : activeThread;
        return (
          <div className="fixed top-[56.25vw] bottom-0 left-0 right-0 z-[300] flex flex-col bg-black md:bg-black/80 md:backdrop-blur-xl anim-slide-up md:top-0">
            <div className="h-14 flex items-center px-4 gap-4 border-b border-white/10 md:max-w-2xl md:mx-auto md:w-full bg-black shrink-0">
              <button onClick={() => setActiveThread(null)} className="p-2 text-white"><IconBack /></button>
              <div className="flex flex-col"><span className="text-white font-black text-sm">Balasan</span><span className="text-[10px] text-[#8e8e93] font-bold">ke @{currentActiveThread.username}</span></div>
            </div>
            <div className="flex-1 overflow-y-auto no-scrollbar md:max-w-2xl md:mx-auto md:w-full bg-black">
              <div className="p-4 bg-white/[0.03] border-b border-white/5">
                <CommentItem comment={currentActiveThread} hideActions onSeek={onSeek} userId={userId} />
              </div>
              <ThreadList replies={currentActiveThread.replies || []} userId={userId} onLike={handleLike} />
            </div>
            <div className="p-3 border-t border-white/10 bg-[#1c1c1e] md:max-w-2xl md:mx-auto md:w-full shrink-0">
              <CommentComposer userId={userId} autoFocus placeholder={`Balas @${currentActiveThread.username}...`} onSubmit={(t: string) => handleSubmit(t, currentActiveThread.id)} />
            </div>
          </div>
        );
      })()}
    </div>
  );
}

const CommentItem = ({ comment: c, onReply, onLike, onSeek, hideActions, userId }: any) => {
  const isMe = c.user_id === userId;
  return (
    <div className="py-4 flex gap-3 group">
      <div className="w-9 h-9 rounded-full bg-[#2c2c2e] flex items-center justify-center text-xs font-black text-white shrink-0 shadow-md border border-white/10 overflow-hidden">
        {c.avatar ? <img src={c.avatar} className="w-full h-full object-cover" /> : (c.username || "U").charAt(0).toUpperCase()}
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 mb-0.5">
          <span className={`text-white font-bold text-[13px] truncate ${isMe ? 'text-[#0a84ff]' : ''}`}>@{c.username.toLowerCase()}</span>
          <span className="text-[#8e8e93] text-[10px] shrink-0">{new Date(c.created_at).toLocaleDateString()}</span>
          {c.timestamp_sec != null && (
            <button onClick={() => onSeek(c.timestamp_sec)} className="text-[#0a84ff] text-[10px] font-black bg-[#0a84ff]/10 px-1.5 rounded shrink-0">
              {Math.floor(c.timestamp_sec / 60)}:{(c.timestamp_sec % 60).toString().padStart(2, "0")}
            </button>
          )}
        </div>
        <p className="text-[#e5e5ea] text-sm leading-relaxed break-words">{c.text}</p>
        {!hideActions && (
          <div className="flex items-center gap-6 mt-3">
            <button onClick={onLike} className={`flex items-center gap-1.5 transition-all active:scale-125 ${c.reactions > 0 ? 'text-[#ff2d55]' : 'text-[#8e8e93] hover:text-white'}`}>
              <IconHeart filled={c.reactions > 0} />
              <span className="text-[11px] font-bold tabular-nums">{c.reactions || ''}</span>
            </button>
            <button onClick={onReply} className="text-[#0a84ff] text-[11px] font-black hover:underline transition-colors flex items-center gap-1.5">
               {c.reply_count > 0 ? <><span className="w-4 h-[1.5px] bg-[#0a84ff]/50" /> {c.reply_count} Balasan</> : 'Balas'}
            </button>
          </div>
        )}
      </div>
    </div>
  );
};

const CommentComposer = ({ userId, onSubmit, compact, autoFocus, placeholder }: any) => {
  const [text, setText] = useState("");
  const inputRef = useRef<HTMLTextAreaElement>(null);
  useEffect(() => { if (autoFocus) inputRef.current?.focus(); }, [autoFocus]);

  const handleSend = () => { if (!text.trim()) return; onSubmit(text); setText(""); };

  return (
    <div className={`flex gap-3 items-start`}>
      <div className="w-8 h-8 rounded-full bg-gradient-to-tr from-[#0a84ff] to-[#5e5ce6] flex items-center justify-center text-[10px] font-black shrink-0 text-white border border-white/20">
        {userId ? userId.charAt(5).toUpperCase() : "?"}
      </div>
      <div className="flex-1 relative">
        <textarea ref={inputRef} value={text} onChange={(e) => setText(e.target.value)} placeholder={placeholder || "Tambahkan komentar..."} rows={compact ? 1 : 2} className="w-full bg-[#2c2c2e]/50 text-white text-sm p-3 rounded-2xl border border-white/10 focus:outline-none focus:border-[#0a84ff]/50 transition-all resize-none no-scrollbar" onKeyDown={(e) => { if (e.key === 'Enter' && !e.shiftKey && text.trim()) { e.preventDefault(); handleSend(); } }} />
        {text.trim() && <button onClick={handleSend} className="absolute right-3 bottom-3 text-[#0a84ff] font-black text-xs uppercase tracking-widest">Kirim</button>}
      </div>
    </div>
  );
};

const ThreadList = ({ replies = [], userId, onLike }: any) => {
  return (
    <div className="p-4 space-y-1 border-l border-white/5 ml-6">
      {replies.length === 0 && <p className="text-[#8e8e93] text-xs py-4 italic">Belum ada balasan.</p>}
      {replies.map((r: any) => <CommentItem key={r.id} comment={r} hideActions userId={userId} onLike={() => onLike(r.id)} />)}
    </div>
  );
};
