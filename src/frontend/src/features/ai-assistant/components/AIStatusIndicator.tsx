import React from "react";
import { Loader2, Mic, Volume2, WifiOff } from "lucide-react";
import type { AssistantStatus } from "@/features/ai-assistant/context/voice-assistant-context";

type Props = {
  status: AssistantStatus;
  className?: string;
};

// Nhãn tiếng Việt tự nhiên cho từng trạng thái thật của agent — không lộ state kỹ
// thuật (vd "PROCESSING"/"WAITING_FOR_BOOKING_RESULT") ra giao diện người dùng (mục
// 5 + 14 của yêu cầu).
const STATUS_CONFIG: Record<AssistantStatus, { label: string; icon: React.ElementType; className: string }> = {
  connecting: { label: "Đang kết nối…", icon: Loader2, className: "text-slate-500 dark:text-slate-400" },
  idle: { label: "Mời anh/chị nói…", icon: Mic, className: "text-slate-500 dark:text-slate-400" },
  listening: { label: "Đang nghe…", icon: Mic, className: "text-[#00C9B7]" },
  processing: { label: "Đang suy nghĩ…", icon: Loader2, className: "text-amber-500" },
  speaking: { label: "Đang trả lời…", icon: Volume2, className: "text-[#00C9B7]" },
  error: { label: "Mất kết nối", icon: WifiOff, className: "text-rose-500" },
};

export const AIStatusIndicator: React.FC<Props> = ({ status, className }) => {
  const config = STATUS_CONFIG[status];
  const Icon = config.icon;
  const isSpinning = status === "connecting" || status === "processing";

  return (
    <span className={`inline-flex items-center gap-1.5 text-xs font-semibold ${config.className} ${className ?? ""}`}>
      <Icon className={`w-3.5 h-3.5 ${isSpinning ? "animate-spin" : ""}`} />
      {config.label}
    </span>
  );
};
