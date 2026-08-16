import React from "react";
import { Phone, PhoneOff } from "lucide-react";
import { useVoiceAssistant } from "@/features/ai-assistant/context/useVoiceAssistant";

// Entry point DUY NHẤT của Voice AI — nổi cố định góc màn hình, không che nội dung
// chính, luôn khả dụng ở mọi trang (mounted 1 lần trong AppLayout). Bấm là MỞ CUỘC
// GỌI thoại thẳng (không phải mở popup chat) — icon ống nghe, không phải mic, đúng
// tinh thần "gọi điện với AI Agentic chứ không phải nhắn tin chatbot". Tự ẩn khi popup
// đang mở để tránh 2 lớp điều khiển chồng nhau trên mobile.
export const VoiceAIButton: React.FC = () => {
  const { isOpen, open, close, status } = useVoiceAssistant();

  return (
    <button
      type="button"
      onClick={isOpen ? close : open}
      aria-label={isOpen ? "Kết thúc cuộc gọi với trợ lý AI" : "Gọi trợ lý AI AloSM"}
      aria-expanded={isOpen}
      className={`fixed z-40 flex items-center justify-center rounded-full shadow-xl transition-all duration-300 cursor-pointer
        bottom-24 right-5 w-14 h-14 md:bottom-8 md:right-8 md:w-16 md:h-16
        ${isOpen ? "bg-rose-500 hover:bg-rose-600" : "bg-gradient-to-br from-[#00A651] to-[#04763B] hover:scale-105 active:scale-95"}
        ${!isOpen && status === "listening" ? "animate-pulse ring-4 ring-[#00A651]/30" : ""}`}
    >
      {isOpen ? (
        <PhoneOff className="w-6 h-6 text-white" />
      ) : (
        <Phone className="w-6 h-6 md:w-7 md:h-7 text-white" />
      )}
      {!isOpen && (
        <span className="absolute inset-0 rounded-full bg-[#00A651]/40 animate-ping [animation-duration:2.5s] pointer-events-none" />
      )}
    </button>
  );
};
