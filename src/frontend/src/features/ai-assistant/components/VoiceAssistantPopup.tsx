import React from "react";
import { MessageCircle, Phone, X } from "lucide-react";
import { useVoiceAssistant } from "@/features/ai-assistant/context/useVoiceAssistant";
import { VoiceChatPanel } from "@/features/ai-assistant/components/VoiceChatPanel";
import { VoiceCallPanel } from "@/features/ai-assistant/components/VoiceCallPanel";
import { BookingConfirmationModal } from "@/features/ai-assistant/components/BookingConfirmationModal";
import { BookingSuccessModal } from "@/features/ai-assistant/components/BookingSuccessModal";
import { HistoryPanel } from "@/features/history/components/HistoryPanel";
import { TranscriptModal } from "@/features/history/components/TranscriptModal";

// Popup nổi (mục 3) — KHÔNG phải trang riêng. Desktop: cửa sổ nhỏ nổi góc dưới phải.
// Mobile: bottom sheet trượt lên từ đáy màn hình, không chiếm toàn bộ chiều cao (mục
// 17 — responsive, không che hết CTA quan trọng phía sau).
export const VoiceAssistantPopup: React.FC = () => {
  const { isOpen, mode, setMode, close, isHistoryOpen, closeHistory, transcriptSessionId, openTranscript, closeTranscript } =
    useVoiceAssistant();

  if (!isOpen) return null;

  return (
    <div
      role="dialog"
      aria-label="Trợ lý AloSM"
      className="fixed z-40 inset-x-0 bottom-0 md:inset-auto md:bottom-28 md:right-8
        h-[88vh] md:h-[620px] w-full md:w-[400px]
        bg-white dark:bg-[#12161A] border border-slate-200/80 dark:border-white/10
        rounded-t-3xl md:rounded-3xl shadow-2xl flex flex-col overflow-hidden
        animate-in slide-in-from-bottom-4 fade-in duration-300"
    >
      <div className="flex items-center justify-between px-4 py-3 border-b border-slate-100 dark:border-white/10 shrink-0">
        <p className="text-sm font-bold text-[#191C1E] dark:text-white">Trợ lý AloSM</p>
        <div className="flex items-center gap-2">
          <div className="flex items-center bg-slate-100 dark:bg-white/10 rounded-full p-0.5">
            <button
              type="button"
              onClick={() => setMode("chat")}
              aria-label="Chế độ nhắn tin"
              aria-pressed={mode === "chat"}
              className={`p-1.5 rounded-full transition-colors ${
                mode === "chat" ? "bg-white text-[#006a62] shadow-sm dark:bg-[#0B0E11] dark:text-[#00D1C1]" : "text-slate-400"
              }`}
            >
              <MessageCircle className="w-3.5 h-3.5" />
            </button>
            <button
              type="button"
              onClick={() => setMode("call")}
              aria-label="Chế độ gọi thoại"
              aria-pressed={mode === "call"}
              className={`p-1.5 rounded-full transition-colors ${
                mode === "call" ? "bg-white text-[#006a62] shadow-sm dark:bg-[#0B0E11] dark:text-[#00D1C1]" : "text-slate-400"
              }`}
            >
              <Phone className="w-3.5 h-3.5" />
            </button>
          </div>
          <button
            type="button"
            onClick={close}
            aria-label="Đóng trợ lý AI"
            className="text-slate-400 hover:text-[#191C1E] p-1.5 rounded-full hover:bg-slate-100 transition-colors dark:text-slate-400 dark:hover:text-white dark:hover:bg-white/10"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
      </div>

      <div className="relative flex-1 min-h-0">
        {mode === "chat" ? <VoiceChatPanel /> : <VoiceCallPanel />}
        <BookingConfirmationModal />
        <BookingSuccessModal />
      </div>

      <HistoryPanel isOpen={isHistoryOpen} onClose={closeHistory} onSelectSession={openTranscript} />
      <TranscriptModal sessionId={transcriptSessionId} onClose={closeTranscript} />
    </div>
  );
};
