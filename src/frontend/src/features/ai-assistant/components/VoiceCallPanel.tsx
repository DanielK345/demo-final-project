import React, { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { MessageCircle, Mic, MicOff, PhoneOff, RotateCcw, Volume2, VolumeX } from "lucide-react";
import { useVoiceAssistant } from "@/features/ai-assistant/context/useVoiceAssistant";
import type { AssistantStatus } from "@/features/ai-assistant/context/voice-assistant-context";
import { useVoiceActivityRecorder } from "@/features/voice/useVoiceActivityRecorder";
import { AIStatusIndicator } from "@/features/ai-assistant/components/AIStatusIndicator";
import { BookingProgressStrip } from "@/features/ai-assistant/components/BookingProgressStrip";
import { RideBookingExperience } from "@/features/ai-assistant/components/RideBookingExperience";
import { CURRENT_POLICY_VERSION } from "@/features/policies/api";

const LiveKitVoiceSession = React.lazy(() =>
  import("@/features/livekit/LiveKitVoiceSession").then((module) => ({
    default: module.LiveKitVoiceSession,
  })),
);

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
const LegacyVoiceCallPanel: React.FC = () => {
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
  const consentKey = `alosm_voice_consent_v${CURRENT_POLICY_VERSION}`;
  const [voiceConsent, setVoiceConsent] = useState(() => localStorage.getItem(consentKey) === "accepted");

  // Chỉ thật sự lắng nghe khi: đã có phiên, chưa tự tắt mic, phiên chưa kết thúc, và
  // AI hiện không đang xử lý/đang nói (tránh ghi đè lượt đang gửi hoặc tự ghi lại
  // chính giọng AI phát ra loa). Cho phép lắng nghe lại ngay cả sau lỗi (status
  // "error") — không cần bấm gì để "thử lại" như trước.
  const listeningActive =
    voiceConsent && Boolean(sessionId) && !sessionEnded && !micMuted && status !== "processing" && status !== "speaking" && status !== "connecting";

  const { isSpeechDetected } = useVoiceActivityRecorder({
    active: listeningActive,
    permissionGranted: voiceConsent,
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
  if (!voiceConsent) {
    return (
      <div className="flex h-full flex-col items-center justify-center px-6 text-center">
        <div className="grid h-16 w-16 place-items-center rounded-full bg-[#E7FBF9] text-[#008F88]"><Mic className="h-7 w-7" /></div>
        <h2 className="mt-5 text-xl font-extrabold text-[#173132] dark:text-white">Cho phép xử lý giọng nói?</h2>
        <p className="mt-3 max-w-md text-sm leading-6 text-slate-600 dark:text-slate-300">Khi bạn đồng ý, trình duyệt mới mở micro. Audio và transcript được gửi tới pipeline Voice AI để nhận dạng, sửa lỗi và phản hồi trong phiên. Đây là consent riêng, không dùng cho quảng cáo.</p>
        <Link to="/policies?section=privacy" className="mt-3 text-xs font-bold text-[#008F88] underline">Xem chính sách dữ liệu phiên bản {CURRENT_POLICY_VERSION}</Link>
        <div className="mt-6 flex flex-wrap justify-center gap-2">
          <button type="button" onClick={openConversation} className="rounded-xl border border-slate-300 px-4 py-2 text-sm font-bold text-slate-600 dark:border-white/20 dark:text-slate-200">Dùng chat chữ</button>
          <button type="button" onClick={() => { localStorage.setItem(consentKey, "accepted"); setVoiceConsent(true); }} className="rounded-xl bg-[#00C9B7] px-4 py-2 text-sm font-bold text-white">Đồng ý và mở micro</button>
        </div>
      </div>
    );
  }

  return (
    <div className="flex h-full min-h-0 flex-col items-center overflow-y-auto px-4 py-5 text-center [scrollbar-gutter:stable] sm:px-6">
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

      {/* Điều khiển cuộc gọi luôn nằm ngay dưới sound bubble và ở trong document
          flow. Không dùng absolute/fixed để không thể đè lên thông tin chuyến. */}
      <div className="mb-3 flex shrink-0 items-start justify-center gap-5 sm:gap-7">
      {sessionEnded ? (
        <button
          type="button"
          onClick={() => void newSession()}
          className="inline-flex items-center gap-2 rounded-xl bg-[#00C9B7] px-5 py-2.5 text-sm font-semibold text-[#0B0E11] hover:opacity-90"
        >
          <RotateCcw className="h-4 w-4" />
          Gọi lại
        </button>
      ) : (
        <>
          <button
            type="button"
            onClick={toggleMuted}
            aria-label={isMuted ? "Bật loa" : "Tắt loa"}
            title={isMuted ? "Bật loa" : "Tắt loa"}
            className="group flex w-16 flex-col items-center gap-1.5 text-[10px] font-semibold text-slate-500 dark:text-slate-400"
          >
            <span className="grid h-12 w-12 place-items-center rounded-full bg-slate-100 text-slate-600 transition group-hover:bg-slate-200 dark:bg-white/10 dark:text-slate-300 dark:group-hover:bg-white/20">
              {isMuted ? <VolumeX className="h-5 w-5" /> : <Volume2 className="h-5 w-5" />}
            </span>
            {isMuted ? "Bật loa" : "Tắt loa"}
          </button>

          <button
            type="button"
            onClick={() => setMicMuted((value) => !value)}
            aria-label={micMuted ? "Bật micro" : "Tắt micro"}
            title={micMuted ? "Bật micro" : "Tắt micro"}
            className="group flex w-16 flex-col items-center gap-1.5 text-[10px] font-semibold text-slate-500 dark:text-slate-400"
          >
            <span className={`grid h-14 w-14 place-items-center rounded-full shadow-md transition ${
              micMuted
                ? "bg-slate-200 text-slate-500 dark:bg-white/10 dark:text-slate-400"
                : "bg-[#00C9B7] text-white group-hover:bg-[#008F88]"
            }`}>
              {micMuted ? <MicOff className="h-6 w-6" /> : <Mic className="h-6 w-6" />}
            </span>
            {micMuted ? "Bật micro" : "Tắt micro"}
          </button>

          <button
            type="button"
            onClick={close}
            aria-label="Kết thúc cuộc gọi"
            title="Kết thúc cuộc gọi"
            className="group flex w-16 flex-col items-center gap-1.5 text-[10px] font-semibold text-rose-500"
          >
            <span className="grid h-12 w-12 place-items-center rounded-full bg-rose-50 text-rose-600 transition group-hover:bg-rose-100 dark:bg-rose-500/10 dark:text-rose-400 dark:group-hover:bg-rose-500/20">
              <PhoneOff className="h-5 w-5" />
            </span>
            Kết thúc
          </button>
        </>
      )}
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
    </div>
  );
};

export const VoiceCallPanel: React.FC = () => {
  if (import.meta.env.VITE_VOICE_RUNTIME === "livekit") {
    return (
      <React.Suspense fallback={<div className="p-6 text-center text-sm text-slate-500">Đang tải cuộc gọi…</div>}>
        <LiveKitVoiceSession />
      </React.Suspense>
    );
  }
  return <LegacyVoiceCallPanel />;
};
