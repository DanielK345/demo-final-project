import { fetchApi } from "@/app/config/api";
import { getAccessToken } from "@/features/auth/storage";

export interface RideSession {
  session_id: string;
  status: string;
  channel: string;
  created_at: string;
}

export interface RideTurn {
  message_id: string;
  action: "ASK_USER" | "RESPOND" | "HANDOFF" | "END_SESSION";
  message: string;
  state: Record<string, unknown>;
  booking?: { booking_id: string; status: string; estimated_fare: number } | null;
}

function authHeader(): HeadersInit {
  const token = getAccessToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}

export function createRideSession(): Promise<RideSession> {
  return fetchApi<RideSession>("/api/v1/sessions", {
    method: "POST",
    headers: authHeader(),
    body: JSON.stringify({ channel: "WEB_VOICE", device_id: "browser" }),
  });
}

export function sendRideMessage(sessionId: string, message: string, source: "TEXT" | "VOICE", sttConfidence?: number): Promise<RideTurn> {
  return fetchApi<RideTurn>(`/api/v1/sessions/${sessionId}/messages`, {
    method: "POST",
    body: JSON.stringify({ message, source, stt_confidence: sttConfidence }),
  });
}

export function endRideSession(sessionId: string): Promise<unknown> {
  return fetchApi(`/api/v1/sessions/${sessionId}/end`, {
    method: "POST",
    body: JSON.stringify({ reason: "USER_ENDED" }),
  });
}
