export interface ChatRequest {
  message: string;
}

export interface ChatResponse {
  response: string;
  analysis: string;
}

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
}
