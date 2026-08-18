import { TokenSource } from "livekit-client";
import { API_BASE_URL } from "@/app/config/api";
import { getAccessToken } from "@/features/auth/storage";

export const LIVEKIT_AGENT_NAME = "alosm-voice";

export function createAloSMTokenSource() {
  const accessToken = getAccessToken();
  if (!accessToken) throw new Error("Vui lòng đăng nhập để bắt đầu cuộc gọi LiveKit.");

  return TokenSource.endpoint(`${API_BASE_URL}/api/v1/livekit/token`, {
    headers: {
      Authorization: `Bearer ${accessToken}`,
    },
  });
}
