import { createContext } from "react";

export type ThemeMode = "light" | "dark";

export interface ThemeContextValue {
  theme: ThemeMode;
  setTheme: (theme: ThemeMode) => void;
  toggleTheme: () => void;
}

// Tách riêng khỏi ThemeProvider.tsx: file đó chỉ nên export component (Fast Refresh
// của Vite yêu cầu file component không lẫn export khác — oxlint
// react(only-export-components) sẽ cảnh báo nếu gộp chung).
export const ThemeContext = createContext<ThemeContextValue | null>(null);
