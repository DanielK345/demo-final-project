import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  RoomAudioRenderer,
  SessionProvider,
  useAgent,
  useDataChannel,
  useLocalParticipant,
  useSession,
  useSessionMessages,
} from "@livekit/components-react";
import { LoaderCircle, Mic, MicOff, PhoneOff, Send, Volume2, VolumeX } from "lucide-react";
import { CURRENT_POLICY_VERSION } from "@/features/policies/api";
import { useVoiceAssistant } from "@/features/ai-assistant/context/useVoiceAssistant";
import { discardPreparedAloSMCall, prepareAloSMCall } from "./prepareCall";
import { createAloSMTokenSource, LIVEKIT_AGENT_NAME } from "./tokenSource";
import {
  BOOKING_STATE_TOPIC,
  TRANSCRIPT_REWRITE_TOPIC,
  type BookingState,
  type TranscriptRewriteEvent,
} from "./contracts";

const stateLabels = {
  disconnected: "Đã ngắt kết nối",
  connecting: "Đang kết nối",
  "pre-connect-buffering": "Đang mở micro",
  initializing: "Tổng đài đang vào phòng",
  idle: "Đang khởi tạo",
  listening: "Đang nghe bạn",
  thinking: "Đang xử lý",
  speaking: "Đang trả lời",
  failed: "Kết nối thất bại",
} as const;

function formatRewriteLatency(durationMs: number): string {
  return durationMs < 1_000 ? `${durationMs} ms` : `${(durationMs / 1_000).toFixed(1)} s`;
}

function UserTranscriptBubble({
  rawText,
  rewrite,
}: {
  rawText: string;
  rewrite?: TranscriptRewriteEvent;
}) {
  const startedAtRef = useRef(performance.now());
  const [elapsedMs, setElapsedMs] = useState(0);
  const failed = rewrite?.status === "provider_error";
  const skipped = rewrite?.status === "disabled_or_unconfigured" || rewrite?.status === "low_asr_confidence";
  const completed = Boolean(rewrite) && !failed && !skipped;

  useEffect(() => {
    if (rewrite) return;
    const intervalId = window.setInterval(() => {
      setElapsedMs(Math.round(performance.now() - startedAtRef.current));
    }, 100);
    return () => window.clearInterval(intervalId);
  }, [rewrite]);

  return (
    <div
      className={`max-w-[85%] rounded-2xl px-4 py-2.5 text-sm transition-colors duration-300 ${
        completed
          ? "bg-[#007F76] text-white"
          : "bg-slate-200 text-slate-500 dark:bg-white/10 dark:text-slate-400"
      }`}
    >
      <p className="whitespace-pre-wrap break-words">{completed ? rewrite?.normalized_text : rawText}</p>
      <p className={`mt-1 flex items-center gap-1.5 text-[10px] ${completed ? "text-white/75" : "text-slate-400"}`}>
        {!rewrite ? <LoaderCircle className="h-3 w-3 animate-spin" aria-hidden /> : null}
        {!rewrite
          ? `Đang hiệu chỉnh · ${formatRewriteLatency(elapsedMs)}`
          : completed
            ? `${rewrite.applied ? "Đã hiệu chỉnh" : "Đã kiểm tra"} · ${formatRewriteLatency(rewrite.duration_ms ?? elapsedMs)}`
            : failed
              ? `Không thể hiệu chỉnh · ${formatRewriteLatency(rewrite.duration_ms ?? elapsedMs)}`
              : "Giữ nguyên transcript"}
      </p>
    </div>
  );
}

function LiveKitCallContent({
  onClose,
  onRetry,
  autoRetry,
}: {
  onClose: () => void;
  onRetry: () => void;
  autoRetry: boolean;
}) {
  const agent = useAgent();
  const { messages, send, isSending } = useSessionMessages();
  const { localParticipant, isMicrophoneEnabled } = useLocalParticipant();
  const [speakerMuted, setSpeakerMuted] = useState(false);
  const [draft, setDraft] = useState("");
  const [bookingState, setBookingState] = useState<BookingState | null>(null);
  const [transcriptRewrites, setTranscriptRewrites] = useState<Record<string, TranscriptRewriteEvent>>({});
  const { message: bookingStateMessage } = useDataChannel(BOOKING_STATE_TOPIC);
  const { message: transcriptRewriteMessage } = useDataChannel(TRANSCRIPT_REWRITE_TOPIC);

  useEffect(() => {
    if (!bookingStateMessage) return;
    try {
      const decoded = new TextDecoder().decode(bookingStateMessage.payload);
      setBookingState(JSON.parse(decoded) as BookingState);
    } catch {
      // Ignore malformed/older packets; conversation audio must keep running.
    }
  }, [bookingStateMessage]);

  useEffect(() => {
    if (!transcriptRewriteMessage) return;
    try {
      const decoded = new TextDecoder().decode(transcriptRewriteMessage.payload);
      const rewrite = JSON.parse(decoded) as TranscriptRewriteEvent;
      if (!rewrite.item_id || rewrite.schema_version !== "1") return;
      setTranscriptRewrites((current) => ({ ...current, [rewrite.item_id]: rewrite }));
    } catch {
      // Ignore malformed/older packets; raw realtime transcript remains visible.
    }
  }, [transcriptRewriteMessage]);

  useEffect(() => {
    if (!autoRetry || agent.state !== "failed") return;
    const timeoutId = window.setTimeout(onRetry, 1_500);
    return () => window.clearTimeout(timeoutId);
  }, [agent.state, autoRetry, onRetry]);

  const toggleMicrophone = useCallback(async () => {
    await localParticipant.setMicrophoneEnabled(!isMicrophoneEnabled);
  }, [isMicrophoneEnabled, localParticipant]);

  const submitText = useCallback(async () => {
    const text = draft.trim();
    if (!text || isSending) return;
    setDraft("");
    await send(text);
  }, [draft, isSending, send]);

  return (
    <div className="flex h-full min-h-[560px] w-full flex-col rounded-3xl bg-white p-5 shadow-2xl dark:bg-slate-950">
      <RoomAudioRenderer muted={speakerMuted} />

      <div className="text-center">
        <p className="text-xs font-bold uppercase tracking-[0.22em] text-[#008F88]">LiveKit Voice Agent</p>
        <h2 className="mt-2 text-xl font-bold text-slate-900 dark:text-white">Tổng đài AloSM</h2>
        <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">{stateLabels[agent.state]}</p>
        {agent.failureReasons?.length ? (
          <div className="mt-2">
            <p className="text-sm text-rose-600">{agent.failureReasons.join("; ")}</p>
            <button
              type="button"
              onClick={onRetry}
              disabled={autoRetry}
              className="mt-3 rounded-xl bg-[#00A99D] px-4 py-2 text-sm font-semibold text-white"
            >
              {autoRetry ? "Đang tự tạo lại cuộc gọi…" : "Tạo lại cuộc gọi"}
            </button>
          </div>
        ) : null}
      </div>

      {bookingState ? (
        <div className="mt-4 grid grid-cols-2 gap-2 rounded-2xl border border-emerald-100 bg-emerald-50 p-3 text-xs text-slate-700 dark:border-emerald-900/50 dark:bg-emerald-950/20 dark:text-slate-200">
          {bookingState.recovered ? (
            <p className="col-span-2 font-semibold text-emerald-700 dark:text-emerald-300">
              Đã khôi phục yêu cầu đặt xe trước đó.
            </p>
          ) : null}
          <p><span className="font-semibold">Điểm đón:</span> {bookingState.pickup?.display_name ?? "Chưa chọn"}</p>
          <p><span className="font-semibold">Điểm đến:</span> {bookingState.destination?.display_name ?? "Chưa chọn"}</p>
          <p><span className="font-semibold">Loại xe:</span> {bookingState.vehicle_type ?? "Chưa chọn"}</p>
          <p>
            <span className="font-semibold">Giá dự kiến:</span>{" "}
            {bookingState.quote
              ? `${bookingState.quote.fare_amount.toLocaleString("vi-VN")} ${bookingState.quote.currency}`
              : "Chưa có"}
          </p>
          <p><span className="font-semibold">Xác nhận:</span> {bookingState.confirmation_status}</p>
          <p><span className="font-semibold">Mã chuyến:</span> {bookingState.booking?.booking_id ?? "Chưa tạo"}</p>
          {bookingState.failure ? (
            <p className="col-span-2 rounded-lg bg-amber-100 p-2 text-amber-900 dark:bg-amber-950/50 dark:text-amber-100">
              {bookingState.failure.message}
              {bookingState.failure.fallback_action === "repeat_or_text"
                ? " Bạn có thể nói lại hoặc nhập nội dung bên dưới."
                : ""}
            </p>
          ) : null}
          {bookingState.handoff ? (
            <p className="col-span-2 font-semibold text-[#008F88]">
              Đã chuyển tổng đài viên: {bookingState.handoff.handoff_id}
            </p>
          ) : null}
        </div>
      ) : null}

      <div className="mt-5 min-h-0 flex-1 space-y-3 overflow-y-auto rounded-2xl bg-slate-50 p-4 dark:bg-white/5">
        {messages.length === 0 ? (
          <p className="text-center text-sm text-slate-400">Transcript realtime sẽ xuất hiện tại đây.</p>
        ) : (
          messages.map((item) => {
            const isUser = item.type === "userTranscript" || item.from?.identity === localParticipant.identity;
            const rewrite = item.type === "userTranscript"
              ? transcriptRewrites[item.id]
                ?? Object.values(transcriptRewrites).find((candidate) => candidate.raw_text === item.message)
              : undefined;
            return (
              <div key={item.id} className={`flex ${isUser ? "justify-end" : "justify-start"}`}>
                {item.type === "userTranscript" ? (
                  <UserTranscriptBubble rawText={item.message} rewrite={rewrite} />
                ) : (
                  <p
                    className={`max-w-[85%] rounded-2xl px-4 py-2.5 text-sm ${
                      isUser
                        ? "bg-[#007F76] text-white"
                        : "bg-white text-slate-700 shadow-sm dark:bg-white/10 dark:text-slate-100"
                    }`}
                  >
                    {item.message}
                  </p>
                )}
              </div>
            );
          })
        )}
      </div>

      <div className="mt-4 flex gap-2">
        <input
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter") void submitText();
          }}
          placeholder="Fallback nhập tay khi STT lỗi"
          className="min-w-0 flex-1 rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm outline-none focus:border-[#00A99D] dark:border-white/10 dark:bg-white/5 dark:text-white"
        />
        <button
          type="button"
          onClick={() => void submitText()}
          disabled={!draft.trim() || isSending}
          className="grid h-10 w-10 place-items-center rounded-xl bg-[#00A99D] text-white disabled:opacity-40"
          aria-label="Gửi tin nhắn"
        >
          <Send className="h-4 w-4" />
        </button>
      </div>

      <div className="mt-5 flex items-center justify-center gap-5">
        <button
          type="button"
          onClick={() => setSpeakerMuted((value) => !value)}
          className="grid h-12 w-12 place-items-center rounded-full bg-slate-100 text-slate-700 dark:bg-white/10 dark:text-white"
          aria-label={speakerMuted ? "Bật loa" : "Tắt loa"}
        >
          {speakerMuted ? <VolumeX className="h-5 w-5" /> : <Volume2 className="h-5 w-5" />}
        </button>
        <button
          type="button"
          onClick={() => void toggleMicrophone()}
          className={`grid h-14 w-14 place-items-center rounded-full text-white ${
            isMicrophoneEnabled ? "bg-[#00A99D]" : "bg-slate-500"
          }`}
          aria-label={isMicrophoneEnabled ? "Tắt micro" : "Bật micro"}
        >
          {isMicrophoneEnabled ? <Mic className="h-6 w-6" /> : <MicOff className="h-6 w-6" />}
        </button>
        <button
          type="button"
          onClick={onClose}
          className="grid h-12 w-12 place-items-center rounded-full bg-rose-600 text-white"
          aria-label="Kết thúc cuộc gọi"
        >
          <PhoneOff className="h-5 w-5" />
        </button>
      </div>
    </div>
  );
}

function LiveKitSessionAttempt({
  callInstanceId,
  onClose,
  onRetry,
  autoRetry,
}: {
  callInstanceId: string;
  onClose: () => void;
  onRetry: () => void;
  autoRetry: boolean;
}) {
  const [connectionError, setConnectionError] = useState<string | null>(null);
  const tokenSource = useMemo(() => createAloSMTokenSource(callInstanceId), [callInstanceId]);
  const session = useSession(tokenSource, {
    agentName: LIVEKIT_AGENT_NAME,
    participantAttributes: { "alosm.call_id": callInstanceId },
    agentConnectTimeoutMilliseconds: 20_000,
  });

  const start = session.start;
  const end = session.end;
  const wasConnectedRef = useRef(false);
  const intentionalDisconnectRef = useRef(false);

  useEffect(() => {
    let active = true;
    void start({ tracks: { microphone: { enabled: true } } }).catch((error: unknown) => {
      if (active) setConnectionError(error instanceof Error ? error.message : "Không thể kết nối LiveKit.");
    });
    return () => {
      active = false;
      void end();
    };
  }, [end, start]);

  useEffect(() => {
    if (session.isConnected) {
      wasConnectedRef.current = true;
      return;
    }
    if (wasConnectedRef.current && !intentionalDisconnectRef.current) {
      wasConnectedRef.current = false;
      onClose();
    }
  }, [onClose, session.isConnected]);

  const endCall = useCallback(() => {
    intentionalDisconnectRef.current = true;
    void end().finally(onClose);
  }, [end, onClose]);

  const retryCall = useCallback(() => {
    intentionalDisconnectRef.current = true;
    void end().finally(onRetry);
  }, [end, onRetry]);

  if (connectionError) {
    return (
      <div className="rounded-3xl bg-white p-6 text-center shadow-2xl dark:bg-slate-950">
        <p className="text-sm text-rose-600">{connectionError}</p>
        <div className="mt-4 flex justify-center gap-3">
          <button type="button" onClick={retryCall} className="rounded-xl bg-[#00A99D] px-4 py-2 text-white">
            Tạo lại cuộc gọi
          </button>
          <button type="button" onClick={endCall} className="rounded-xl bg-slate-900 px-4 py-2 text-white">
            Đóng
          </button>
        </div>
      </div>
    );
  }

  return (
    <SessionProvider session={session}>
      <LiveKitCallContent onClose={endCall} onRetry={retryCall} autoRetry={autoRetry} />
    </SessionProvider>
  );
}

export const LiveKitVoiceSession: React.FC = () => {
  const { endSession, livekitCallInstanceId } = useVoiceAssistant();
  const consentKey = `alosm_voice_consent_v${CURRENT_POLICY_VERSION}`;
  const [consented, setConsented] = useState(() => localStorage.getItem(consentKey) === "accepted");
  const [attempt, setAttempt] = useState(() => ({
    id: 0,
    callInstanceId: livekitCallInstanceId ?? crypto.randomUUID(),
  }));

  const retry = useCallback(() => {
    const callInstanceId = crypto.randomUUID();
    void prepareAloSMCall(callInstanceId).catch(() => undefined);
    setAttempt((current) => ({ id: current.id + 1, callInstanceId }));
  }, []);

  useEffect(
    () => () => discardPreparedAloSMCall(attempt.callInstanceId),
    [attempt.callInstanceId],
  );

  if (!consented) {
    return (
      <div className="rounded-3xl bg-white p-6 text-center shadow-2xl dark:bg-slate-950">
        <h2 className="text-lg font-bold text-slate-900 dark:text-white">Cho phép xử lý âm thanh</h2>
        <p className="mt-3 text-sm text-slate-500">
          AloSM cần dùng micro và transcript realtime để thực hiện cuộc gọi. Audio recording vẫn đang tắt mặc định.
        </p>
        <button
          type="button"
          onClick={() => {
            void prepareAloSMCall(attempt.callInstanceId).catch(() => undefined);
            localStorage.setItem(consentKey, "accepted");
            setConsented(true);
          }}
          className="mt-5 rounded-xl bg-[#00A99D] px-5 py-2.5 font-semibold text-white"
        >
          Đồng ý và bắt đầu
        </button>
      </div>
    );
  }

  return (
    <LiveKitSessionAttempt
      key={attempt.id}
      callInstanceId={attempt.callInstanceId}
      onClose={() => void endSession()}
      onRetry={retry}
      autoRetry={attempt.id === 0}
    />
  );
};
