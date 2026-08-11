import { useMutation, useQuery } from "@tanstack/react-query";
import { sendChatMessage, checkAgentStatus } from "./api";

export function useSendMessage() {
  return useMutation({
    mutationFn: (message: string) => sendChatMessage(message),
  });
}

export function useAgentStatus() {
  return useQuery({
    queryKey: ["agentStatus"],
    queryFn: checkAgentStatus,
    refetchInterval: 30000,
  });
}
