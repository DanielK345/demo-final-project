import React, { useCallback, useEffect, useRef, useState } from "react";
import { Bot, History, Keyboard, Mic, Send, Square, Volume2 } from "lucide-react";
import { useLocation, useNavigate } from "react-router-dom";
import { getCurrentUser } from "@/features/auth/api";
import { redirectToLoginIfUnauthorized } from "@/features/auth/sessionGuard";
import {
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
import { HistoryPanel } from "@/features/history/components/HistoryPanel";
import { TranscriptModal } from "@/features/history/components/TranscriptModal";

type Message = { id: string; role: "user" | "assistant"; text: string };

// Chào thân thiện + hỏi han trước, RỒI MỚI hỏi cần giúp gì — theo đúng yêu cầu, thay
// vì câu cũ mở đầu bằng liệt kê yêu cầu kỹ thuật (loại xe/không hỏi SĐT) nghe khô
// khan, giống thông báo hệ thống hơn là chào hỏi. Thông tin kỹ thuật đó vẫn còn,
// chuyển thành dòng phụ nhỏ dưới tiêu đề trang (xem bên dưới) — không mất đi, chỉ
// không còn là ấn tượng đầu tiên nữa. Cá nhân hoá bằng tên thật của khách.
function buildWelcomeMessage(userName: string): string {
  return `Xin chào ${userName}! Em là trợ lý AloSM, rất vui được đồng hành cùng anh/chị hôm nay 😊 Anh/chị đang cần em hỗ trợ gì ạ — đặt xe, theo dõi chuyến đi, hay có thắc mắc nào khác không?`;
}

export const AssistantPage: React.FC = () => {
  const [sessionId, setSessionId] = useState<string | null>(null);
  const userName = getUserName();
  const [messages, setMessages] = useState<Message[]>([
    { id: "welcome", role: "assistant", text: buildWelcomeMessage(userName) },
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
  const [isHistoryOpen, setIsHistoryOpen] = useState(false);
  const [transcriptSessionId, setTranscriptSessionId] = useState<string | null>(null);
  const [isTextInputOpen, setIsTextInputOpen] = useState(false);
  const navigate = useNavigate();
  const location = useLocation();

  const resetConversationUi = useCallback(() => {
    setMessages([{ id: "welcome", role: "assistant", text: buildWelcomeMessage(getUserName()) }]);
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

  const send = useCallback(async (value: string, source: "TEXT" | "VOICE" = "TEXT") => {
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
  }, [sessionId, isSending, sessionEnded, lifecycleStatus, applyTurnResult, navigate]);

  // Các nút "AI đặt xe ngay" ở Trang chủ / Dịch vụ / Theo dõi chuyến đi điều hướng
  // thẳng vào đây kèm `state.prefill` — thay vì tự mở form/modal, câu mô tả chuyến đi
  // được gửi hộ như thể người dùng vừa gõ nó, để Agentic AI tiếp quản toàn bộ (hỏi
  // xác nhận, tạo booking) giống hệt các quick-chip có sẵn (vd "Đặt xe ra sân bay").
  // useRef (không phải state) để chỉ gửi đúng 1 lần kể cả khi StrictMode chạy effect
  // 2 lần lúc dev.
  const prefillHandledRef = useRef(false);
  useEffect(() => {
    const prefill = (location.state as { prefill?: string } | null)?.prefill;
    if (!prefill || prefillHandledRef.current || !sessionId || sessionEnded) return;
    prefillHandledRef.current = true;
    send(prefill);
    navigate(location.pathname, { replace: true, state: null });
  }, [location.state, sessionId, sessionEnded, navigate, location.pathname, send]);

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

  const inputDisabled = !sessionId || isSending || sessionEnded;

  return (
    // Trang này nằm trong AppLayout (Sidebar/Topbar/MobileNav thật — xem
    // app/router/index.tsx) nên đã có taskbar để sang màn khác, không cần nút
    // "Trang chủ" tự chế nữa. Giao diện panel dùng đúng tông sáng như mọi trang khác
    // (bg trắng/viền xám nhạt) + biến thể `dark:` để theo đúng theme toàn site khi
    // người dùng bật "Giao diện tối" trong Cài đặt (xem ThemeProvider).
    <div className="pb-8">
      <div className="text-center mb-6">
        <h1 className="text-3xl font-extrabold text-[#191C1E] dark:text-white">
          Chào {userName}, bạn muốn đi đâu?
        </h1>
        <p className="text-slate-500 dark:text-slate-400 mt-2">
          Nói tự nhiên hoặc nhắn tin. AloSM luôn hỏi xác nhận trước khi đặt xe.
        </p>
        <p className="text-xs text-slate-400 dark:text-slate-500 mt-1">
          Hỗ trợ xe máy, ô tô 4 chỗ và ô tô 7 chỗ · Không hỏi số điện thoại hay email
          trong hội thoại — SĐT liên hệ tài xế lấy tự động từ tài khoản của anh/chị.
        </p>
        <div className="mt-4 max-w-xl mx-auto text-left">
          <LlmStatusNote />
        </div>
      </div>

      <div className="flex flex-col lg:flex-row gap-6 items-start">
        <div className="flex-1 min-w-0 w-full">
          <div className="bg-white border border-slate-200/80 shadow-[0px_4px_20px_rgba(16,18,19,0.05)] rounded-3xl overflow-hidden dark:bg-[#12161A] dark:border-white/10 dark:shadow-2xl">
            {/* Thanh trên cùng của khu trò chuyện — chỉ còn nút Lịch sử (điều hướng
                sang trang khác đã có Topbar lo, không lặp lại ở đây) */}
            <div className="flex items-center justify-between px-5 py-3 border-b border-slate-100 dark:border-white/10">
              <span className="text-xs font-bold text-slate-500 dark:text-slate-300 uppercase tracking-wider">
                AloSM Voice
              </span>
              <button
                type="button"
                onClick={() => setIsHistoryOpen(true)}
                className="flex items-center gap-1.5 text-xs font-semibold text-slate-600 hover:text-[#006a62] px-3 py-1.5 rounded-full hover:bg-slate-100 transition-colors dark:text-slate-300 dark:hover:text-[#00D1C1] dark:hover:bg-white/10"
              >
                <History className="w-3.5 h-3.5" />
                Lịch sử trò chuyện
              </button>
            </div>

            {/* Mic — hành động chính, đặt đầu tiên và nổi bật nhất; chat text là lựa
                chọn phụ, gấp gọn phía dưới (xem nút "Hoặc nhắn tin"). Banner gradient
                này là mảng màu thương hiệu cố định, không đổi theo theme sáng/tối. */}
            <div className="p-8 bg-gradient-to-br from-[#0B3D3A] via-[#0E4F49] to-[#00D1C1]/30 text-white text-center">
              <button
                onClick={toggleMicrophone}
                disabled={inputDisabled}
                className={`w-32 h-32 mx-auto rounded-full flex items-center justify-center transition disabled:opacity-50 ${
                  isListening
                    ? "bg-rose-500/90 border-4 border-rose-300/60 scale-105 animate-pulse"
                    : "bg-white/10 border-4 border-white/30 hover:scale-105 hover:bg-white/15"
                }`}
                aria-label="Bắt đầu nói"
              >
                {isListening ? <Square className="w-10 h-10 fill-white" /> : <Mic className="w-12 h-12" />}
              </button>
              <p className="font-bold mt-5 text-lg">
                {sessionEnded
                  ? "Phiên đã kết thúc"
                  : isListening
                    ? "Đang ghi âm… Nhấn để gửi"
                    : isSending
                      ? "Đang xử lý giọng nói…"
                      : sessionId
                        ? "Nhấn để nói"
                        : "Đang kết nối phiên…"}
              </p>
              <p className="text-xs text-white/70 mt-1 flex items-center justify-center gap-1">
                <Volume2 className="w-3 h-3" /> Whisper/Gemini STT · OpenAI TTS
              </p>
            </div>

            <div className="p-5 md:p-6">
              <div className="h-[280px] overflow-y-auto space-y-4 pr-1" aria-live="polite">
                {messages.map((message) => (
                  <div
                    key={message.id}
                    className={`flex gap-3 ${message.role === "user" ? "justify-end" : "justify-start"}`}
                  >
                    {message.role === "assistant" && (
                      <span className="mt-1 w-8 h-8 shrink-0 rounded-full bg-[#00D1C1]/15 text-[#006a62] dark:text-[#00D1C1] grid place-items-center">
                        <Bot className="w-4 h-4" />
                      </span>
                    )}
                    <p
                      className={`max-w-[80%] rounded-2xl px-4 py-3 text-sm leading-6 ${
                        message.role === "user"
                          ? "bg-[#00D1C1] text-[#0B0E11] font-medium rounded-tr-sm"
                          : "bg-slate-100 text-slate-700 rounded-tl-sm dark:bg-white/10 dark:text-slate-100"
                      }`}
                    >
                      {message.text}
                    </p>
                  </div>
                ))}
                {isSending && (
                  <p className="text-sm text-slate-500 dark:text-slate-400 animate-pulse">AloSM đang xử lý…</p>
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
                <p className="mt-4 text-sm bg-amber-50 text-amber-800 border border-amber-200 rounded-xl p-3 dark:bg-amber-500/10 dark:text-amber-300 dark:border-amber-500/30">
                  {notice}
                </p>
              )}

              {sessionEnded && (
                <div className="mt-4">
                  <button
                    type="button"
                    onClick={handleNewSession}
                    className="rounded-xl bg-[#00D1C1] px-4 py-2 text-sm font-semibold text-[#0B0E11] hover:opacity-90"
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
                      className="text-xs bg-slate-100 text-slate-700 rounded-full px-3 py-2 hover:bg-slate-200 dark:bg-white/10 dark:text-slate-200 dark:hover:bg-white/20"
                    >
                      Đặt xe ra sân bay
                    </button>
                    <button
                      type="button"
                      onClick={() => setIsTextInputOpen((open) => !open)}
                      className="flex items-center gap-1.5 text-xs bg-slate-100 text-slate-700 rounded-full px-3 py-2 hover:bg-slate-200 dark:bg-white/10 dark:text-slate-200 dark:hover:bg-white/20"
                    >
                      <Keyboard className="w-3.5 h-3.5" />
                      {isTextInputOpen ? "Ẩn nhắn tin" : "Hoặc nhắn tin"}
                    </button>
                  </div>

                  {isTextInputOpen && (
                    <form
                      onSubmit={(event) => {
                        event.preventDefault();
                        send(text);
                      }}
                      className="flex gap-2 border-t border-slate-100 dark:border-white/10 mt-5 pt-4"
                    >
                      <input
                        value={text}
                        onChange={(event) => setText(event.target.value)}
                        disabled={inputDisabled}
                        autoFocus
                        className="flex-1 rounded-xl bg-slate-50 border border-slate-200 text-[#191C1E] placeholder:text-slate-400 px-4 py-3 text-sm outline-none focus:ring-2 focus:ring-[#00D1C1] dark:bg-white/5 dark:border-white/10 dark:text-white dark:placeholder:text-slate-500"
                        placeholder="Nhập điểm đón và điểm đến…"
                      />
                      <button
                        disabled={!text.trim() || inputDisabled}
                        className="w-12 rounded-xl bg-[#00D1C1] text-[#0B0E11] grid place-items-center disabled:opacity-50"
                        aria-label="Gửi"
                      >
                        <Send className="w-5 h-5" />
                      </button>
                    </form>
                  )}
                </>
              )}
            </div>
          </div>
        </div>
        <BookingProgressSidebar
          progress={bookingProgress}
          lifecycleStatus={lifecycleStatus}
          isProcessing={isSending}
        />
      </div>

      <HistoryPanel
        isOpen={isHistoryOpen}
        onClose={() => setIsHistoryOpen(false)}
        onSelectSession={(id) => setTranscriptSessionId(id)}
      />
      <TranscriptModal sessionId={transcriptSessionId} onClose={() => setTranscriptSessionId(null)} />
    </div>
  );
};
