import React from "react";
import { Mic, X } from "lucide-react";
import { useVoiceAssistant } from "@/features/ai-assistant/context/useVoiceAssistant";

// Entry point DUY NHẤT của Voice AI (mục 2) — nổi cố định góc màn hình, không che nội
// dung chính, luôn khả dụng ở mọi trang (mounted 1 lần trong AppLayout). Tự ẩn khi
// popup đang mở (mục 3 — click mở popup, không phải chuyển trang) để tránh 2 lớp
// điều khiển chồng nhau trên mobile khi popup đã chiếm phần dưới màn hình.
export const VoiceAIButton: React.FC = () => {
  const { isOpen, open, close, status } = useVoiceAssistant();

  return (
    <button
      type="button"
      onClick={isOpen ? close : open}
      aria-label={isOpen ? "Đóng trợ lý AI" : "Mở trợ lý AI AloSM"}
      aria-expanded={isOpen}
      className={`fixed z-40 flex items-center justify-center rounded-full shadow-xl transition-all duration-300 cursor-pointer
        bottom-24 right-5 w-14 h-14 md:bottom-8 md:right-8 md:w-16 md:h-16
        ${isOpen ? "bg-slate-800 dark:bg-white/10 rotate-90" : "bg-gradient-to-br from-[#00D1C1] to-[#006a62] hover:scale-105 active:scale-95"}
        ${!isOpen && status === "listening" ? "animate-pulse ring-4 ring-[#00D1C1]/30" : ""}`}
    >
      {isOpen ? (
        <X className="w-6 h-6 text-white" />
      ) : (
        <Mic className="w-6 h-6 md:w-7 md:h-7 text-white" />
      )}
      {!isOpen && (
        <span className="absolute inset-0 rounded-full bg-[#00D1C1]/40 animate-ping [animation-duration:2.5s] pointer-events-none" />
      )}
    </button>
  );
};
