import React from "react";
import { Navigate, useLocation } from "react-router-dom";
import { getUserRole } from "./storage";

export const RequireRole: React.FC<{ roles: string[]; children: React.ReactNode }> = ({ roles, children }) => {
  const location = useLocation();
  const role = getUserRole();
  if (!roles.includes(role || "")) {
    return <Navigate to="/" replace state={{ from: location.pathname }} />;
  }
  return <>{children}</>;
};
