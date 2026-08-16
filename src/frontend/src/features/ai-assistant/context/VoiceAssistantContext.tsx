import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { getCurrentUser } from "@/features/auth/api";
import { redirectToLoginIfUnauthorized } from "@/features/auth/sessionGuard";
import { getAccessToken, getSessionId, getUserName, saveAuthSession } from "@/features/auth/storage";
import {
  createRideSession,
  endRideSession,
  getRideSession,
  resetRideConversation,
  sendRideMessage,
  submitSessionFeedback,
} from "@/features/ride/api";
import type { BookingLifecycleStatus, BookingProgress, RideTurn } from "@/features/ride/api";
import {
  playAudioBlob,
  playBase64Audio,
  sendVoiceTurn,
  speakWithBrowserTts,
  stopVoicePlayback,
  synthesizeSpeech,
} from "@/features/voice/api";
import type { CompletedBooking } from "@/features/ai-assistant/components/BookingSuccessPanel";
import {
  VoiceAssistantContext,
  type AssistantStatus,
  type Message,
  type VoiceAssistantValue,
} from "./voice-assistant-context";

function buildWelcomeMessage(userName: string): string {
  return `Xin chào ${userName}! Em là trợ lý AloSM, rất vui được đồng hành cùng anh/chị hôm nay 😊 Anh/chị đang cần em hỗ trợ gì ạ — đặt xe, theo dõi chuyến đi, hay có thắc mắc nào khác không?`;
}

export const VoiceAssistantProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const navigate = useNavigate();

  const [isOpen, setIsOpen] = useState(false);
  const [isConversationOpen, setIsConversationOpen] = useState(false);
  const [status, setStatus] = useState<AssistantStatus>("connecting");
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [sessionEnded, setSessionEnded] = useState(false);
  const [messages, setMessages] = useState<Message[]>([
    { id: "welcome", role: "assistant", text: buildWelcomeMessage(getUserName()) },
  ]);
  const [notice, setNotice] = useState<string | null>(null);
  const [draft, setDraft] = useState("");
  const [bookingProgress, setBookingProgress] = useState<BookingProgress | null>(null);
  const [lifecycleStatus, setLifecycleStatus] = useState<BookingLifecycleStatus | null>(null);
  const [completedBooking, setCompletedBooking] = useState<CompletedBooking | null>(null);
  const [showConfirmationModal, setShowConfirmationModal] = useState(false);
  const [showSuccessModal, setShowSuccessModal] = useState(false);
  const [isSubmittingRating, setIsSubmittingRating] = useState(false);
  const [isHistoryOpen, setIsHistoryOpen] = useState(false);
  const [transcriptSessionId, setTranscriptSessionId] = useState<string | null>(null);
  const [isMuted, setIsMuted] = useState(false);
  const isMutedRef = useRef(isMuted);
  isMutedRef.current = isMuted;

  // Chặn gửi trùng khi đang xử lý lượt trước — đọc qua ref (không phải state) vì
  // được dùng ngay trong closure của sendText/handleVoiceRecorded, tránh phải liệt kê
  // `status` vào dependency array chỉ để đọc giá trị tức thời.
  const statusRef = useRef(status);
  statusRef.current = status;

  const resetConversationUi = useCallback(() => {
    setMessages([{ id: "welcome", role: "assistant", text: buildWelcomeMessage(getUserName()) }]);
    setDraft("");
    setBookingProgress(null);
    setLifecycleStatus(null);
    setCompletedBooking(null);
    setShowConfirmationModal(false);
    setShowSuccessModal(false);
    setSessionEnded(false);
    setNotice(null);
  }, []);

  const applyTurnResult = useCallback((result: RideTurn) => {
    if (result.state?.booking_progress !== undefined) {
      setBookingProgress(result.state.booking_progress ?? null);
    }
    const nextLifecycle = result.state?.booking_lifecycle_status ?? result.booking?.lifecycle_status ?? null;
    if (nextLifecycle) setLifecycleStatus(nextLifecycle);

    if (nextLifecycle === "SUCCESS" && result.booking) {
      setCompletedBooking({
        booking_id: result.booking.booking_id,
        estimated_fare: result.booking.estimated_fare,
        lifecycle_status: "SUCCESS",
      });
      setShowConfirmationModal(false);
      setShowSuccessModal(true);
      return;
    }
    if (nextLifecycle === "FAILED") {
      setCompletedBooking({
        booking_id: result.booking?.booking_id ?? "",
        estimated_fare: result.booking?.estimated_fare ?? 0,
        lifecycle_status: "FAILED",
      });
      setShowConfirmationModal(false);
      setShowSuccessModal(true);
      return;
    }
    // Tín hiệu THẬT (không suy đoán) rằng agent đã thu thập đủ thông tin và đang chờ
    // khách xác nhận — đúng src/agents/workflows/booking_models.py::BookingStep.CONFIRM.
    const readyToConfirm =
      result.state?.current_workflow === "RIDE_BOOKING" && result.state?.current_step === "CONFIRM";
    setShowConfirmationModal(Boolean(readyToConfirm));
  }, []);

  const handleEndOfTurnActions = useCallback(
    (result: RideTurn) => {
      if (result.action === "HANDOFF") setNotice("Yêu cầu đã được chuyển đến tổng đài viên.");
      if (result.action === "END_SESSION") {
        // Agent tự kết thúc hội thoại (vd khách nói "hủy"/"thôi") — chỉ reset PHIÊN
        // HỘI THOẠI, không đăng xuất tài khoản (khác hẳn 2 việc, xem endSession()).
        setSessionId(null);
        localStorage.removeItem("alosm_session_id");
        setSessionEnded(true);
        setShowConfirmationModal(false);
        setNotice("Phiên hội thoại đã kết thúc. Nhấn “Bắt đầu phiên mới” để đặt xe tiếp.");
      }
    },
    [],
  );

  // Toàn bộ popup giờ LUÔN là cuộc gọi thoại (không còn chat im lặng) — mọi câu trả
  // lời của agent, dù đến từ lượt gõ chữ (openWithPrefill/confirmBooking) hay lượt
  // nói, đều được đọc to như đang thật sự nghe tổng đài viên trả lời, trừ khi người
  // dùng tự tắt loa (isMuted).
  const speakReply = useCallback(async (
    text: string,
    audioBase64?: string | null,
    audioMimeType?: string,
    reviewContext?: { bookingConfirmed?: boolean; action?: string },
    serverTtsUnavailable = false,
  ) => {
    if (isMutedRef.current) return;
    setStatus("speaking");
    if (audioBase64) {
      try {
        await playBase64Audio(audioBase64, audioMimeType ?? "audio/mpeg");
        return;
      } catch {
        setNotice("Audio phản hồi lỗi, hệ thống đang tổng hợp lại bằng giọng dự phòng.");
      }
    }
    if (serverTtsUnavailable) {
      setNotice("Máy chủ giọng nói đang bận, đang dùng giọng đọc dự phòng của trình duyệt.");
      await speakWithBrowserTts(text);
      return;
    }
    try {
      const synthesized = await synthesizeSpeech(text, reviewContext);
      if (synthesized.fallbackUsed) {
        setNotice(`Đang sử dụng giọng dự phòng ${synthesized.voice}.`);
      }
      await playAudioBlob(synthesized.blob);
    } catch {
      setNotice("Máy chủ giọng nói đang bận, đang dùng giọng đọc dự phòng của trình duyệt.");
      await speakWithBrowserTts(text);
    }
  }, []);

  const sendText = useCallback(
    async (value: string) => {
      const message = value.trim();
      if (!message || !sessionId || sessionEnded || statusRef.current === "processing") return;
      setMessages((items) => [...items, { id: `user-${Date.now()}`, role: "user", text: message }]);
      setStatus("processing");
      setNotice(null);
      try {
        const result = await sendRideMessage(sessionId, message, "TEXT");
        setMessages((items) => [...items, { id: result.message_id, role: "assistant", text: result.message }]);
        applyTurnResult(result);
        handleEndOfTurnActions(result);
        // `/messages` (gõ chữ) không trả audio_base64 (chỉ `/voice/turn` mới có, từ
        // OpenAI TTS thật) — dùng giọng đọc trình duyệt cho lượt gõ chữ, vẫn đọc to
        // như 1 cuộc gọi thật, không im lặng như chatbot nhắn tin nữa.
        await speakReply(result.message, null, undefined, {
          bookingConfirmed: result.state?.booking_lifecycle_status === "SUCCESS",
          action: result.action,
        });
        setStatus("idle");
      } catch (error) {
        setStatus("error");
        if (redirectToLoginIfUnauthorized(error, navigate)) return;
        setNotice(error instanceof Error ? error.message : "Không thể gửi tin nhắn. Vui lòng thử lại.");
      }
    },
    [sessionId, sessionEnded, applyTurnResult, handleEndOfTurnActions, navigate, speakReply],
  );

  const handleVoiceRecorded = useCallback(
    async (audio: Blob) => {
      if (!sessionId || sessionEnded || statusRef.current === "processing") return;
      setStatus("processing");
      setNotice(null);
      try {
        const result = await sendVoiceTurn(sessionId, audio);
        setMessages((items) => [
          ...items,
          {
            id: `user-${Date.now()}`,
            role: "user",
            text: result.transcript,
            transcriptRewrite: result.transcript_rewrite ?? undefined,
          },
          { id: result.message_id, role: "assistant", text: result.message },
        ]);
        applyTurnResult(result);
        handleEndOfTurnActions(result);
        await speakReply(result.message, result.audio_base64, result.audio_mime_type, {
          bookingConfirmed: result.state?.booking_lifecycle_status === "SUCCESS",
          action: result.action,
        }, result.tts_provider === "unavailable");
        setStatus("idle");
      } catch (error) {
        setStatus("error");
        if (redirectToLoginIfUnauthorized(error, navigate)) return;
        setNotice(error instanceof Error ? error.message : "Không thể xử lý giọng nói. Vui lòng thử lại.");
      }
    },
    [sessionId, sessionEnded, applyTurnResult, handleEndOfTurnActions, navigate, speakReply],
  );

  // Khởi tạo phiên hội thoại 1 LẦN khi Provider mount (ở AppLayout — ngay sau đăng
  // nhập), không phải mỗi lần mở popup — để đóng/mở popup qua lại giữa các trang
  // không làm mất hội thoại đang dở (Scenario 6, mục 26).
  useEffect(() => {
    let cancelled = false;

    const bootstrapSession = async () => {
      setStatus("connecting");
      const cachedSessionId = getSessionId();
      if (cachedSessionId) {
        try {
          await getRideSession(cachedSessionId);
          if (cancelled) return;
          setSessionId(cachedSessionId);
          setStatus("idle");
          return;
        } catch (error) {
          if (cancelled) return;
          if (redirectToLoginIfUnauthorized(error, navigate)) return;
        }
      }

      try {
        const user = await getCurrentUser();
        if (cancelled) return;
        if (user.session_id) {
          saveAuthSession({
            access_token: getAccessToken() || "",
            user_id: user.user_id,
            full_name: user.full_name,
            session_id: user.session_id,
          });
          setSessionId(user.session_id);
          setStatus("idle");
          return;
        }
        const session = await createRideSession();
        if (cancelled) return;
        saveAuthSession({
          access_token: getAccessToken() || "",
          user_id: user.user_id,
          full_name: user.full_name,
          session_id: session.session_id,
        });
        setSessionId(session.session_id);
        setStatus("idle");
      } catch (error) {
        if (cancelled) return;
        if (redirectToLoginIfUnauthorized(error, navigate)) return;
        setStatus("error");
        setNotice(error instanceof Error ? error.message : "Không thể khởi tạo phiên hội thoại.");
      }
    };

    bootstrapSession();
    return () => {
      cancelled = true;
    };
    // `navigate` từ useNavigate() ổn định giữa các lần render (không đổi tham chiếu)
    // nên liệt kê đủ vào dependency array vẫn chỉ chạy đúng 1 lần lúc Provider mount —
    // không cần eslint-disable, giống hệt effect bootstrap gốc ở AssistantPage cũ.
  }, [navigate]);

  const open = useCallback(() => setIsOpen(true), []);
  const close = useCallback(() => {
    setIsConversationOpen(false);
    setIsOpen(false);
  }, []);
  const openConversation = useCallback(() => setIsConversationOpen(true), []);
  const closeConversation = useCallback(() => setIsConversationOpen(false), []);

  const openWithPrefill = useCallback((prefill: string) => {
    setDraft(prefill);
    setIsConversationOpen(true);
    setIsOpen(true);
  }, []);

  const confirmBooking = useCallback(async () => {
    // Gửi đúng 1 lượt hội thoại thật ("Xác nhận đặt xe" khớp _CONFIRM_TERMS ở
    // src/agents/understanding/rules.py) — KHÔNG có endpoint tạo booking riêng ở
    // frontend. Đặt xe luôn đi qua agent thật, không bao giờ tạo trực tiếp từ UI.
    await sendText("Xác nhận đặt xe");
  }, [sendText]);

  const dismissConfirmation = useCallback(() => setShowConfirmationModal(false), []);
  const closeSuccessModal = useCallback(() => setShowSuccessModal(false), []);

  const submitRating = useCallback(
    async (rating: number) => {
      if (!sessionId) return;
      setIsSubmittingRating(true);
      try {
        await submitSessionFeedback(sessionId, rating);
      } catch (error) {
        setNotice(error instanceof Error ? error.message : "Không thể gửi đánh giá.");
      } finally {
        setIsSubmittingRating(false);
      }
    },
    [sessionId],
  );

  const endSession = useCallback(async () => {
    if (sessionId) {
      await endRideSession(sessionId).catch(() => undefined);
    }
    setSessionId(null);
    localStorage.removeItem("alosm_session_id");
    setSessionEnded(true);
    setShowConfirmationModal(false);
    setShowSuccessModal(false);
    setNotice("Phiên hội thoại đã kết thúc. Nhấn “Bắt đầu phiên mới” để đặt xe tiếp.");
  }, [sessionId]);

  const newSession = useCallback(async () => {
    // `agent_state` (bao gồm conversation_history) chỉ thuộc về một session ở
    // backend. Kết thúc session hiện tại rồi tạo ID mới là reset memory thật, không
    // chỉ là xóa bubble ở UI.
    if (sessionId) {
      await endRideSession(sessionId).catch(() => undefined);
    }
    try {
      stopVoicePlayback();
      setStatus("connecting");
      const user = await getCurrentUser();
      const session = await createRideSession();
      saveAuthSession({
        access_token: getAccessToken() || "",
        user_id: user.user_id,
        full_name: user.full_name,
        session_id: session.session_id,
      });
      setSessionId(session.session_id);
      setStatus("idle");
      resetConversationUi();
    } catch (error) {
      if (redirectToLoginIfUnauthorized(error, navigate)) return;
      setSessionId(null);
      setSessionEnded(true);
      setShowConfirmationModal(false);
      setShowSuccessModal(false);
      setStatus("error");
      setNotice(error instanceof Error ? error.message : "Không thể tạo phiên mới.");
    }
  }, [sessionId, navigate, resetConversationUi]);

  const resetConversation = useCallback(async () => {
    if (!sessionId || sessionEnded || statusRef.current === "processing") return;
    try {
      stopVoicePlayback();
      setStatus("processing");
      await resetRideConversation(sessionId);
      resetConversationUi();
      setStatus("idle");
    } catch (error) {
      if (redirectToLoginIfUnauthorized(error, navigate)) return;
      setStatus("error");
      setNotice(error instanceof Error ? error.message : "Không thể đặt lại cuộc hội thoại.");
    }
  }, [sessionId, sessionEnded, navigate, resetConversationUi]);

  const openHistory = useCallback(() => setIsHistoryOpen(true), []);
  const closeHistory = useCallback(() => setIsHistoryOpen(false), []);
  const openTranscript = useCallback((id: string) => setTranscriptSessionId(id), []);
  const closeTranscript = useCallback(() => setTranscriptSessionId(null), []);
  const toggleMuted = useCallback(() => {
    setIsMuted((value) => {
      if (!value) stopVoicePlayback();
      return !value;
    });
  }, []);

  useEffect(() => () => stopVoicePlayback(), []);
  // Cho VoiceCallPanel báo lỗi ghi âm/micro qua đúng 1 kênh thông báo duy nhất
  // (`notice`) thay vì mỗi nơi tự vẽ 1 banner lỗi riêng.
  const reportError = useCallback((message: string) => {
    setStatus("error");
    setNotice(message);
  }, []);

  const value = useMemo<VoiceAssistantValue>(
    () => ({
      isOpen,
      open,
      close,
      isConversationOpen,
      openConversation,
      closeConversation,
      openWithPrefill,
      draft,
      setDraft,
      status,
      messages,
      notice,
      sessionId,
      sessionEnded,
      sendText,
      handleVoiceRecorded,
      endSession,
      newSession,
      resetConversation,
      bookingProgress,
      lifecycleStatus,
      showConfirmationModal,
      confirmBooking,
      dismissConfirmation,
      showSuccessModal,
      completedBooking,
      closeSuccessModal,
      submitRating,
      isSubmittingRating,
      isHistoryOpen,
      openHistory,
      closeHistory,
      transcriptSessionId,
      openTranscript,
      closeTranscript,
      isMuted,
      toggleMuted,
      reportError,
    }),
    [
      isOpen,
      open,
      close,
      isConversationOpen,
      openConversation,
      closeConversation,
      openWithPrefill,
      draft,
      setDraft,
      status,
      messages,
      notice,
      sessionId,
      sessionEnded,
      sendText,
      handleVoiceRecorded,
      endSession,
      newSession,
      resetConversation,
      bookingProgress,
      lifecycleStatus,
      showConfirmationModal,
      confirmBooking,
      dismissConfirmation,
      showSuccessModal,
      completedBooking,
      closeSuccessModal,
      submitRating,
      isSubmittingRating,
      isHistoryOpen,
      openHistory,
      closeHistory,
      transcriptSessionId,
      openTranscript,
      closeTranscript,
      isMuted,
      toggleMuted,
      reportError,
    ],
  );

  return <VoiceAssistantContext.Provider value={value}>{children}</VoiceAssistantContext.Provider>;
};
