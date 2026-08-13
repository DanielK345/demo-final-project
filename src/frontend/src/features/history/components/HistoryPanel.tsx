import React, { useEffect, useState } from "react";
import { History, Mic, MessageSquare, X, AlertCircle } from "lucide-react";
import { listSessionHistory, type SessionHistorySummary } from "@/features/history/api";

interface HistoryPanelProps {
  isOpen: boolean;
  onClose: () => void;
  onSelectSession: (sessionId: string) => void;
}

function formatDate(iso: string | null): string {
  if (!iso) return "";
  try {
    return new Date(iso).toLocaleString("vi-VN", {
      day: "2-digit",
      month: "2-digit",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return "";
  }
}

export const HistoryPanel: React.FC<HistoryPanelProps> = ({ isOpen, onClose, onSelectSession }) => {
  const [sessions, setSessions] = useState<SessionHistorySummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!isOpen) return;
    let cancelled = false;
    setSessions(null);
    setError(null);
    listSessionHistory()
      .then((data) => {
        if (!cancelled) setSessions(data);
      })
      .catch((cause) => {
        if (!cancelled) setError(cause instanceof Error ? cause.message : "Không thể tải lịch sử.");
      });
    return () => {
      cancelled = true;
    };
  }, [isOpen]);

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex justify-end">
      <div className="fixed inset-0 bg-black/40 dark:bg-black/60" onClick={onClose} />
      <aside className="relative z-10 w-full max-w-sm h-full bg-white border-l border-slate-200/80 flex flex-col shadow-2xl dark:bg-[#12161A] dark:border-white/10">
        <div className="flex items-center justify-between px-5 py-4 border-b border-slate-100 dark:border-white/10">
          <h2 className="text-sm font-bold text-[#191C1E] dark:text-white flex items-center gap-2">
            <History className="w-4 h-4 text-[#00D1C1]" />
            Lịch sử trò chuyện
          </h2>
          <button
            type="button"
            onClick={onClose}
            className="text-slate-400 hover:text-[#191C1E] p-1.5 rounded-full hover:bg-slate-100 transition-colors dark:text-slate-400 dark:hover:text-white dark:hover:bg-white/10"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto px-3 py-3 space-y-2">
          {error && (
            <p className="flex items-center gap-2 text-xs text-rose-700 bg-rose-50 border border-rose-200 rounded-xl p-3 dark:text-rose-300 dark:bg-rose-500/10 dark:border-rose-500/30">
              <AlertCircle className="w-4 h-4 shrink-0" />
              {error}
            </p>
          )}

          {sessions === null && !error && (
            <p className="text-xs text-slate-500 dark:text-slate-400 text-center py-8">Đang tải...</p>
          )}

          {sessions !== null && sessions.length === 0 && (
            <p className="text-xs text-slate-500 dark:text-slate-400 text-center py-8">Chưa có cuộc trò chuyện nào.</p>
          )}

          {sessions?.map((session) => (
            <button
              key={session.session_id}
              type="button"
              onClick={() => onSelectSession(session.session_id)}
              className="w-full text-left rounded-xl bg-slate-50 hover:bg-slate-100 border border-slate-200/80 hover:border-[#00D1C1]/40 p-3.5 transition-colors dark:bg-white/5 dark:hover:bg-white/10 dark:border-white/10"
            >
              <div className="flex items-center justify-between mb-1.5">
                <span className="flex items-center gap-1.5 text-[10px] font-bold uppercase tracking-wider text-[#006a62] dark:text-[#00D1C1]">
                  {session.channel === "WEB_VOICE" ? <Mic className="w-3 h-3" /> : <MessageSquare className="w-3 h-3" />}
                  {session.channel === "WEB_VOICE" ? "Giọng nói" : "Nhắn tin"}
                </span>
                <span className="text-[10px] text-slate-400 dark:text-slate-500">{formatDate(session.created_at)}</span>
              </div>
              <p className="text-xs text-slate-700 dark:text-slate-200 line-clamp-2">{session.preview || "(không có nội dung)"}</p>
              <p className="text-[10px] text-slate-400 dark:text-slate-500 mt-1">{session.message_count} tin nhắn</p>
            </button>
          ))}
        </div>
      </aside>
    </div>
  );
};
