import { API_BASE_URL, ApiError, extractErrorMessage } from "@/app/config/api";
import { getAccessToken } from "@/features/auth/storage";

export interface VoiceTurnResponse {
  transcript: string;
  stt_confidence: number;
  message_id: string;
  action: "ASK_USER" | "RESPOND" | "HANDOFF" | "END_SESSION";
  message: string;
  state: Record<string, unknown>;
  booking?: { booking_id: string; status: string; estimated_fare: number } | null;
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

export function speakWithBrowser(text: string): void {
  if (!("speechSynthesis" in window)) return;
  window.speechSynthesis.cancel();
  const utterance = new SpeechSynthesisUtterance(text);
  utterance.lang = "vi-VN";
  window.speechSynthesis.speak(utterance);
}
