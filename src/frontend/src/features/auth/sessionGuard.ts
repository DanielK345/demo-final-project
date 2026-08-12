import { isUnauthorizedError } from "@/app/config/api";
import { clearAuthSession } from "@/features/auth/storage";

export function redirectToLoginIfUnauthorized(
  error: unknown,
  navigate: (path: string, options?: { replace?: boolean }) => void,
): boolean {
  if (!isUnauthorizedError(error)) return false;
  clearAuthSession();
  navigate("/login", { replace: true });
  return true;
}
