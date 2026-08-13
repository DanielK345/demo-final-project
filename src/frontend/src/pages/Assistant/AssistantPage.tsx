import React, { useCallback, useEffect, useState } from "react";
import { Bot, Home, LogOut, Mic, Send, Square, Volume2 } from "lucide-react";
import { NavLink, useNavigate } from "react-router-dom";
import { getCurrentUser } from "@/features/auth/api";
import { redirectToLoginIfUnauthorized } from "@/features/auth/sessionGuard";
import {
  clearAuthSession,
  getAccessToken,
  getSessionId,
  getUserName,
  saveAuthSession,
} from "@/features/auth/storage";
import { BookingSuccessPanel } from "@/features/ai-assistant/components/BookingSuccessPanel";
import { LlmStatusNote } from "@/features/ai-assistant/components/LlmStatusNote";
import { BookingProgressSidebar } from "@/features/ai-assistant/components/BookingProgressSidebar";
import {
  createRideSession,
  endRideSession,
  getRideSession,
  sendRideMessage,
  submitSessionFeedback,
} from "@/features/ride/api";
import type { BookingLifecycleStatus, BookingProgress, RideBooking, RideTurn } from "@/features/ride/api";
import { playBase64Audio, sendVoiceTurn, speakWithBrowser } from "@/features/voice/api";
import { useVoiceRecorder } from "@/features/voice/useVoiceRecorder";

type Message = { id: string; role: "user" | "assistant"; text: string };

const WELCOME_MESSAGE =
  "Xin chào! Em chỉ cần điểm đón, điểm đến và loại xe (4 chỗ, 7 chỗ hoặc hạng sang). Em không hỏi số điện thoại, email hay thông tin riêng tư.";

export const AssistantPage: React.FC = () => {
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [messages, setMessages] = useState<Message[]>([
    { id: "welcome", role: "assistant", text: WELCOME_MESSAGE },
  ]);
  const [text, setText] = useState("");
  const [isSending, setIsSending] = useState(false);
  const [isListening, setIsListening] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const [bookingProgress, setBookingProgress] = useState<BookingProgress | null>(null);
  const [lifecycleStatus, setLifecycleStatus] = useState<BookingLifecycleStatus | null>(null);
  const [completedBooking, setCompletedBooking] = useState<RideBooking | null>(null);
  const [showOutcomePanel, setShowOutcomePanel] = useState(false);
  const [isSubmittingRating, setIsSubmittingRating] = useState(false);
  const [sessionEnded, setSessionEnded] = useState(false);
  const navigate = useNavigate();
  const userName = getUserName();

  const resetConversationUi = useCallback(() => {
    setMessages([{ id: "welcome", role: "assistant", text: WELCOME_MESSAGE }]);
    setBookingProgress(null);
    setLifecycleStatus(null);
    setCompletedBooking(null);
    setShowOutcomePanel(false);
    setSessionEnded(false);
    setNotice(null);
  }, []);

  const applyTurnResult = useCallback((result: RideTurn) => {
    if (result.state?.booking_progress) {
      setBookingProgress(result.state.booking_progress);
    }
    const status =
      result.state?.booking_lifecycle_status ??
      result.booking?.lifecycle_status ??
      null;
    if (status) {
      setLifecycleStatus(status);
    }
    if (status === "SUCCESS" && result.booking) {
      setCompletedBooking(result.booking);
      setShowOutcomePanel(true);
    } else if (status === "FAILED") {
      setCompletedBooking({
        booking_id: result.booking?.booking_id ?? "",
        status: "FAILED",
        lifecycle_status: "FAILED",
        estimated_fare: result.booking?.estimated_fare ?? 0,
      });
      setShowOutcomePanel(true);
    }
  }, []);

  const handleVoiceRecorded = async (audio: Blob) => {
    if (!sessionId || isSending || sessionEnded) return;
    setIsSending(true);
    setNotice(null);
    if (lifecycleStatus !== "SUCCESS") {
      setLifecycleStatus("PENDING");
    }
    try {
      const result = await sendVoiceTurn(sessionId, audio);
      setMessages((items) => [
        ...items,
        { id: `user-${Date.now()}`, role: "user", text: result.transcript },
        { id: result.message_id, role: "assistant", text: result.message },
      ]);
      applyTurnResult(result as RideTurn);
      if (result.audio_base64) {
        await playBase64Audio(result.audio_base64, result.audio_mime_type);
      } else {
        speakWithBrowser(result.message);
      }
      if (result.action === "HANDOFF") setNotice("Yêu cầu đã được chuyển đến tổng đài viên.");
      if (result.action === "END_SESSION") {
        // Bug thật đã sửa: trước đây khi AGENT tự kết thúc hội thoại (vd khách nói
        // "hủy"/"thôi"), code này đăng xuất khỏi TÀI KHOẢN luôn (clearAuthSession +
        // về /login) — trong khi nút "Kết thúc phiên" tường minh (handleEndSession)
        // chỉ reset phiên hội thoại, KHÔNG đăng xuất tài khoản. 2 đường xử lý cùng 1
        // tình huống ("hội thoại kết thúc") lại khác hẳn nhau — không nhất quán, và
        // buộc khách đăng nhập lại chỉ vì nói "hủy" là quá tay. Đồng bộ lại theo đúng
        // hành vi của handleEndSession.
        setSessionId(null);
        localStorage.removeItem("alosm_session_id");
        setSessionEnded(true);
        setShowOutcomePanel(false);
        setNotice("Phiên hội thoại đã kết thúc. Nhấn “Bắt đầu phiên mới” để đặt xe tiếp.");
      }
    } catch (error) {
      setLifecycleStatus("FAILED");
      if (redirectToLoginIfUnauthorized(error, navigate)) return;
      setNotice(error instanceof Error ? error.message : "Không thể xử lý giọng nói.");
    } finally {
      setIsSending(false);
      setIsListening(false);
    }
  };

  const { toggleRecording } = useVoiceRecorder({
    onRecorded: handleVoiceRecorded,
    onError: (error) => {
      setIsListening(false);
      setNotice(error.message);
    },
  });

  useEffect(() => {
    let cancelled = false;

    const bootstrapSession = async () => {
      const cachedSessionId = getSessionId();
      if (cachedSessionId) {
        try {
          await getRideSession(cachedSessionId);
          if (cancelled) return;
          setSessionId(cachedSessionId);
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
      } catch (error) {
        if (cancelled) return;
        if (redirectToLoginIfUnauthorized(error, navigate)) return;
        setNotice(error instanceof Error ? error.message : "Không thể khởi tạo phiên hội thoại.");
      }
    };

    bootstrapSession();
    return () => {
      cancelled = true;
    };
  }, [navigate]);

  const send = async (value: string, source: "TEXT" | "VOICE" = "TEXT") => {
    const message = value.trim();
    if (!message || !sessionId || isSending || sessionEnded) return;
    setMessages((items) => [...items, { id: `user-${Date.now()}`, role: "user", text: message }]);
    setText("");
    setIsSending(true);
    if (lifecycleStatus !== "SUCCESS") {
      setLifecycleStatus("PENDING");
    }
    try {
      const result = await sendRideMessage(sessionId, message, source, source === "VOICE" ? 0.9 : undefined);
      setMessages((items) => [...items, { id: result.message_id, role: "assistant", text: result.message }]);
      applyTurnResult(result);
      speakWithBrowser(result.message);
      if (result.action === "HANDOFF") setNotice("Yêu cầu đã được chuyển đến tổng đài viên.");
      if (result.action === "END_SESSION") {
        // Bug thật đã sửa: trước đây khi AGENT tự kết thúc hội thoại (vd khách nói
        // "hủy"/"thôi"), code này đăng xuất khỏi TÀI KHOẢN luôn (clearAuthSession +
        // về /login) — trong khi nút "Kết thúc phiên" tường minh (handleEndSession)
        // chỉ reset phiên hội thoại, KHÔNG đăng xuất tài khoản. 2 đường xử lý cùng 1
        // tình huống ("hội thoại kết thúc") lại khác hẳn nhau — không nhất quán, và
        // buộc khách đăng nhập lại chỉ vì nói "hủy" là quá tay. Đồng bộ lại theo đúng
        // hành vi của handleEndSession.
        setSessionId(null);
        localStorage.removeItem("alosm_session_id");
        setSessionEnded(true);
        setShowOutcomePanel(false);
        setNotice("Phiên hội thoại đã kết thúc. Nhấn “Bắt đầu phiên mới” để đặt xe tiếp.");
      }
    } catch (error) {
      setLifecycleStatus("FAILED");
      if (redirectToLoginIfUnauthorized(error, navigate)) return;
      setNotice(error instanceof Error ? error.message : "Không thể gửi tin nhắn.");
    } finally {
      setIsSending(false);
    }
  };

  const handleSubmitRating = async (rating: number) => {
    if (!sessionId) return;
    setIsSubmittingRating(true);
    try {
      await submitSessionFeedback(sessionId, rating);
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "Không thể gửi đánh giá.");
    } finally {
      setIsSubmittingRating(false);
    }
  };

  const handleEndSession = async () => {
    if (sessionId) {
      await endRideSession(sessionId).catch(() => undefined);
    }
    setSessionId(null);
    localStorage.removeItem("alosm_session_id");
    setSessionEnded(true);
    setShowOutcomePanel(false);
    setNotice("Phiên hội thoại đã kết thúc. Nhấn “Bắt đầu phiên mới” để đặt xe tiếp.");
  };

  const handleNewSession = async () => {
    if (sessionId) {
      await endRideSession(sessionId).catch(() => undefined);
    }
    try {
      const user = await getCurrentUser();
      const session = await createRideSession();
      saveAuthSession({
        access_token: getAccessToken() || "",
        user_id: user.user_id,
        full_name: user.full_name,
        session_id: session.session_id,
      });
      setSessionId(session.session_id);
      resetConversationUi();
    } catch (error) {
      if (redirectToLoginIfUnauthorized(error, navigate)) return;
      setNotice(error instanceof Error ? error.message : "Không thể tạo phiên mới.");
    }
  };

  const toggleMicrophone = async () => {
    if (!sessionId || isSending || sessionEnded) return;
    if (isListening) {
      toggleRecording();
      return;
    }
    setNotice(null);
    setIsListening(true);
    await toggleRecording();
  };

  const logout = async () => {
    if (sessionId) await endRideSession(sessionId).catch(() => undefined);
    clearAuthSession();
    navigate("/login");
  };

  const inputDisabled = !sessionId || isSending || sessionEnded;

  return (
    <main className="min-h-screen bg-slate-50 text-[#191C1E]">
      <header className="min-h-16 px-5 md:px-10 py-3 bg-white border-b border-slate-200 flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="font-extrabold text-xl text-[#006a62]">AloSM Voice</p>
          <p className="text-xs text-slate-500">Đặt xe an toàn, dễ dàng</p>
        </div>
        <div className="flex items-center gap-3">
          <LlmStatusNote compact />
          {/* Bug thật đã sửa: trước đây không có cách nào quay lại Home/Booking/...
              từ trang này ngoài Đăng xuất (mất hết phiên) — trang chỉ có link MỘT
              CHIỀU từ Home tới đây, không có chiều ngược lại. */}
          <NavLink
            to="/"
            className="flex gap-2 items-center text-sm font-semibold text-slate-600 hover:text-[#006a62]"
          >
            <Home className="w-4 h-4" /> Trang chủ
          </NavLink>
          <button
            onClick={logout}
            className="flex gap-2 items-center text-sm font-semibold text-slate-600 hover:text-rose-600"
          >
            <LogOut className="w-4 h-4" /> Đăng xuất
          </button>
        </div>
      </header>
      <section className="max-w-6xl mx-auto px-4 py-8 md:py-12">
        <div className="flex flex-col lg:flex-row gap-6 items-start">
          <div className="flex-1 min-w-0 w-full">
            <div className="text-center mb-6">
              <h1 className="text-3xl font-extrabold">Chào {userName}, bạn muốn đi đâu?</h1>
              <p className="text-slate-500 mt-2">
                Nói tự nhiên hoặc nhắn tin. AloSM luôn hỏi xác nhận trước khi đặt xe.
              </p>
              <div className="mt-4 max-w-xl mx-auto text-left">
                <LlmStatusNote />
              </div>
            </div>
            <div className="bg-white border border-slate-200 shadow-lg rounded-3xl overflow-hidden">
              <div className="p-6 bg-gradient-to-br from-[#006a62] to-[#00D1C1] text-white text-center">
                <button
                  onClick={toggleMicrophone}
                  disabled={inputDisabled}
                  className="w-28 h-28 mx-auto rounded-full bg-white/20 border-4 border-white/50 flex items-center justify-center hover:scale-105 disabled:opacity-50 transition"
                  aria-label="Bắt đầu nói"
                >
                  {isListening ? <Square className="w-9 h-9 fill-white" /> : <Mic className="w-11 h-11" />}
                </button>
                <p className="font-bold mt-4">
                  {sessionEnded
                    ? "Phiên đã kết thúc"
                    : isListening
                      ? "Đang ghi âm… Nhấn để gửi"
                      : isSending
                        ? "Đang xử lý giọng nói…"
                        : sessionId
                          ? "Nhấn để nói (Whisper/TTS)"
                          : "Đang kết nối phiên…"}
                </p>
              </div>
              <div className="p-5 md:p-6">
                <div className="h-[310px] overflow-y-auto space-y-4 pr-1" aria-live="polite">
                  {messages.map((message) => (
                    <div
                      key={message.id}
                      className={`flex gap-3 ${message.role === "user" ? "justify-end" : "justify-start"}`}
                    >
                      {message.role === "assistant" && (
                        <span className="mt-1 w-8 h-8 shrink-0 rounded-full bg-[#00D1C1]/15 text-[#006a62] grid place-items-center">
                          <Bot className="w-4 h-4" />
                        </span>
                      )}
                      <p
                        className={`max-w-[80%] rounded-2xl px-4 py-3 text-sm leading-6 ${
                          message.role === "user"
                            ? "bg-[#00D1C1] text-white rounded-tr-sm"
                            : "bg-slate-100 rounded-tl-sm"
                        }`}
                      >
                        {message.text}
                      </p>
                    </div>
                  ))}
                  {isSending && (
                    <p className="text-sm text-slate-500 animate-pulse">AloSM đang xử lý…</p>
                  )}
                </div>

                {showOutcomePanel && completedBooking && (
                  <BookingSuccessPanel
                    booking={{
                      booking_id: completedBooking.booking_id,
                      estimated_fare: completedBooking.estimated_fare,
                      lifecycle_status: completedBooking.lifecycle_status ?? "SUCCESS",
                    }}
                    onSubmitRating={handleSubmitRating}
                    onEndSession={handleEndSession}
                    onNewSession={handleNewSession}
                    isSubmittingRating={isSubmittingRating}
                  />
                )}

                {notice && (
                  <p className="mt-4 text-sm bg-amber-50 text-amber-800 rounded-xl p-3">{notice}</p>
                )}

                {sessionEnded && (
                  <div className="mt-4">
                    <button
                      type="button"
                      onClick={handleNewSession}
                      className="rounded-xl bg-[#00D1C1] px-4 py-2 text-sm font-semibold text-white hover:opacity-90"
                    >
                      Bắt đầu phiên mới
                    </button>
                  </div>
                )}

                {!sessionEnded && (
                  <>
                    <div className="flex flex-wrap gap-2 mt-4">
                      <button
                        onClick={() => send("Đặt xe từ Quận 1 đến sân bay Tân Sơn Nhất")}
                        className="text-xs bg-slate-100 rounded-full px-3 py-2 hover:bg-slate-200"
                      >
                        Đặt xe ra sân bay
                      </button>
                    </div>
                    <form
                      onSubmit={(event) => {
                        event.preventDefault();
                        send(text);
                      }}
                      className="flex gap-2 border-t border-slate-100 mt-5 pt-4"
                    >
                      <input
                        value={text}
                        onChange={(event) => setText(event.target.value)}
                        disabled={inputDisabled}
                        className="flex-1 rounded-xl bg-slate-100 px-4 py-3 text-sm outline-none focus:ring-2 focus:ring-[#00D1C1]"
                        placeholder="Nhập điểm đón và điểm đến…"
                      />
                      <button
                        disabled={!text.trim() || inputDisabled}
                        className="w-12 rounded-xl bg-[#00D1C1] text-white grid place-items-center disabled:opacity-50"
                        aria-label="Gửi"
                      >
                        <Send className="w-5 h-5" />
                      </button>
                    </form>
                  </>
                )}

                <p className="mt-3 flex items-center gap-1 text-xs text-slate-400">
                  <Volume2 className="w-3 h-3" /> Giọng nói dùng Whisper/Gemini STT và OpenAI TTS.
                </p>
              </div>
            </div>
          </div>
          <BookingProgressSidebar
            progress={bookingProgress}
            lifecycleStatus={lifecycleStatus}
            isProcessing={isSending}
          />
        </div>
      </section>
    </main>
  );
};
