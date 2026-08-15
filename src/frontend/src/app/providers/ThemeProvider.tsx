import React, { useCallback, useEffect, useState } from "react";
import { ThemeContext, type ThemeMode } from "./theme-context";

const STORAGE_KEY = "alosm_theme";

function readStoredTheme(): ThemeMode {
  try {
    return window.localStorage.getItem(STORAGE_KEY) === "dark" ? "dark" : "light";
  } catch {
    // localStorage có thể bị chặn (chế độ riêng tư nghiêm ngặt) — mặc định sáng.
    return "light";
  }
}

function applyThemeClass(theme: ThemeMode) {
  document.documentElement.classList.toggle("dark", theme === "dark");
}

/**
 * Theme áp dụng cho TOÀN BỘ website (không chỉ riêng 1 trang) qua class "dark"
 * trên <html>, kết hợp với biến thể `dark:` của Tailwind (xem index.css).
 *
 * Nguồn sự thật:
 * - localStorage (`alosm_theme`) — áp ngay lập tức, kể cả trước khi đăng nhập
 *   (đọc đồng bộ trong index.html để tránh nháy sáng->tối khi tải trang).
 * - Cài đặt trên backend (`GET/PUT /users/me/settings`, field `theme`) — đồng
 *   bộ giữa các thiết bị; trang Cài đặt gọi `setTheme()` (xem hook `useTheme`
 *   trong useTheme.ts) song song với việc lưu backend (xem PaymentPage.tsx), và
 *   tự đồng bộ lại khi tải xong settings nếu 2 nguồn lệch nhau.
 */
export const ThemeProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [theme, setThemeState] = useState<ThemeMode>(readStoredTheme);

  useEffect(() => {
    applyThemeClass(theme);
  }, [theme]);

  const setTheme = useCallback((next: ThemeMode) => {
    setThemeState(next);
    try {
      window.localStorage.setItem(STORAGE_KEY, next);
    } catch {
      // Bỏ qua nếu không lưu được — theme vẫn áp dụng cho phiên hiện tại.
    }
  }, []);

  const toggleTheme = useCallback(() => {
    setThemeState((current) => {
      const next = current === "dark" ? "light" : "dark";
      try {
        window.localStorage.setItem(STORAGE_KEY, next);
      } catch {
        // Bỏ qua nếu không lưu được.
      }
      return next;
    });
  }, []);

  return (
    <ThemeContext.Provider value={{ theme, setTheme, toggleTheme }}>
      {children}
    </ThemeContext.Provider>
  );
};
