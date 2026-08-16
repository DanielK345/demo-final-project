import React, { type FormEvent, useEffect, useRef } from "react";
import { ArrowLeft, MessageCircle, RotateCcw, Send } from "lucide-react";
import { useVoiceAssistant } from "@/features/ai-assistant/context/useVoiceAssistant";

// Cửa sổ chữ độc lập với màn hình gọi: dùng chung `messages` và `sessionId`, vì vậy
// cả câu nói được nhận dạng lẫn câu gõ mới đều nối tiếp trong một cuộc hội thoại.
export const ConversationWindow: React.FC = () => {
  const {
    isConversationOpen,
    closeConversation,
    messages,
    draft,
    setDraft,
    sendText,
    newSession,
    status,
    sessionEnded,
    notice,
  } = useVoiceAssistant();
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (isConversationOpen) {
      bottomRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
    }
  }, [isConversationOpen, messages, status]);

  if (!isConversationOpen) return null;

  const submit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const value = draft.trim();
    if (!value || status === "processing" || sessionEnded) return;
    setDraft("");
    void sendText(value);
  };

  return (
    <section
      aria-label="Cuộc trò chuyện với trợ lý AloSM"
      className="absolute inset-0 z-10 flex min-h-0 flex-col bg-white dark:bg-[#12161A]"
    >
      <header className="flex shrink-0 items-center gap-3 border-b border-slate-100 px-4 py-3 dark:border-white/10">
        <button
          type="button"
          onClick={closeConversation}
          aria-label="Quay lại cuộc gọi"
          title="Quay lại cuộc gọi"
          className="grid h-9 w-9 place-items-center rounded-full text-slate-500 transition hover:bg-slate-100 hover:text-slate-800 dark:text-slate-400 dark:hover:bg-white/10 dark:hover:text-white"
        >
          <ArrowLeft className="h-5 w-5" />
        </button>
        <span className="grid h-9 w-9 place-items-center rounded-full bg-[#E9FBF8] text-[#008F88] dark:bg-[#00C9B7]/10 dark:text-[#5BE0D3]">
          <MessageCircle className="h-4 w-4" />
        </span>
        <div className="min-w-0">
          <h2 className="text-sm font-bold text-[#191C1E] dark:text-white">AloSM Assistant</h2>
          <p className="text-xs text-slate-400">Nhắn tin để tiếp tục đặt xe</p>
        </div>
        <button
          type="button"
          onClick={() => void newSession()}
          disabled={status === "processing"}
          title="Xóa cuộc trò chuyện và memory của agent"
          className="ml-auto inline-flex shrink-0 items-center gap-1.5 rounded-lg px-2.5 py-2 text-xs font-bold text-[#008F88] transition hover:bg-[#E9FBF8] disabled:cursor-not-allowed disabled:opacity-40 dark:text-[#5BE0D3] dark:hover:bg-[#00C9B7]/10"
        >
          <RotateCcw className="h-3.5 w-3.5" />
          Reset
        </button>
      </header>

      <div className="min-h-0 flex-1 overflow-y-auto px-4 py-4 [scrollbar-gutter:stable]">
        <div className="space-y-3">
          {messages.map((message) => {
            const isUser = message.role === "user";
            return (
              <div key={message.id} className={`flex ${isUser ? "justify-end" : "justify-start"}`}>
                <div
                  className={`max-w-[82%] rounded-2xl px-3.5 py-2.5 text-sm leading-relaxed shadow-sm ${
                    isUser
                      ? "rounded-br-md bg-[#00AFA4] text-white"
                      : "rounded-bl-md bg-slate-100 text-slate-700 dark:bg-white/10 dark:text-slate-100"
                  }`}
                >
                  <p className="whitespace-pre-wrap break-words">{message.text}</p>
                  {message.transcriptRewrite?.status === "rewritten" && (
                    <p className={`mt-1 text-[10px] ${isUser ? "text-white/75" : "text-slate-400"}`}>Đã hiệu chỉnh tên địa điểm</p>
                  )}
                </div>
              </div>
            );
          })}
          {status === "processing" && (
            <div className="flex justify-start">
              <div className="rounded-2xl rounded-bl-md bg-slate-100 px-3.5 py-2.5 text-sm text-slate-500 dark:bg-white/10 dark:text-slate-300">
                AloSM đang trả lời…
              </div>
            </div>
          )}
          {notice && (
            <p role="status" className="rounded-xl bg-amber-50 px-3 py-2 text-xs text-amber-700 dark:bg-amber-500/10 dark:text-amber-200">
              {notice}
            </p>
          )}
          <div ref={bottomRef} />
        </div>
      </div>

      <form onSubmit={submit} className="shrink-0 border-t border-slate-100 bg-white p-3 dark:border-white/10 dark:bg-[#12161A]">
        {sessionEnded && <p className="mb-2 text-center text-xs text-slate-500">Phiên đã kết thúc. Hãy quay lại cuộc gọi để bắt đầu phiên mới.</p>}
        <div className="flex items-end gap-2">
          <textarea
            value={draft}
            onChange={(event) => setDraft(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter" && !event.shiftKey) {
                event.preventDefault();
                event.currentTarget.form?.requestSubmit();
              }
            }}
            rows={1}
            disabled={sessionEnded}
            placeholder="Nhập tin nhắn…"
            aria-label="Tin nhắn cho AloSM"
            className="max-h-28 min-h-11 flex-1 resize-none rounded-2xl border border-slate-200 bg-slate-50 px-4 py-2.5 text-sm text-slate-800 outline-none transition placeholder:text-slate-400 focus:border-[#00C9B7] focus:bg-white disabled:cursor-not-allowed disabled:opacity-60 dark:border-white/10 dark:bg-white/5 dark:text-white dark:focus:bg-white/10"
          />
          <button
            type="submit"
            disabled={!draft.trim() || status === "processing" || sessionEnded}
            aria-label="Gửi tin nhắn"
            className="grid h-11 w-11 shrink-0 place-items-center rounded-full bg-[#00C9B7] text-white transition hover:bg-[#008F88] disabled:cursor-not-allowed disabled:opacity-40"
          >
            <Send className="h-4 w-4" />
          </button>
        </div>
      </form>
    </section>
  );
};
