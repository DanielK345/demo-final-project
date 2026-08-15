import { API_BASE_URL, ApiError, extractErrorMessage } from "@/app/config/api";
import { getAccessToken } from "@/features/auth/storage";
import type { RideBooking, RideTurn } from "@/features/ride/api";

// `/api/v1/voice/turn` và `/api/v1/sessions/{id}/messages` dùng chung
// `SessionService._format_action_response()` ở backend (xem session_service.py) nên
// state/booking trả về CÙNG hình dạng — tái dùng đúng type của RideTurn thay vì khai
// báo lại (tránh lệch dần giữa 2 khai báo cho cùng 1 response thật).
export interface VoiceTurnResponse {
  transcript: string;
  stt_confidence: number;
  message_id: string;
  action: "ASK_USER" | "RESPOND" | "HANDOFF" | "END_SESSION";
  message: string;
  state: RideTurn["state"];
  booking?: RideBooking | null;
  audio_base64: string | null;
  audio_mime_type: string;
  voice_provider: string;
}

function authHeader(): HeadersInit {
  const token = getAccessToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}

export async function sendVoiceTurn(sessionId: string, audio: Blob): Promise<VoiceTurnResponse> {
  const formData = new FormData();
  formData.append("session_id", sessionId);
  formData.append("audio", audio, "recording.webm");

  const response = await fetch(`${API_BASE_URL}/api/v1/voice/turn`, {
    method: "POST",
    headers: authHeader(),
    body: formData,
  });

  if (!response.ok) {
    const errorBody = await response.json().catch(() => null);
    throw new ApiError(extractErrorMessage(errorBody, response.status), response.status);
  }

  return response.json();
}

export function playBase64Audio(base64: string, mimeType: string): Promise<void> {
  return new Promise((resolve, reject) => {
    const audio = new Audio(`data:${mimeType};base64,${base64}`);
    audio.onended = () => resolve();
    audio.onerror = () => reject(new Error("Không thể phát audio phản hồi"));
    void audio.play().catch(reject);
  });
}

// Trả về Promise hoàn tất khi trình duyệt đọc xong (hoặc ngay lập tức nếu trình
// duyệt không hỗ trợ speechSynthesis) — để UI trạng thái "đang nói" (VoiceCallPanel)
// biết chính xác khi nào nên quay lại "đang nghe" thay vì đoán 1 khoảng thời gian cố
// định.
export function speakWithBrowser(text: string): Promise<void> {
  if (!("speechSynthesis" in window)) return Promise.resolve();
  window.speechSynthesis.cancel();
  return new Promise((resolve) => {
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.lang = "vi-VN";
    utterance.onend = () => resolve();
    utterance.onerror = () => resolve();
    window.speechSynthesis.speak(utterance);
  });
}
