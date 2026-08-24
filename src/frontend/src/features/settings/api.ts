import { API_BASE_URL, ApiError, extractErrorMessage, fetchApi } from "@/app/config/api";
import { getAccessToken } from "@/features/auth/storage";

export interface UserSettings {
  push_notifications: boolean;
  email_notifications: boolean;
  sms_notifications: boolean;
  two_factor_enabled: boolean;
  language: string;
  theme: string;
}

function authHeader(): HeadersInit {
  const token = getAccessToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}

export function getSettings(): Promise<UserSettings> {
  return fetchApi<UserSettings>("/api/v1/users/me/settings", { headers: authHeader() });
}

export function updateSettings(updates: Partial<UserSettings>): Promise<UserSettings> {
  return fetchApi<UserSettings>("/api/v1/users/me/settings", {
    method: "PUT",
    headers: authHeader(),
    body: JSON.stringify(updates),
  });
}

// 2FA thật (TOTP) — `two_factor_enabled` ở UserSettings giờ chỉ để HIỂN THỊ, không
// còn set được qua updateSettings() nữa (xem UpdateUserSettingsDTO ở backend). Bật/tắt
// phải qua đúng luồng bên dưới.
export interface TwoFactorSetup {
  secret: string;
  otpauth_url: string;
}

export interface TwoFactorStatus {
  two_factor_enabled: boolean;
}

export function setupTwoFactor(): Promise<TwoFactorSetup> {
  return fetchApi<TwoFactorSetup>("/api/v1/auth/2fa/setup", {
    method: "POST",
    headers: authHeader(),
  });
}

export function confirmTwoFactor(code: string): Promise<TwoFactorStatus> {
  return fetchApi<TwoFactorStatus>("/api/v1/auth/2fa/confirm", {
    method: "POST",
    headers: authHeader(),
    body: JSON.stringify({ code }),
  });
}

export function disableTwoFactor(): Promise<TwoFactorStatus> {
  return fetchApi<TwoFactorStatus>("/api/v1/auth/2fa/disable", {
    method: "POST",
    headers: authHeader(),
  });
}

export async function changePassword(oldPassword: string, newPassword: string): Promise<void> {
  // Không dùng fetchApi() ở đây: backend trả 204 No Content khi thành công, còn
  // fetchApi() luôn gọi response.json() -- ném SyntaxError trên body rỗng.
  const response = await fetch(`${API_BASE_URL}/api/v1/auth/change-password`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...authHeader() },
    body: JSON.stringify({ old_password: oldPassword, new_password: newPassword }),
  });
  if (!response.ok) {
    const errorBody = await response.json().catch(() => null);
    throw new ApiError(extractErrorMessage(errorBody, response.status), response.status);
  }
}
