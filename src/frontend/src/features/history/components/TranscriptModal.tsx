import React, { useEffect, useState } from "react";
import { Bot, User, X, AlertCircle } from "lucide-react";
import { getSessionTranscript, type SessionTranscript } from "@/features/history/api";

interface TranscriptModalProps {
  sessionId: string | null;
  onClose: () => void;
}

function formatTime(iso: string): string {
  try {
    return new Date(iso).toLocaleTimeString("vi-VN", { hour: "2-digit", minute: "2-digit" });
  } catch {
    return "";
  }
}

export const TranscriptModal: React.FC<TranscriptModalProps> = ({ sessionId, onClose }) => {
  const [transcript, setTranscript] = useState<SessionTranscript | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!sessionId) return;
    let cancelled = false;
    setTranscript(null);
    setError(null);
    getSessionTranscript(sessionId)
      .then((data) => {
        if (!cancelled) setTranscript(data);
      })
      .catch((cause) => {
        if (!cancelled) setError(cause instanceof Error ? cause.message : "Không thể tải cuộc trò chuyện.");
      });
    return () => {
      cancelled = true;
    };
  }, [sessionId]);

  if (!sessionId) return null;

  return (
    <div className="fixed inset-0 z-[60] flex items-center justify-center p-4">
      <div className="fixed inset-0 bg-black/50 dark:bg-black/70" onClick={onClose} />
      <div className="relative z-10 w-full max-w-lg max-h-[85vh] bg-white border border-slate-200/80 rounded-2xl shadow-2xl flex flex-col overflow-hidden dark:bg-[#12161A] dark:border-white/10">
        <div className="flex items-center justify-between px-5 py-4 border-b border-slate-100 dark:border-white/10 shrink-0">
          <h2 className="text-sm font-bold text-[#191C1E] dark:text-white">Nội dung cuộc trò chuyện</h2>
          <button
            type="button"
            onClick={onClose}
            className="text-slate-400 hover:text-[#191C1E] p-1.5 rounded-full hover:bg-slate-100 transition-colors dark:text-slate-400 dark:hover:text-white dark:hover:bg-white/10"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto px-5 py-4 space-y-4">
          {error && (
            <p className="flex items-center gap-2 text-xs text-rose-700 bg-rose-50 border border-rose-200 rounded-xl p-3 dark:text-rose-300 dark:bg-rose-500/10 dark:border-rose-500/30">
              <AlertCircle className="w-4 h-4 shrink-0" />
              {error}
            </p>
          )}

          {!transcript && !error && (
            <p className="text-xs text-slate-500 dark:text-slate-400 text-center py-8">Đang tải...</p>
          )}

          {transcript?.messages.map((message, index) => (
            <div
              key={index}
              className={`flex gap-2.5 ${message.role === "user" ? "justify-end" : "justify-start"}`}
            >
              {message.role === "agent" && (
                <span className="mt-1 w-7 h-7 shrink-0 rounded-full bg-[#00D1C1]/15 text-[#006a62] dark:text-[#00D1C1] grid place-items-center">
                  <Bot className="w-3.5 h-3.5" />
                </span>
              )}
              <div className={`max-w-[78%] ${message.role === "user" ? "items-end" : "items-start"} flex flex-col`}>
                <p
                  className={`rounded-2xl px-4 py-2.5 text-sm leading-6 ${
                    message.role === "user"
                      ? "bg-[#00D1C1] text-[#0B0E11] rounded-tr-sm font-medium"
                      : "bg-slate-100 text-slate-700 rounded-tl-sm dark:bg-white/10 dark:text-slate-100"
                  }`}
                >
                  {message.text}
                </p>
                <span className="text-[10px] text-slate-400 dark:text-slate-500 mt-1 px-1">{formatTime(message.timestamp)}</span>
              </div>
              {message.role === "user" && (
                <span className="mt-1 w-7 h-7 shrink-0 rounded-full bg-slate-100 text-slate-500 dark:bg-white/10 dark:text-slate-300 grid place-items-center">
                  <User className="w-3.5 h-3.5" />
                </span>
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};
