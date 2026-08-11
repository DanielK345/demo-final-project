export const API_BASE_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

export async function fetchApi<T>(endpoint: string, options?: RequestInit): Promise<T> {
  const url = `${API_BASE_URL}${endpoint}`;
  const response = await fetch(url, {
    headers: {
      "Content-Type": "application/json",
      ...options?.headers,
    },
    ...options,
  });

  if (!response.ok) {
    const errorBody = await response.json().catch(() => ({ detail: "API Error" }));
    throw new Error(errorBody.detail || `Request failed with status ${response.status}`);
  }

  return response.json();
}
