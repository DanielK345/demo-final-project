import { useContext } from "react";
import { VoiceAssistantContext, type VoiceAssistantValue } from "./voice-assistant-context";

export function useVoiceAssistant(): VoiceAssistantValue {
  const ctx = useContext(VoiceAssistantContext);
  if (!ctx) {
    throw new Error("useVoiceAssistant() phải được gọi bên trong <VoiceAssistantProvider>");
  }
  return ctx;
}
