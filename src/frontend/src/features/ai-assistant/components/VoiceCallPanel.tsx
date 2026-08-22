import React from "react";

const LiveKitVoiceSession = React.lazy(() =>
  import("@/features/livekit/LiveKitVoiceSession").then((module) => ({
    default: module.LiveKitVoiceSession,
  })),
);

export const VoiceCallPanel: React.FC = () => (
  <React.Suspense fallback={<div className="p-6 text-center text-sm text-slate-500">Đang tải cuộc gọi…</div>}>
    <LiveKitVoiceSession />
  </React.Suspense>
);
