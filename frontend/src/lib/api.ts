import { API_URL } from "./config";
import type { ChatRequest, ChatResponse, HealthResponse, HistoryResponse } from "./types";

export type ApiErrorKind = "validation" | "unavailable" | "not_found" | "network" | "timeout" | "server";

export class ApiError extends Error {
  constructor(
    public kind: ApiErrorKind,
    message: string,
    public status?: number,
  ) {
    super(message);
  }
}

const CHAT_TIMEOUT_MS = 90_000; // covers a free-tier cold start (~50 s) plus the LLM call

async function request<T>(path: string, init: RequestInit = {}, timeoutMs = 20_000): Promise<T> {
  const controller = new AbortController();
  const timer = window.setTimeout(() => controller.abort(), timeoutMs);
  let res: Response;
  try {
    res = await fetch(`${API_URL}${path}`, { ...init, signal: controller.signal });
  } catch (err) {
    if ((err as Error).name === "AbortError") {
      throw new ApiError("timeout", "The server took too long to answer. Please try again.");
    }
    throw new ApiError(
      "network",
      "Can't reach the server. If it has been idle, the free host can take about 50 seconds to wake up.",
    );
  } finally {
    window.clearTimeout(timer);
  }

  let body: unknown = null;
  try {
    body = await res.json();
  } catch {
    body = null;
  }

  if (res.ok) return body as T;
  throw toApiError(res.status, body);
}

function toApiError(status: number, body: unknown): ApiError {
  const detail = (body as { detail?: unknown } | null)?.detail;
  if (status === 422) return new ApiError("validation", describeValidation(detail), status);
  if (status === 503) {
    return new ApiError(
      "unavailable",
      "Every AI provider key failed for this request (rate-limited or unavailable), so nothing was saved. Please try again in a moment.",
      status,
    );
  }
  if (status === 404) {
    return new ApiError("not_found", typeof detail === "string" ? detail : "Not found.", status);
  }
  return new ApiError("server", `The server hit an error (${status}). Please try again.`, status);
}

function describeValidation(detail: unknown): string {
  if (Array.isArray(detail) && detail.length > 0) {
    const first = detail[0] as { loc?: unknown[]; msg?: string };
    const field = Array.isArray(first.loc) ? String(first.loc[first.loc.length - 1]) : "";
    if (field === "message") return "That message couldn't be sent: it must be 1–4000 characters.";
    if (field === "session_id") return "That message couldn't be sent: the session id is invalid. Start a new chat.";
    if (first.msg) return `That message couldn't be sent: ${first.msg}.`;
  }
  if (typeof detail === "string") return `That message couldn't be sent: ${detail}.`;
  return "That message couldn't be sent (validation error).";
}

export function getHealth(): Promise<HealthResponse> {
  return request<HealthResponse>("/health", {}, 15_000);
}

export function postChat(body: ChatRequest, simulate?: string): Promise<ChatResponse> {
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (simulate) headers["X-Simulate-Failure"] = simulate;
  return request<ChatResponse>("/chat", { method: "POST", headers, body: JSON.stringify(body) }, CHAT_TIMEOUT_MS);
}

export function getHistory(sessionId: string): Promise<HistoryResponse> {
  return request<HistoryResponse>(`/sessions/${encodeURIComponent(sessionId)}/messages`);
}

/** Poll /health until it answers (used to ride out a cold start). */
export async function waitForServer(maxWaitMs = 75_000, everyMs = 5_000): Promise<boolean> {
  const deadline = Date.now() + maxWaitMs;
  while (Date.now() < deadline) {
    try {
      await getHealth();
      return true;
    } catch {
      await new Promise((r) => window.setTimeout(r, everyMs));
    }
  }
  return false;
}
