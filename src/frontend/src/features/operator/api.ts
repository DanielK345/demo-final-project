import { fetchApi } from "@/app/config/api";
import { getAccessToken } from "@/features/auth/storage";

export type HandoffRecord = {
  handoff_id: string;
  session_id: string;
  reason: string;
  reason_code: string;
  summary: string;
  pending_action?: string | null;
  priority: number;
  severity: string;
  queue: string;
  requires_immediate_transfer: boolean;
  status: "pending" | "accepted" | "connected" | "resolved" | "failed";
  created_at: string;
  accepted_at?: string | null;
  connected_at?: string | null;
  resolved_at?: string | null;
  operator_id?: string | null;
  room_name?: string | null;
  context_snapshot?: {
    summary?: string;
    booking_state?: Record<string, unknown>;
    last_failure?: Record<string, unknown> | null;
  } | null;
};

function authHeader(): HeadersInit {
  const token = getAccessToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}

export function listHandoffs(status = "pending"): Promise<HandoffRecord[]> {
  return fetchApi<HandoffRecord[]>(`/api/v1/handoffs?status=${encodeURIComponent(status)}`, {
    headers: authHeader(),
  });
}

export function acceptHandoff(handoffId: string): Promise<{ handoff_id: string; status: string; operator_id: string | null }> {
  return fetchApi(`/api/v1/handoffs/${encodeURIComponent(handoffId)}/accept`, {
    method: "POST",
    headers: authHeader(),
  });
}

export function getOperatorToken(handoffId: string): Promise<{ server_url: string; participant_token: string; handoff_id: string; room_name: string }> {
  return fetchApi("/api/v1/livekit/operator-token", {
    method: "POST",
    headers: authHeader(),
    body: JSON.stringify({ handoff_id: handoffId }),
  });
}

export function resolveHandoff(handoffId: string): Promise<HandoffRecord> {
  return fetchApi(`/api/v1/handoffs/${encodeURIComponent(handoffId)}/resolve`, {
    method: "POST",
    headers: authHeader(),
  });
}
