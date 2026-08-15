import React, { useState } from "react";
import { ChevronDown, ChevronUp, MessageSquareText } from "lucide-react";
import type { Message } from "@/features/ai-assistant/context/voice-assistant-context";

type Props = {
  messages: Message[];
};

// Transcript rút gọn trong Voice Call Mode (mục 6) — mặc định chỉ hiện lượt trao đổi
// gần nhất, mở rộng xem thêm khi cần, KHÔNG biến thành cả màn hình chat lớn.
export const VoiceTranscript: React.FC<Props> = ({ messages }) => {
  const [expanded, setExpanded] = useState(false);
  const conversation = messages.filter((message) => message.id !== "welcome");
  if (conversation.length === 0) return null;

  const visible = expanded ? conversation : conversation.slice(-2);

  return (
    <div className="w-full rounded-2xl bg-slate-50 border border-slate-200/80 dark:bg-white/5 dark:border-white/10">
      <button
        type="button"
        onClick={() => setExpanded((value) => !value)}
        className="w-full flex items-center justify-between px-4 py-2.5 text-xs font-semibold text-slate-500 dark:text-slate-400"
      >
        <span className="flex items-center gap-1.5">
          <MessageSquareText className="w-3.5 h-3.5" />
          Nội dung cuộc gọi
        </span>
        {expanded ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
      </button>
      <div className="px-4 pb-3 space-y-2 max-h-40 overflow-y-auto">
        {visible.map((message) => (
          <p key={message.id} className="text-xs leading-5">
            <span className={message.role === "user" ? "font-bold text-[#191C1E] dark:text-white" : "font-bold text-[#006a62] dark:text-[#00D1C1]"}>
              {message.role === "user" ? "Bạn: " : "AI: "}
            </span>
            <span className="text-slate-600 dark:text-slate-300">{message.text}</span>
          </p>
        ))}
      </div>
    </div>
  );
};
