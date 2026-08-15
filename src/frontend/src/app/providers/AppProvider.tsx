import React from "react";
import { QueryProvider } from "./QueryProvider";
import { ThemeProvider } from "./ThemeProvider";

export const AppProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  return (
    <ThemeProvider>
      <QueryProvider>{children}</QueryProvider>
    </ThemeProvider>
  );
};
