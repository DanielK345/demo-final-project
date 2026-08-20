import React, { useCallback, useEffect, useMemo, useState } from "react";
import {
  RoomAudioRenderer,
  SessionProvider,
  useAgent,
  useDataChannel,
  useLocalParticipant,
  useSession,
  useSessionMessages,
} from "@livekit/components-react";
import { Mic, MicOff, PhoneOff, Send, Volume2, VolumeX } from "lucide-react";
import { getCurrentUser } from "@/features/auth/api";
import { CURRENT_POLICY_VERSION } from "@/features/policies/api";
import { useVoiceAssistant } from "@/features/ai-assistant/context/useVoiceAssistant";
import { getRideSession } from "@/features/ride/api";
import { createAloSMTokenSource, LIVEKIT_AGENT_NAME } from "./tokenSource";
import { BOOKING_STATE_TOPIC, type BookingState } from "./contracts";

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
  const { message: bookingStateMessage } = useDataChannel(BOOKING_STATE_TOPIC);
  const agentFailure = agent.failureReasons?.join("; ") ?? "";

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
    // StrictMode intentionally runs the session cleanup once in development.
    // That transient end may briefly expose `failed` without a real LiveKit agent
    // failure. Retrying it creates a second room. Only retry actionable failures
    // reported by the Session API itself.
    if (!autoRetry || agent.state !== "failed" || !agentFailure) return;
    const timeoutId = window.setTimeout(onRetry, 1_500);
    return () => window.clearTimeout(timeoutId);
  }, [agent.state, agentFailure, autoRetry, onRetry]);

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
            return (
              <div key={item.id} className={`flex ${isUser ? "justify-end" : "justify-start"}`}>
                <p
                  className={`max-w-[85%] rounded-2xl px-4 py-2.5 text-sm ${
                    isUser
                      ? "bg-[#00A99D] text-white"
                      : "bg-white text-slate-700 shadow-sm dark:bg-white/10 dark:text-slate-100"
                  }`}
                >
                  {item.message}
                </p>
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
  onClose,
  onRetry,
  autoRetry,
}: {
  onClose: () => void;
  onRetry: () => void;
  autoRetry: boolean;
}) {
  const [connectionError, setConnectionError] = useState<string | null>(null);
  const callInstanceId = useMemo(() => crypto.randomUUID(), []);
  const tokenSource = useMemo(() => createAloSMTokenSource(), []);
  const session = useSession(tokenSource, {
    agentName: LIVEKIT_AGENT_NAME,
    participantAttributes: { "alosm.call_id": callInstanceId },
    agentConnectTimeoutMilliseconds: 20_000,
  });

  const start = session.start;
  const end = session.end;

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

  const endCall = useCallback(() => {
    void end().finally(onClose);
  }, [end, onClose]);

  const retryCall = useCallback(() => {
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
  const { close, sessionId, newSession } = useVoiceAssistant();
  const consentKey = `alosm_voice_consent_v${CURRENT_POLICY_VERSION}`;
  const [consented, setConsented] = useState(() => localStorage.getItem(consentKey) === "accepted");
  const [attempt, setAttempt] = useState(0);
  const [resumeState, setResumeState] = useState<"checking" | "prompt" | "ready" | "needs-new" | "error">(
    "checking",
  );
  const [resumeError, setResumeError] = useState<string | null>(null);

  useEffect(() => {
    if (!consented) return;
    if (!sessionId) {
      setResumeState("needs-new");
      return;
    }
    let active = true;
    setResumeState("checking");
    setResumeError(null);
    void (async () => {
      // The provider may stay mounted while another tab/call rebinds this token.
      // Check the authoritative binding before touching the cached session so a
      // normal stale-cache recovery does not generate a backend 409.
      const user = await getCurrentUser();
      if (!active) return;
      if (!user.session_id || user.session_id !== sessionId) {
        setResumeState("needs-new");
        return;
      }

      const session = await getRideSession(sessionId);
      if (!active) return;
      if (session.status !== "ACTIVE" || session.voice_session_terminal) {
        setResumeState("needs-new");
      } else if (session.has_resumable_voice_state) {
        setResumeState("prompt");
      } else {
        setResumeState("ready");
      }
    })()
      .catch((error: unknown) => {
        if (!active) return;
        setResumeError(error instanceof Error ? error.message : "Không thể kiểm tra phiên trước.");
        setResumeState("error");
      });
    return () => {
      active = false;
    };
  }, [consented, sessionId]);

  const startNewSession = useCallback(async () => {
    setResumeState("checking");
    setResumeError(null);
    try {
      const created = await newSession();
      if (!created) {
        setResumeError("Không thể tạo phiên mới.");
        setResumeState("error");
      }
    } catch (error) {
      setResumeError(error instanceof Error ? error.message : "Không thể tạo phiên mới.");
      setResumeState("error");
    }
  }, [newSession]);

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

  if (resumeState === "checking") {
    return (
      <div className="flex h-full items-center justify-center rounded-3xl bg-white p-6 text-center dark:bg-slate-950">
        <p className="text-sm text-slate-500 dark:text-slate-400">Đang chuẩn bị phiên cuộc gọi…</p>
      </div>
    );
  }

  if (resumeState === "prompt") {
    return (
      <div className="flex h-full flex-col items-center justify-center rounded-3xl bg-white p-6 text-center dark:bg-slate-950">
        <h2 className="text-lg font-bold text-slate-900 dark:text-white">Tiếp tục chuyến đang đặt?</h2>
        <p className="mt-2 max-w-sm text-sm text-slate-500 dark:text-slate-400">
          Phiên trước còn thông tin đặt xe chưa hoàn tất. Bạn có thể tiếp tục hoặc bắt đầu một phiên riêng.
        </p>
        <div className="mt-5 flex flex-wrap justify-center gap-3">
          <button
            type="button"
            onClick={() => setResumeState("ready")}
            className="rounded-xl bg-[#00A99D] px-5 py-2.5 font-semibold text-white"
          >
            Tiếp tục phiên trước
          </button>
          <button
            type="button"
            onClick={() => void startNewSession()}
            className="rounded-xl border border-slate-300 px-5 py-2.5 font-semibold text-slate-700 dark:border-white/20 dark:text-white"
          >
            Bắt đầu cuộc gọi mới
          </button>
        </div>
      </div>
    );
  }

  if (resumeState === "needs-new" || resumeState === "error") {
    return (
      <div className="flex h-full flex-col items-center justify-center rounded-3xl bg-white p-6 text-center dark:bg-slate-950">
        <h2 className="text-lg font-bold text-slate-900 dark:text-white">
          {resumeState === "error" ? "Không thể kiểm tra phiên" : "Phiên trước đã kết thúc"}
        </h2>
        {resumeError ? <p className="mt-2 text-sm text-rose-600">{resumeError}</p> : null}
        <button
          type="button"
          onClick={() => void startNewSession()}
          className="mt-5 rounded-xl bg-[#00A99D] px-5 py-2.5 font-semibold text-white"
        >
          Bắt đầu cuộc gọi mới
        </button>
      </div>
    );
  }

  return (
    <LiveKitSessionAttempt
      key={attempt}
      onClose={close}
      onRetry={() => setAttempt((value) => value + 1)}
      autoRetry={attempt === 0}
    />
  );
};
