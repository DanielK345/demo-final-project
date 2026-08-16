import React, { useEffect, useState } from "react";
import { MessageCircle, Mic, MicOff, PhoneOff, RotateCcw, Volume2, VolumeX } from "lucide-react";
import { useVoiceAssistant } from "@/features/ai-assistant/context/useVoiceAssistant";
import type { AssistantStatus } from "@/features/ai-assistant/context/voice-assistant-context";
import { useVoiceActivityRecorder } from "@/features/voice/useVoiceActivityRecorder";
import { AIStatusIndicator } from "@/features/ai-assistant/components/AIStatusIndicator";
import { BookingProgressStrip } from "@/features/ai-assistant/components/BookingProgressStrip";
import { RideBookingExperience } from "@/features/ai-assistant/components/RideBookingExperience";

function formatDuration(totalSeconds: number): string {
  const minutes = Math.floor(totalSeconds / 60)
    .toString()
    .padStart(2, "0");
  const seconds = (totalSeconds % 60).toString().padStart(2, "0");
  return `${minutes}:${seconds}`;
}

// Màn hình gọi thoại kiểu Messenger — đây là toàn bộ giao diện popup, không phải 1
// trong 2 chế độ nữa. State hiển thị đi qua đúng 1 AssistantStatus, không rải rác
// boolean. Micro LUÔN lắng nghe (VAD tự động phát hiện lúc nói/lúc dứt câu) — không
// còn kiểu "bấm mic mới được nói", đúng cảm giác một cuộc gọi thật.
export const VoiceCallPanel: React.FC = () => {
  const {
    status,
    sessionId,
    sessionEnded,
    handleVoiceRecorded,
    messages,
    bookingProgress,
    sendText,
    openConversation,
    isMuted,
    toggleMuted,
    reportError,
    close,
    newSession,
  } = useVoiceAssistant();
  const [micMuted, setMicMuted] = useState(false);
  const [elapsed, setElapsed] = useState(0);

  // Chỉ thật sự lắng nghe khi: đã có phiên, chưa tự tắt mic, phiên chưa kết thúc, và
  // AI hiện không đang xử lý/đang nói (tránh ghi đè lượt đang gửi hoặc tự ghi lại
  // chính giọng AI phát ra loa). Cho phép lắng nghe lại ngay cả sau lỗi (status
  // "error") — không cần bấm gì để "thử lại" như trước.
  const listeningActive =
    Boolean(sessionId) && !sessionEnded && !micMuted && status !== "processing" && status !== "speaking" && status !== "connecting";

  const { isSpeechDetected } = useVoiceActivityRecorder({
    active: listeningActive,
    onUtterance: handleVoiceRecorded,
    onError: (error) => reportError(error.message),
  });

  // Đếm thời lượng cuộc gọi kể từ lúc vào Voice Call Mode — reset mỗi lần quay lại
  // (đúng tinh thần "thời lượng cuộc gọi hiện tại", không phải tuổi thọ cả phiên).
  useEffect(() => {
    const interval = window.setInterval(() => setElapsed((value) => value + 1), 1000);
    return () => window.clearInterval(interval);
  }, []);

  const displayStatus: AssistantStatus = !sessionId ? "connecting" : isSpeechDetected ? "listening" : status;
  const isActive = displayStatus === "listening" || displayStatus === "speaking";
  const latestUserMessage = [...messages].reverse().find((message) => message.role === "user")?.text;

  return (
    <div className="relative flex h-full min-h-0 flex-col items-center overflow-hidden px-4 py-5 pb-28 text-center sm:px-6">
      <p className="shrink-0 text-xs font-bold text-slate-400 dark:text-slate-500 uppercase tracking-wider">AloSM Voice</p>
      <p className="mt-1 shrink-0 text-sm font-mono text-slate-400 dark:text-slate-500">{formatDuration(elapsed)}</p>

      {/* Orb trung tâm — pulse khi đang nghe/nói, đứng yên khi rảnh */}
      <div className="relative my-4 grid shrink-0 place-items-center">
        {isActive && (
          <span
            className={`absolute w-32 h-32 rounded-full animate-ping [animation-duration:1.6s] ${
              displayStatus === "listening" ? "bg-[#00C9B7]/30" : "bg-[#008F88]/30"
            }`}
          />
        )}
        <div
          className={`w-28 h-28 rounded-full flex items-center justify-center border-4 transition-colors duration-300 ${
            displayStatus === "listening"
              ? "bg-[#00C9B7]/15 border-[#00C9B7]"
              : displayStatus === "speaking"
                ? "bg-[#008F88]/15 border-[#008F88] dark:border-[#00C9B7]"
                : displayStatus === "error"
                  ? "bg-rose-50 border-rose-300 dark:bg-rose-500/10 dark:border-rose-500/40"
                  : "bg-slate-100 border-slate-200 dark:bg-white/5 dark:border-white/10"
          }`}
        >
          {/* Waveform đơn giản — chỉ nhảy khi có âm thanh đang diễn ra (nghe hoặc nói) */}
          <div className="flex items-end gap-1 h-8" aria-hidden>
            {[0, 1, 2, 3, 4].map((bar) => (
              <span
                key={bar}
                style={{
                  animationDelay: `${bar * 0.12}s`,
                  height: isActive ? `${10 + ((bar % 3) + 1) * 6}px` : "4px",
                }}
                className={`w-1.5 rounded-full bg-[#008F88] dark:bg-[#00C9B7] transition-[height] duration-300 ${
                  isActive ? "animate-[pulse_0.9s_ease-in-out_infinite]" : ""
                }`}
              />
            ))}
          </div>
        </div>
      </div>

      <div className="shrink-0">
      {micMuted ? (
        <span className="inline-flex items-center gap-1.5 text-xs font-semibold text-slate-400 dark:text-slate-500">
          <MicOff className="w-3.5 h-3.5" />
          Micro đang tắt — bấm nút micro để tiếp tục nói
        </span>
      ) : (
        <AIStatusIndicator status={displayStatus} />
      )}
      </div>

      <div className="w-full shrink-0">
        <BookingProgressStrip progress={bookingProgress} />
      </div>
      <div className="mt-3 w-full shrink-0">
        <RideBookingExperience
          progress={bookingProgress}
          onSay={sendText}
          disabled={status === "processing"}
          voiceCommand={latestUserMessage}
        />
      </div>
      <button
        type="button"
        onClick={openConversation}
        className="mt-3 inline-flex shrink-0 items-center gap-2 rounded-xl border border-[#00C9B7]/25 bg-[#E9FBF8] px-4 py-2.5 text-sm font-semibold text-[#008F88] transition hover:bg-[#D7F7F2] dark:bg-[#00C9B7]/10 dark:text-[#5BE0D3] dark:hover:bg-[#00C9B7]/20"
      >
        <MessageCircle className="h-4 w-4" />
        Xem cuộc trò chuyện{messages.length > 1 ? ` (${messages.length})` : ""}
      </button>

      <div className="absolute inset-x-0 bottom-5 z-10 flex w-full justify-center px-4">
      {sessionEnded ? (
        <button
          type="button"
          onClick={() => void newSession()}
          className="inline-flex items-center gap-2 rounded-xl bg-[#00C9B7] px-5 py-2.5 text-sm font-semibold text-[#0B0E11] hover:opacity-90"
        >
          <RotateCcw className="w-4 h-4" />
          Gọi lại
        </button>
      ) : (
        <div className="flex items-center gap-6">
          <button
            type="button"
            onClick={toggleMuted}
            aria-label={isMuted ? "Bật loa" : "Tắt loa"}
            title={isMuted ? "Bật loa" : "Tắt loa"}
            className="w-11 h-11 rounded-full grid place-items-center bg-slate-100 text-slate-600 hover:bg-slate-200 dark:bg-white/10 dark:text-slate-300 dark:hover:bg-white/20"
          >
            {isMuted ? <VolumeX className="w-5 h-5" /> : <Volume2 className="w-5 h-5" />}
          </button>

          {/* Không còn "bấm để nói" — nút này giờ là bật/tắt micro của chính mình (như
              nút mute trên mọi app gọi điện thật), mặc định LUÔN bật để nghe liên tục. */}
          <button
            type="button"
            onClick={() => setMicMuted((value) => !value)}
            aria-label={micMuted ? "Bật micro" : "Tắt micro"}
            title={micMuted ? "Bật micro" : "Tắt micro"}
            className={`w-16 h-16 rounded-full grid place-items-center shadow-lg transition ${
              micMuted
                ? "bg-slate-200 text-slate-500 dark:bg-white/10 dark:text-slate-400"
                : "bg-[#00C9B7] hover:bg-[#008F88] text-[#0B0E11] hover:text-white"
            }`}
          >
            {micMuted ? <MicOff className="w-6 h-6" /> : <Mic className="w-6 h-6 text-white" />}
          </button>

          <button
            type="button"
            onClick={close}
            aria-label="Kết thúc cuộc gọi"
            title="Kết thúc cuộc gọi"
            className="w-11 h-11 rounded-full grid place-items-center bg-rose-50 text-rose-600 hover:bg-rose-100 dark:bg-rose-500/10 dark:text-rose-400 dark:hover:bg-rose-500/20"
          >
            <PhoneOff className="w-5 h-5" />
          </button>
        </div>
      )}
      </div>
    </div>
  );
};
