import React, { useEffect, useRef, useState } from "react";
import { ChevronDown, ChevronUp, MessageSquareText } from "lucide-react";
import type { Message } from "@/features/ai-assistant/context/voice-assistant-context";

type Props = {
  messages: Message[];
};

// "1 cửa sổ nhỏ hiển thị lại text lời người dùng và AI hội thoại với nhau" — đây là
// nơi DUY NHẤT xem lại nội dung cuộc gọi (không còn khung chat riêng), nên mặc định
// MỞ SẴN (trước đây thu gọn theo mặc định vì chỉ là phụ trợ cho khung chat chính, giờ
// đây chính là màn hình chính). Vẫn gập lại được nếu người dùng muốn nhường chỗ cho
// phần điều khiển cuộc gọi.
export const VoiceTranscript: React.FC<Props> = ({ messages }) => {
  const [expanded, setExpanded] = useState(true);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (expanded) bottomRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages.length, expanded]);

  if (messages.length === 0) return null;

  // Bao gồm cả câu chào mở đầu — đây là lời AI nói ĐẦU TIÊN khi khách "nhấc máy", nên
  // phải xuất hiện trong đúng cửa sổ ghi lại nội dung cuộc gọi, không lọc bỏ như khi
  // còn Mode Chat riêng (lúc đó tin nhắn chào đã hiện sẵn trong khung bong bóng chat).
  const visible = expanded ? messages : messages.slice(-2);

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
      <div className="px-4 pb-3 space-y-2 max-h-52 overflow-y-auto">
        {visible.map((message) => (
          <p key={message.id} className="text-xs leading-5">
            <span className={message.role === "user" ? "font-bold text-[#191C1E] dark:text-white" : "font-bold text-[#04763B] dark:text-[#00A651]"}>
              {message.role === "user" ? "Bạn: " : "AI: "}
            </span>
            <span className="text-slate-600 dark:text-slate-300">{message.text}</span>
          </p>
        ))}
        <div ref={bottomRef} />
      </div>
    </div>
  );
};
