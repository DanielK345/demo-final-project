import { fetchApi } from "@/app/config/api";
import { getAccessToken } from "@/features/auth/storage";

export interface SessionHistorySummary {
  session_id: string;
  channel: string;
  status: string;
  created_at: string | null;
  message_count: number;
  preview: string;
}

export interface TranscriptMessage {
  timestamp: string;
  role: "user" | "agent";
  text: string;
  source?: string | null;
  stt_confidence?: number | null;
  action?: string | null;
}

export interface SessionTranscript {
  session_id: string;
  channel: string;
  status: string;
  created_at: string | null;
  ended_at: string | null;
  messages: TranscriptMessage[];
}

function authHeader(): HeadersInit {
  const token = getAccessToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}

export function listSessionHistory(): Promise<SessionHistorySummary[]> {
  return fetchApi<SessionHistorySummary[]>("/api/v1/sessions/history", { headers: authHeader() });
}

export function getSessionTranscript(sessionId: string): Promise<SessionTranscript> {
  return fetchApi<SessionTranscript>(`/api/v1/sessions/history/${sessionId}`, { headers: authHeader() });
}
