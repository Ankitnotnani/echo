// Mirrors the backend API contract exactly (field names must not change).

export type ResolutionSource = "LIVE_INFERENCE" | "LLM_CACHE";

export interface ChatMetadata {
  resolution_source: ResolutionSource;
  model: string;
  latency_ms: number;
  input_tokens: number;
  output_tokens: number;
  key_id: string | null;
  fallback_attempts: number;
}

export interface ChatRequest {
  session_id: string;
  message: string;
  system_prompt?: string;
}

export interface ChatResponse {
  session_id: string;
  reply: string;
  metadata: ChatMetadata;
}

export interface HealthResponse {
  status: "ok";
  keys_configured: number;
  cache_enabled: boolean;
  model?: string;
  failure_simulation_enabled?: boolean;
}

export interface HistoryMessage {
  role: "user" | "assistant";
  content: string;
  metadata?: Partial<ChatMetadata>;
  created_at?: string;
}

export interface HistoryResponse {
  session_id: string;
  messages: HistoryMessage[];
}

// ---- UI-only types ----

export type ThreadItem =
  | { id: string; kind: "user"; text: string }
  | { id: string; kind: "assistant"; text: string; meta: Partial<ChatMetadata> }
  | { id: string; kind: "error"; text: string; retry?: { message: string; simulate?: string } };

export type HealthState =
  | { state: "checking" }
  | { state: "ok"; data: HealthResponse }
  | { state: "down"; reason: string };
