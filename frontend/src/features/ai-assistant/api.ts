import { fetchApi } from "@/app/config/api";
import type { ChatRequest, ChatResponse, AgentStatusResponse } from "@/types/api";

export async function sendChatMessage(message: string): Promise<ChatResponse> {
  return fetchApi<ChatResponse>("/api/v1/chat", {
    method: "POST",
    body: JSON.stringify({ message } as ChatRequest),
  });
}

export async function checkAgentStatus(): Promise<AgentStatusResponse> {
  return fetchApi<AgentStatusResponse>("/api/v1/status");
}
