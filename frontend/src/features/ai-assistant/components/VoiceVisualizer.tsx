import React from "react";
import { Mic } from "lucide-react";

interface VoiceVisualizerProps {
  isListening: boolean;
  onMicClick: () => void;
}

export const VoiceVisualizer: React.FC<VoiceVisualizerProps> = ({
  isListening,
  onMicClick,
}) => {
  const bounceDelays = [
    "0ms",
    "200ms",
    "400ms",
    "600ms",
    "800ms",
    "100ms",
    "300ms",
    "500ms",
    "700ms",
    "900ms",
  ];

  return (
    <div className="glass-panel rounded-2xl p-8 flex flex-col items-center justify-center flex-1 relative overflow-hidden min-h-[380px]">
      <div className="absolute inset-0 bg-gradient-to-b from-[#00D1C1]/5 to-transparent pointer-events-none" />

      {/* Voice UI Layer Disclaimer Tag */}
      <span className="text-[10px] font-mono text-slate-400 bg-slate-100 px-2.5 py-0.5 rounded-full mb-4 z-10">
        Voice UI Layer — Ready for STT/TTS Integration
      </span>

      {/* Mic Pulse Circles */}
      <div className="relative w-48 h-48 flex items-center justify-center mb-6">
        <div className="absolute inset-0 rounded-full bg-[#00D1C1]/20 pulse-ring" />
        <div
          className="absolute inset-4 rounded-full bg-[#00D1C1]/30 pulse-ring"
          style={{ animationDelay: "0.5s" }}
        />
        <button
          type="button"
          onClick={onMicClick}
          title="Nhấn để nói"
          className="relative w-24 h-24 rounded-full bg-gradient-to-tr from-[#00D1C1] to-[#006a62] shadow-[0_0_40px_rgba(0,209,193,0.5)] flex items-center justify-center text-white z-10 cursor-pointer hover:scale-105 transition-transform active:scale-95"
        >
          <Mic className="w-10 h-10" />
        </button>
      </div>

      {/* Text Messages */}
      <div className="text-center z-10 mb-2">
        <h2 className="text-2xl font-bold text-[#191C1E] mb-1">
          {isListening ? "Hệ thống đang nghe..." : "Trợ lý AI sẵn sàng"}
        </h2>
        <p className="text-sm text-slate-500">
          {isListening ? "Hãy nói điểm đến của bạn..." : "Nhấp micrô để nói điểm đến"}
        </p>
      </div>

      {/* Simulated Waveform */}
      <div className="flex items-center justify-center gap-1.5 mt-6 h-12 w-full max-w-md px-8 opacity-80">
        {bounceDelays.map((delay, i) => (
          <div
            key={i}
            className={`w-1.5 bg-[#00D1C1] rounded-full animate-bounce ${
              isListening ? "h-10" : "h-5 opacity-60"
            }`}
            style={{ animationDelay: delay }}
          />
        ))}
      </div>
    </div>
  );
};
