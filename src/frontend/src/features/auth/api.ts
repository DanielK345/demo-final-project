import { fetchApi } from "@/app/config/api";
import { getAccessToken } from "@/features/auth/storage";

export interface AuthResponse {
  user_id: string;
  full_name: string;
  phone: string;
  role: "CUSTOMER";
  access_token: string;
  token_type: string;
  expires_in: number;
  session_id: string;
}

export interface CurrentUser {
  user_id: string;
  full_name: string;
  phone: string;
  role: "CUSTOMER";
  session_id: string | null;
}

function authHeader(): HeadersInit {
  const token = getAccessToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}

export async function login(phone: string, password: string): Promise<AuthResponse> {
  return fetchApi<AuthResponse>("/api/v1/auth/login", {
    method: "POST",
    body: JSON.stringify({ phone, password }),
  });
}

export async function register(fullName: string, phone: string, password: string): Promise<AuthResponse> {
  return fetchApi<AuthResponse>("/api/v1/auth/register", {
    method: "POST",
    body: JSON.stringify({ full_name: fullName, phone, password }),
  });
}

export async function getCurrentUser(): Promise<CurrentUser> {
  return fetchApi<CurrentUser>("/api/v1/auth/me", {
    headers: authHeader(),
  });
}
