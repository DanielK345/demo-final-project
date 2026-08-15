export const API_BASE_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

export class ApiError extends Error {
  status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

export function isUnauthorizedError(error: unknown): boolean {
  return error instanceof ApiError && error.status === 401;
}

// FastAPI's `detail` field is usually a string, but validation errors (HTTP 422)
// return it as a list of { msg, loc, type, ... } objects instead. Normalize any
// shape down to a human-readable string so callers never end up rendering
// "[object Object]" (e.g. via `new Error(detail)`).
export function extractErrorMessage(errorBody: unknown, status: number): string {
  const detail = (errorBody as { detail?: unknown } | null)?.detail;
  if (typeof detail === "string" && detail.trim()) return detail;
  if (Array.isArray(detail)) {
    const messages = detail
      .map((item) => (item && typeof item === "object" && "msg" in item ? String((item as { msg: unknown }).msg) : null))
      .filter((message): message is string => Boolean(message));
    if (messages.length) return messages.join("; ");
  }
  if (detail && typeof detail === "object" && "msg" in detail) return String((detail as { msg: unknown }).msg);
  return `Request failed with status ${status}`;
}

export async function fetchApi<T>(endpoint: string, options?: RequestInit): Promise<T> {
  const url = `${API_BASE_URL}${endpoint}`;
  const response = await fetch(url, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...options?.headers,
    },
  });

  if (!response.ok) {
    const errorBody = await response.json().catch(() => null);
    throw new ApiError(extractErrorMessage(errorBody, response.status), response.status);
  }

  return response.json();
}
