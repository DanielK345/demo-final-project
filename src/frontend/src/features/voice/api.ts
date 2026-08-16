import { API_BASE_URL, ApiError, extractErrorMessage } from "@/app/config/api";
import { getAccessToken } from "@/features/auth/storage";
import type { RideBooking, RideTurn } from "@/features/ride/api";

export interface VoiceTurnResponse {
  transcript: string;
  transcript_rewritten: boolean;
  transcript_rewrite_confidence?: number | null;
  transcript_rewrite_reason?: string | null;
  transcript_rewrite?: TranscriptRewriteTrace | null;
  stt_confidence: number | null;
  message_id: string;
  action: "ASK_USER" | "RESPOND" | "HANDOFF" | "END_SESSION";
  message: string;
  state: RideTurn["state"];
  booking?: RideBooking | null;
  audio_base64: string | null;
  audio_mime_type: string;
  voice_provider: string;
  tts_provider?: string | null;
  tts_voice?: string | null;
  tts_fallback_used?: boolean;
  tts_duration_ms?: number | null;
  tts_review_decision?: string | null;
  tts_review_reason_codes?: string[];
}

export interface SpeechReviewContext {
  bookingConfirmed?: boolean;
  action?: string;
}

export interface TranscriptRewriteTrace {
  provider: string;
  called: boolean;
  applied: boolean;
  status: string;
}

export interface SynthesizedSpeech {
  blob: Blob;
  provider: string;
  voice: string;
  fallbackUsed: boolean;
  durationMs: number;
  reviewDecision: string;
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

export async function synthesizeSpeech(
  text: string,
  reviewContext: SpeechReviewContext = {},
): Promise<SynthesizedSpeech> {
  const response = await fetch(`${API_BASE_URL}/api/v1/voice/speak`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...authHeader() },
    body: JSON.stringify({
      text,
      booking_confirmed: reviewContext.bookingConfirmed ?? false,
      action: reviewContext.action ?? null,
    }),
  });
  if (!response.ok) {
    const errorBody = await response.json().catch(() => null);
    throw new ApiError(extractErrorMessage(errorBody, response.status), response.status);
  }
  const blob = await response.blob();
  if (!blob.size || !blob.type.startsWith("audio/")) {
    throw new Error("Máy chủ trả về âm thanh không hợp lệ");
  }
  return {
    blob,
    provider: response.headers.get("X-TTS-Provider") ?? "unknown",
    voice: response.headers.get("X-TTS-Voice") ?? "unknown",
    fallbackUsed: response.headers.get("X-TTS-Fallback") === "true",
    durationMs: Number(response.headers.get("X-TTS-Duration-Ms") ?? 0),
    reviewDecision: response.headers.get("X-TTS-Review") ?? "unknown",
  };
}

let activeAudio: HTMLAudioElement | null = null;
let activeObjectUrl: string | null = null;
let resolveActivePlayback: (() => void) | null = null;

function stopActiveAudio(): void {
  if (activeAudio) {
    activeAudio.pause();
    activeAudio.src = "";
    activeAudio = null;
  }
  if (activeObjectUrl) {
    URL.revokeObjectURL(activeObjectUrl);
    activeObjectUrl = null;
  }
  const resolve = resolveActivePlayback;
  resolveActivePlayback = null;
  resolve?.();
}

export function playAudioBlob(blob: Blob): Promise<void> {
  if (!blob.size || !blob.type.startsWith("audio/")) {
    return Promise.reject(new Error("Dữ liệu âm thanh không hợp lệ"));
  }
  stopActiveAudio();
  const objectUrl = URL.createObjectURL(blob);
  const audio = new Audio(objectUrl);
  activeAudio = audio;
  activeObjectUrl = objectUrl;
  return new Promise((resolve, reject) => {
    resolveActivePlayback = resolve;
    const cleanup = () => {
      if (activeAudio === audio) activeAudio = null;
      if (activeObjectUrl === objectUrl) activeObjectUrl = null;
      if (resolveActivePlayback === resolve) resolveActivePlayback = null;
      URL.revokeObjectURL(objectUrl);
    };
    audio.onended = () => {
      cleanup();
      resolve();
    };
    audio.onerror = () => {
      cleanup();
      reject(new Error("Không thể giải mã hoặc phát audio phản hồi"));
    };
    void audio.play().catch((error: unknown) => {
      cleanup();
      reject(error instanceof Error ? error : new Error("Trình duyệt đã chặn phát âm thanh"));
    });
  });
}

export function playBase64Audio(base64: string, mimeType: string): Promise<void> {
  try {
    if (!mimeType.startsWith("audio/")) throw new Error("MIME audio không hợp lệ");
    const binary = window.atob(base64);
    if (!binary.length) throw new Error("Audio phản hồi rỗng");
    const bytes = new Uint8Array(binary.length);
    for (let index = 0; index < binary.length; index += 1) bytes[index] = binary.charCodeAt(index);
    return playAudioBlob(new Blob([bytes], { type: mimeType }));
  } catch (error) {
    return Promise.reject(error instanceof Error ? error : new Error("Audio base64 không hợp lệ"));
  }
}

export function stopVoicePlayback(): void {
  stopActiveAudio();
}
