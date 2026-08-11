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
}
