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
  livekit_configured?: boolean;
  livekit_agent_name?: string;
  livekit_stt_model?: string;
  livekit_llm_model?: string;
  livekit_tts_model?: string;
}
