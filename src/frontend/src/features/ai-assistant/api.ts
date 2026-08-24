import { fetchApi } from "@/app/config/api";
import type { AgentStatusResponse } from "@/types/api";

// sendChatMessage()/ChatRequest/ChatResponse (POST /api/v1/chat, chat UI cũ) đã bị
// xoá — không còn UI nào gọi nữa, xem lịch sử git nếu cần tham khảo lại. Route
// /api/v1/chat vẫn còn ở Backend (legacy, dùng bởi test), chỉ Frontend hết gọi.
export async function checkAgentStatus(): Promise<AgentStatusResponse> {
  return fetchApi<AgentStatusResponse>("/api/v1/status");
}
