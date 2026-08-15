import React, { useEffect, useState } from "react";
import { Keyboard, Mic, PhoneOff, Volume2, VolumeX } from "lucide-react";
import { useVoiceAssistant } from "@/features/ai-assistant/context/useVoiceAssistant";
import type { AssistantStatus } from "@/features/ai-assistant/context/voice-assistant-context";
import { useVoiceRecorder } from "@/features/voice/useVoiceRecorder";
import { AIStatusIndicator } from "@/features/ai-assistant/components/AIStatusIndicator";
import { VoiceTranscript } from "@/features/ai-assistant/components/VoiceTranscript";

function formatDuration(totalSeconds: number): string {
  const minutes = Math.floor(totalSeconds / 60)
    .toString()
    .padStart(2, "0");
  const seconds = (totalSeconds % 60).toString().padStart(2, "0");
  return `${minutes}:${seconds}`;
}

// Mode B — Voice Call (mục 5+6): màn hình gọi thoại thu nhỏ trong popup, không toàn
// màn hình. State hiển thị đi qua đúng 1 AssistantStatus (mục 19), không rải rác
// boolean.
export const VoiceCallPanel: React.FC = () => {
  const {
    status,
    sessionId,
    sessionEnded,
    handleVoiceRecorded,
    messages,
    isMuted,
    toggleMuted,
    reportError,
    setMode,
  } = useVoiceAssistant();
  const [recording, setRecording] = useState(false);
  const [elapsed, setElapsed] = useState(0);

  const { toggleRecording } = useVoiceRecorder({
    onRecorded: async (audio) => {
      setRecording(false);
      await handleVoiceRecorded(audio);
    },
    onError: (error) => {
      setRecording(false);
      reportError(error.message);
    },
  });

  // Đếm thời lượng cuộc gọi kể từ lúc vào Voice Call Mode — reset mỗi lần quay lại
  // (đúng tinh thần "thời lượng cuộc gọi hiện tại", không phải tuổi thọ cả phiên).
  useEffect(() => {
    const interval = window.setInterval(() => setElapsed((value) => value + 1), 1000);
    return () => window.clearInterval(interval);
  }, []);

  const displayStatus: AssistantStatus = !sessionId
    ? "connecting"
    : recording
      ? "listening"
      : status;

  const canTalk = Boolean(sessionId) && !sessionEnded && displayStatus !== "processing" && displayStatus !== "speaking";

  const handleMicPress = async () => {
    if (!canTalk) return;
    if (!recording) setRecording(true);
    await toggleRecording();
  };

  const isActive = displayStatus === "listening" || displayStatus === "speaking";

  return (
    <div className="flex flex-col items-center h-full px-6 py-8 text-center">
      <p className="text-xs font-bold text-slate-400 dark:text-slate-500 uppercase tracking-wider">AloSM Voice</p>
      <p className="text-sm font-mono text-slate-400 dark:text-slate-500 mt-1">{formatDuration(elapsed)}</p>

      {/* Orb trung tâm — pulse khi đang nghe/nói, đứng yên khi rảnh */}
      <div className="relative my-8 grid place-items-center">
        {isActive && (
          <span
            className={`absolute w-32 h-32 rounded-full animate-ping [animation-duration:1.6s] ${
              displayStatus === "listening" ? "bg-[#00D1C1]/30" : "bg-[#006a62]/30"
            }`}
          />
        )}
        <div
          className={`w-28 h-28 rounded-full flex items-center justify-center border-4 transition-colors duration-300 ${
            displayStatus === "listening"
              ? "bg-[#00D1C1]/15 border-[#00D1C1]"
              : displayStatus === "speaking"
                ? "bg-[#006a62]/15 border-[#006a62] dark:border-[#00D1C1]"
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
                className={`w-1.5 rounded-full bg-[#006a62] dark:bg-[#00D1C1] transition-[height] duration-300 ${
                  isActive ? "animate-[pulse_0.9s_ease-in-out_infinite]" : ""
                }`}
              />
            ))}
          </div>
        </div>
      </div>

      <AIStatusIndicator status={displayStatus} />

      <div className="flex-1" />

      <VoiceTranscript messages={messages} />

      {sessionEnded ? (
        <button
          type="button"
          onClick={() => setMode("chat")}
          className="mt-6 inline-flex items-center gap-2 rounded-xl bg-[#00D1C1] px-5 py-2.5 text-sm font-semibold text-[#0B0E11] hover:opacity-90"
        >
          Quay lại trò chuyện
        </button>
      ) : (
        <div className="flex items-center gap-6 mt-6">
          <button
            type="button"
            onClick={toggleMuted}
            aria-label={isMuted ? "Bật loa" : "Tắt loa"}
            title={isMuted ? "Bật loa" : "Tắt loa"}
            className="w-11 h-11 rounded-full grid place-items-center bg-slate-100 text-slate-600 hover:bg-slate-200 dark:bg-white/10 dark:text-slate-300 dark:hover:bg-white/20"
          >
            {isMuted ? <VolumeX className="w-5 h-5" /> : <Volume2 className="w-5 h-5" />}
          </button>

          <button
            type="button"
            onClick={handleMicPress}
            disabled={!canTalk}
            aria-label={recording ? "Dừng nói, gửi cho AI" : "Nhấn để nói"}
            className={`w-16 h-16 rounded-full grid place-items-center shadow-lg transition disabled:opacity-50 ${
              recording
                ? "bg-rose-500 hover:bg-rose-600 scale-105"
                : "bg-[#00D1C1] hover:bg-[#006a62] text-[#0B0E11] hover:text-white"
            }`}
          >
            <Mic className="w-6 h-6 text-white" />
          </button>

          <button
            type="button"
            onClick={() => setMode("chat")}
            aria-label="Kết thúc cuộc gọi, quay lại nhắn tin"
            title="Kết thúc cuộc gọi"
            className="w-11 h-11 rounded-full grid place-items-center bg-rose-50 text-rose-600 hover:bg-rose-100 dark:bg-rose-500/10 dark:text-rose-400 dark:hover:bg-rose-500/20"
          >
            <PhoneOff className="w-5 h-5" />
          </button>
        </div>
      )}

      {!sessionEnded && (
        <button
          type="button"
          onClick={() => setMode("chat")}
          className="mt-4 inline-flex items-center gap-1.5 text-xs font-semibold text-slate-400 hover:text-slate-600 dark:text-slate-500 dark:hover:text-slate-300"
        >
          <Keyboard className="w-3.5 h-3.5" />
          Chuyển sang nhắn tin
        </button>
      )}
    </div>
  );
};
