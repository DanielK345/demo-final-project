import { createContext } from "react";
import type { BookingLifecycleStatus, BookingProgress } from "@/features/ride/api";
import type { CompletedBooking } from "@/features/ai-assistant/components/BookingSuccessPanel";

// Tách riêng khỏi VoiceAssistantContext.tsx: file đó chỉ nên export component
// (Fast Refresh của Vite yêu cầu file component không lẫn export khác — oxlint
// react(only-export-components) sẽ cảnh báo nếu gộp chung, đúng cách ThemeProvider đã
// tách theme-context.ts/useTheme.ts trước đó).

export type AssistantMode = "chat" | "call";

// Gộp mọi trạng thái "AI đang làm gì" vào 1 giá trị duy nhất thay vì rải rác nhiều cờ
// boolean (isSending/isListening/isCalling/...) dễ lệch nhau — đúng yêu cầu state
// machine tường minh. "error" chỉ phản ánh lỗi kỹ thuật của LƯỢT VỪA RỒI (mất kết
// nối, không gọi được API...), không phải trạng thái đặt xe thất bại (cái đó đi qua
// completedBooking/lifecycleStatus + BookingSuccessModal, đã có UI riêng).
export type AssistantStatus = "connecting" | "idle" | "listening" | "processing" | "speaking" | "error";

export type Message = { id: string; role: "user" | "assistant"; text: string };

export interface VoiceAssistantValue {
  // Popup + chế độ hiển thị
  isOpen: boolean;
  mode: AssistantMode;
  open: () => void;
  close: () => void;
  setMode: (mode: AssistantMode) => void;
  // Mở popup + gửi luôn 1 câu dựng sẵn (dùng bởi các nút "AI đặt xe ngay" khắp app)
  openWithPrefill: (prefill: string) => void;

  // Hội thoại
  status: AssistantStatus;
  messages: Message[];
  notice: string | null;
  sessionId: string | null;
  sessionEnded: boolean;
  sendText: (value: string) => Promise<void>;
  handleVoiceRecorded: (audio: Blob) => Promise<void>;
  endSession: () => Promise<void>;
  newSession: () => Promise<void>;

  // Tiến trình đặt xe (đổ trực tiếp từ state thật trả về mỗi lượt — không tự bịa field)
  bookingProgress: BookingProgress | null;
  lifecycleStatus: BookingLifecycleStatus | null;

  // Xác nhận trước khi đặt (mục 7-9 yêu cầu) — bám đúng BookingStep.CONFIRM thật của
  // Core Agent, không tự đặt xe ngay khi đủ field.
  showConfirmationModal: boolean;
  confirmBooking: () => Promise<void>;
  dismissConfirmation: () => void;

  // Kết quả đặt xe (thành công/thất bại)
  showSuccessModal: boolean;
  completedBooking: CompletedBooking | null;
  closeSuccessModal: () => void;
  submitRating: (rating: number) => Promise<void>;
  isSubmittingRating: boolean;

  // Lịch sử hội thoại cũ (tái dùng HistoryPanel/TranscriptModal có sẵn)
  isHistoryOpen: boolean;
  openHistory: () => void;
  closeHistory: () => void;
  transcriptSessionId: string | null;
  openTranscript: (sessionId: string) => void;
  closeTranscript: () => void;

  // Voice Call Mode
  isMuted: boolean;
  toggleMuted: () => void;
  reportError: (message: string) => void;
}

export const VoiceAssistantContext = createContext<VoiceAssistantValue | null>(null);
