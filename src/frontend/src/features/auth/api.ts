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

// /auth/login trả 1 trong 2 hình dạng thật tuỳ tài khoản có bật 2FA hay không — xem
// LoginResponseDTO (src/backend/schemas/auth.py). requires_2fa=true nghĩa là mật khẩu
// đã đúng nhưng CHƯA đăng nhập xong, phải gọi verifyTwoFactorLogin() với mã TOTP thật.
export interface TwoFactorChallenge {
  requires_2fa: true;
  pending_token: string;
}

export type LoginResult = TwoFactorChallenge | AuthResponse;

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

export function isTwoFactorChallenge(result: LoginResult): result is TwoFactorChallenge {
  return (result as TwoFactorChallenge).requires_2fa === true;
}

export async function login(phone: string, password: string): Promise<LoginResult> {
  return fetchApi<LoginResult>("/api/v1/auth/login", {
    method: "POST",
    body: JSON.stringify({ phone, password }),
  });
}

export async function verifyTwoFactorLogin(pendingToken: string, code: string): Promise<AuthResponse> {
  return fetchApi<AuthResponse>("/api/v1/auth/2fa/verify-login", {
    method: "POST",
    body: JSON.stringify({ pending_token: pendingToken, code }),
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
