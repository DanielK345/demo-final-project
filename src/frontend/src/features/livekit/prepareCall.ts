import { API_BASE_URL } from "@/app/config/api";
import { getAccessToken } from "@/features/auth/storage";

export type PreparedCallResponse = {
  server_url: string;
  participant_token: string;
  agent_prepared: boolean;
};

const preparedCalls = new Map<string, Promise<PreparedCallResponse>>();

export function liveKitAuthorizationHeaders(): Record<string, string> {
  const accessToken = getAccessToken();
  if (!accessToken) throw new Error("Vui lòng đăng nhập để bắt đầu cuộc gọi LiveKit.");
  return { Authorization: `Bearer ${accessToken}` };
}

export function prepareAloSMCall(callInstanceId: string): Promise<PreparedCallResponse> {
  const existing = preparedCalls.get(callInstanceId);
  if (existing) return existing;

  const request = fetch(`${API_BASE_URL}/api/v1/livekit/prepare`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...liveKitAuthorizationHeaders(),
    },
    body: JSON.stringify({ call_instance_id: callInstanceId }),
  }).then(async (response) => {
    if (!response.ok) {
      throw new Error(`Không thể chuẩn bị LiveKit agent (${response.status}).`);
    }
    return response.json() as Promise<PreparedCallResponse>;
  });
  preparedCalls.set(callInstanceId, request);
  return request;
}

export function takePreparedAloSMCall(callInstanceId: string): Promise<PreparedCallResponse> | undefined {
  const prepared = preparedCalls.get(callInstanceId);
  preparedCalls.delete(callInstanceId);
  return prepared;
}

export function discardPreparedAloSMCall(callInstanceId: string | null): void {
  if (callInstanceId) preparedCalls.delete(callInstanceId);
}
