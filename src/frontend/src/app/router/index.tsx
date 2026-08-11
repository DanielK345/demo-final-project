import React from "react";
import { createBrowserRouter, RouterProvider } from "react-router-dom";
import { AssistantPage } from "@/pages/Assistant/AssistantPage";
import { LoginPage } from "@/pages/Login/LoginPage";

const router = createBrowserRouter([
  {
    path: "/login",
    element: <LoginPage />,
  },
  { path: "/", element: <AssistantPage /> },
  { path: "*", element: <LoginPage /> },
]);

export const AppRouter: React.FC = () => {
  return <RouterProvider router={router} />;
};
