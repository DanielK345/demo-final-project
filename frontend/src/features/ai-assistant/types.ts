export interface ChatMessage {
  id: string;
  sender: "user" | "assistant";
  content: string;
  analysis?: string;
  timestamp: string;
  status?: "sending" | "sent" | "error";
}
