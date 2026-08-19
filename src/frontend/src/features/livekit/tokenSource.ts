import { TokenSource } from "livekit-client";
import { API_BASE_URL } from "@/app/config/api";
import { liveKitAuthorizationHeaders, takePreparedAloSMCall } from "./prepareCall";

export const LIVEKIT_AGENT_NAME = "alosm-voice";
const PREPARE_WAIT_TIMEOUT_MS = 1_500;

async function waitForPreparedCall<T>(prepared: Promise<T>): Promise<T> {
  let timeoutId: ReturnType<typeof setTimeout> | undefined;
  try {
    return await Promise.race([
      prepared,
      new Promise<never>((_, reject) => {
        timeoutId = setTimeout(() => reject(new Error("LiveKit prepare timed out")), PREPARE_WAIT_TIMEOUT_MS);
      }),
    ]);
  } finally {
    if (timeoutId) clearTimeout(timeoutId);
  }
}

export function createAloSMTokenSource(callInstanceId: string) {
  const endpoint = TokenSource.endpoint(`${API_BASE_URL}/api/v1/livekit/token`, {
    headers: liveKitAuthorizationHeaders(),
  });
  let usePreparedCall = true;

  return TokenSource.custom(async (options) => {
    const prepared = usePreparedCall ? takePreparedAloSMCall(callInstanceId) : undefined;
    usePreparedCall = false;
    if (prepared) {
      try {
        const response = await waitForPreparedCall(prepared);
        return {
          serverUrl: response.server_url,
          participantToken: response.participant_token,
        };
      } catch {
        // The standard token path below retains RoomConfiguration dispatch and
        // therefore preserves the previous behavior when early dispatch fails.
      }
    }
    return endpoint.fetch({
      ...options,
      participantAttributes: {
        ...(options.participantAttributes ?? {}),
        "alosm.call_id": callInstanceId,
      },
    });
  });
}
