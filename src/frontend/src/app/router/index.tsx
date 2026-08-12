import React from "react";
import { createBrowserRouter, RouterProvider } from "react-router-dom";
import { RequireAuth } from "@/features/auth/RequireAuth";
import { AssistantPage } from "@/pages/Assistant/AssistantPage";
import { LoginPage } from "@/pages/Login/LoginPage";

const router = createBrowserRouter([
  {
    path: "/login",
    element: <LoginPage />,
  },
  {
    path: "/",
    element: (
      <RequireAuth>
        <AssistantPage />
      </RequireAuth>
    ),
  },
  { path: "*", element: <LoginPage /> },
]);

export const AppRouter: React.FC = () => {
  return <RouterProvider router={router} />;
};
