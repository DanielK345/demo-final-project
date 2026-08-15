export interface HealthResponse {
  status: string;
  env: string;
}

export interface AgentStatusResponse {
  status: string;
  agent: string;
  llm_enabled: boolean;
  llm_provider: string;
  llm_model: string;
  understanding_mode: "openai" | "rules";
  conversation_backend: "session_rules" | "core_agent";
  voice_provider?: "openai" | "gemini" | null;
  voice_stt_model?: string;
  voice_tts_enabled?: boolean;
}
