const ACCESS_TOKEN_KEY = "alosm_access_token";
const USER_ID_KEY = "alosm_user_id";
const USER_NAME_KEY = "alosm_user_name";
const USER_ROLE_KEY = "alosm_user_role";
const SESSION_ID_KEY = "alosm_session_id";

export function getAccessToken(): string | null {
  return localStorage.getItem(ACCESS_TOKEN_KEY);
}

export function getUserId(): string | null {
  return localStorage.getItem(USER_ID_KEY);
}

export function getSessionId(): string | null {
  return localStorage.getItem(SESSION_ID_KEY);
}

export function getUserName(): string {
  return localStorage.getItem(USER_NAME_KEY) || "bạn";
}

export function getUserRole(): string | null {
  return localStorage.getItem(USER_ROLE_KEY);
}

export function isAuthenticated(): boolean {
  const token = getAccessToken();
  const userId = getUserId();
  const sessionId = getSessionId();
  return Boolean(token?.trim() && userId?.trim() && sessionId?.trim());
}

export function saveAuthSession(payload: {
  access_token: string;
  user_id: string;
  full_name: string;
  session_id: string;
  role?: string;
}): void {
  localStorage.setItem(ACCESS_TOKEN_KEY, payload.access_token);
  localStorage.setItem(USER_ID_KEY, payload.user_id);
  localStorage.setItem(USER_NAME_KEY, payload.full_name);
  localStorage.setItem(SESSION_ID_KEY, payload.session_id);
  if (payload.role) localStorage.setItem(USER_ROLE_KEY, payload.role);
}

export function clearAuthSession(): void {
  localStorage.removeItem(ACCESS_TOKEN_KEY);
  localStorage.removeItem(USER_ID_KEY);
  localStorage.removeItem(USER_NAME_KEY);
  localStorage.removeItem(USER_ROLE_KEY);
  localStorage.removeItem(SESSION_ID_KEY);
}

/** Clear only stale conversation state while preserving the valid login. */
export function clearSessionId(): void {
  localStorage.removeItem(SESSION_ID_KEY);
}
