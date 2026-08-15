import React, { useEffect, useRef, useState } from "react";
import { Bot, History, Mic, RotateCcw, Send } from "lucide-react";
import { useVoiceAssistant } from "@/features/ai-assistant/context/useVoiceAssistant";
import { LlmStatusNote } from "@/features/ai-assistant/components/LlmStatusNote";
import { BookingProgressStrip } from "@/features/ai-assistant/components/BookingProgressStrip";

const QUICK_CHIPS = ["Đặt xe ra sân bay", "Theo dõi chuyến đi của tôi", "Chính sách huỷ chuyến như thế nào?"];

// Mode A — Chat/Text (mục 4): bong bóng tin nhắn, tự cuộn xuống cuối, KHÔNG hiển thị
// JSON/tool-call/confidence — chỉ nội dung hội thoại thật.
export const VoiceChatPanel: React.FC = () => {
  const {
    messages,
    status,
    notice,
    sendText,
    sessionEnded,
    sessionId,
    newSession,
    setMode,
    openHistory,
    bookingProgress,
  } = useVoiceAssistant();
  const [text, setText] = useState("");
  const listEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    listEndRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages.length, status]);

  const disabled = !sessionId || status === "processing" || sessionEnded;

  const handleSubmit = (event: React.FormEvent) => {
    event.preventDefault();
    if (!text.trim()) return;
    void sendText(text);
    setText("");
  };

  return (
    <div className="flex flex-col h-full">
      {/* Header phụ trong popup: lịch sử + trạng thái LLM rút gọn (chỉ 1 badge nhỏ,
          không phải màn hình debug — mục 14) */}
      <div className="flex items-center justify-between px-4 py-2.5 border-b border-slate-100 dark:border-white/10 shrink-0">
        <LlmStatusNote compact />
        <button
          type="button"
          onClick={openHistory}
          className="flex items-center gap-1.5 text-xs font-semibold text-slate-500 hover:text-[#006a62] px-2.5 py-1.5 rounded-full hover:bg-slate-100 transition-colors dark:text-slate-400 dark:hover:text-[#00D1C1] dark:hover:bg-white/10"
        >
          <History className="w-3.5 h-3.5" />
          Lịch sử
        </button>
      </div>

      <BookingProgressStrip progress={bookingProgress} />

      <div className="flex-1 overflow-y-auto px-4 py-4 space-y-3" aria-live="polite">
        {messages.map((message) => (
          <div key={message.id} className={`flex gap-2.5 ${message.role === "user" ? "justify-end" : "justify-start"}`}>
            {message.role === "assistant" && (
              <span className="mt-0.5 w-7 h-7 shrink-0 rounded-full bg-[#00D1C1]/15 text-[#006a62] dark:text-[#00D1C1] grid place-items-center">
                <Bot className="w-3.5 h-3.5" />
              </span>
            )}
            <p
              className={`max-w-[78%] rounded-2xl px-3.5 py-2.5 text-sm leading-6 ${
                message.role === "user"
                  ? "bg-[#00D1C1] text-[#0B0E11] font-medium rounded-tr-sm"
                  : "bg-slate-100 text-slate-700 rounded-tl-sm dark:bg-white/10 dark:text-slate-100"
              }`}
            >
              {message.text}
            </p>
          </div>
        ))}
        {status === "processing" && (
          <p className="text-xs text-slate-500 dark:text-slate-400 animate-pulse pl-9">AloSM đang xử lý…</p>
        )}
        <div ref={listEndRef} />
      </div>

      {notice && (
        <p className="mx-4 mb-2 text-xs bg-amber-50 text-amber-800 border border-amber-200 rounded-xl p-2.5 dark:bg-amber-500/10 dark:text-amber-300 dark:border-amber-500/30">
          {notice}
        </p>
      )}

      <div className="shrink-0 border-t border-slate-100 dark:border-white/10 p-3">
        {sessionEnded ? (
          <button
            type="button"
            onClick={() => void newSession()}
            className="w-full flex items-center justify-center gap-2 rounded-xl bg-[#00D1C1] px-4 py-2.5 text-sm font-semibold text-[#0B0E11] hover:opacity-90"
          >
            <RotateCcw className="w-4 h-4" />
            Bắt đầu phiên mới
          </button>
        ) : (
          <>
            <div className="flex gap-1.5 mb-2 overflow-x-auto pb-0.5">
              {QUICK_CHIPS.map((chip) => (
                <button
                  key={chip}
                  type="button"
                  onClick={() => void sendText(chip)}
                  disabled={disabled}
                  className="shrink-0 text-[11px] bg-slate-100 text-slate-700 rounded-full px-3 py-1.5 hover:bg-slate-200 disabled:opacity-50 dark:bg-white/10 dark:text-slate-200 dark:hover:bg-white/20"
                >
                  {chip}
                </button>
              ))}
            </div>
            <form onSubmit={handleSubmit} className="flex items-center gap-2">
              <input
                value={text}
                onChange={(event) => setText(event.target.value)}
                disabled={disabled}
                className="flex-1 rounded-xl bg-slate-50 border border-slate-200 text-[#191C1E] placeholder:text-slate-400 px-3.5 py-2.5 text-sm outline-none focus:ring-2 focus:ring-[#00D1C1] disabled:opacity-60 dark:bg-white/5 dark:border-white/10 dark:text-white dark:placeholder:text-slate-500"
                placeholder={sessionId ? "Nhập điểm đón và điểm đến…" : "Đang kết nối phiên…"}
                aria-label="Nhập nội dung"
              />
              <button
                type="button"
                onClick={() => setMode("call")}
                disabled={!sessionId || sessionEnded}
                aria-label="Chuyển sang gọi thoại"
                title="Gọi thoại với AI"
                className="w-10 h-10 shrink-0 rounded-xl bg-slate-100 text-slate-600 grid place-items-center hover:bg-slate-200 disabled:opacity-50 dark:bg-white/10 dark:text-slate-300 dark:hover:bg-white/20"
              >
                <Mic className="w-4 h-4" />
              </button>
              <button
                type="submit"
                disabled={!text.trim() || disabled}
                aria-label="Gửi"
                className="w-10 h-10 shrink-0 rounded-xl bg-[#00D1C1] text-[#0B0E11] grid place-items-center disabled:opacity-50"
              >
                <Send className="w-4 h-4" />
              </button>
            </form>
          </>
        )}
      </div>
    </div>
  );
};
