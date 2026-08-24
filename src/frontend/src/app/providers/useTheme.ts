import { useContext } from "react";
import { ThemeContext, type ThemeContextValue } from "./theme-context";

export function useTheme(): ThemeContextValue {
  const ctx = useContext(ThemeContext);
  if (!ctx) {
    throw new Error("useTheme phải được dùng bên trong <ThemeProvider>");
  }
  return ctx;
}
