import React from "react";
import { History, RotateCcw, X } from "lucide-react";
import { useVoiceAssistant } from "@/features/ai-assistant/context/useVoiceAssistant";
import { VoiceCallPanel } from "@/features/ai-assistant/components/VoiceCallPanel";
import { BookingConfirmationModal } from "@/features/ai-assistant/components/BookingConfirmationModal";
import { BookingSuccessModal } from "@/features/ai-assistant/components/BookingSuccessModal";
import { HistoryPanel } from "@/features/history/components/HistoryPanel";
import { TranscriptModal } from "@/features/history/components/TranscriptModal";

// Popup nổi — KHÔNG phải trang riêng. Desktop: cửa sổ nhỏ nổi góc dưới phải. Mobile:
// bottom sheet trượt lên từ đáy màn hình, không chiếm toàn bộ chiều cao. LUÔN là màn
// hình cuộc gọi thoại kiểu Messenger (không còn mode chat/call để chuyển qua lại) —
// gọi điện thật với AI Agentic, không phải cửa sổ nhắn tin chatbot.
export const VoiceAssistantPopup: React.FC = () => {
  const { isOpen, close, newSession, isHistoryOpen, openHistory, closeHistory, transcriptSessionId, openTranscript, closeTranscript } =
    useVoiceAssistant();

  if (!isOpen) return null;

  return (
    <div
      role="dialog"
      aria-label="Cuộc gọi với trợ lý AloSM"
      className="fixed z-40 inset-x-0 bottom-0 md:inset-auto md:bottom-28 md:right-8
        h-[92vh] md:h-[720px] w-full md:w-[460px]
        bg-white dark:bg-[#12161A] border border-slate-200/80 dark:border-white/10
        rounded-t-3xl md:rounded-3xl shadow-2xl flex flex-col overflow-hidden
        animate-in slide-in-from-bottom-4 fade-in duration-300"
    >
      <div className="flex items-center justify-between px-4 py-3 border-b border-slate-100 dark:border-white/10 shrink-0">
        <p className="text-sm font-bold text-[#191C1E] dark:text-white">Gọi trợ lý AloSM</p>
        <div className="flex items-center gap-1">
          <button
            type="button"
            onClick={() => void newSession()}
            aria-label="Bắt đầu lại cuộc hội thoại"
            title="Bắt đầu lại cuộc hội thoại"
            className="text-slate-400 hover:text-[#00A651] p-1.5 rounded-full hover:bg-[#00A651]/10 transition-colors dark:text-slate-400 dark:hover:text-[#00A651] dark:hover:bg-[#00A651]/10"
          >
            <RotateCcw className="w-4 h-4" />
          </button>
          <button
            type="button"
            onClick={openHistory}
            aria-label="Lịch sử cuộc gọi"
            title="Lịch sử cuộc gọi"
            className="text-slate-400 hover:text-[#191C1E] p-1.5 rounded-full hover:bg-slate-100 transition-colors dark:text-slate-400 dark:hover:text-white dark:hover:bg-white/10"
          >
            <History className="w-4 h-4" />
          </button>
          <button
            type="button"
            onClick={close}
            aria-label="Đóng"
            className="text-slate-400 hover:text-[#191C1E] p-1.5 rounded-full hover:bg-slate-100 transition-colors dark:text-slate-400 dark:hover:text-white dark:hover:bg-white/10"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
      </div>

      <div className="relative flex-1 min-h-0">
        <VoiceCallPanel />
        <BookingConfirmationModal />
        <BookingSuccessModal />
      </div>

      <HistoryPanel isOpen={isHistoryOpen} onClose={closeHistory} onSelectSession={openTranscript} />
      <TranscriptModal sessionId={transcriptSessionId} onClose={closeTranscript} />
    </div>
  );
};
