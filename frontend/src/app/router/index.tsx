import React from "react";
import { createBrowserRouter, RouterProvider } from "react-router-dom";
import { AppLayout } from "@/components/layout/AppLayout";
import { HomePage } from "@/pages/Home/HomePage";
import { BookingPage } from "@/pages/Booking/BookingPage";
import { ActivityPage } from "@/pages/Activity/ActivityPage";
import { AssistantPage } from "@/pages/Assistant/AssistantPage";
import { PaymentPage } from "@/pages/Payment/PaymentPage";
import { ProfilePage } from "@/pages/Profile/ProfilePage";
import { TrackingPage } from "@/pages/Tracking/TrackingPage";
import { LoginPage } from "@/pages/Login/LoginPage";
import { NotFoundPage } from "@/pages/NotFound/NotFoundPage";

const router = createBrowserRouter([
  {
    path: "/login",
    element: <LoginPage />,
  },
  {
    path: "/",
    element: <AppLayout />,
    children: [
      { index: true, element: <HomePage /> },
      { path: "booking", element: <BookingPage /> },
      { path: "activity", element: <ActivityPage /> },
      { path: "assistant", element: <AssistantPage /> },
      { path: "tracking", element: <TrackingPage /> },
      { path: "payment", element: <PaymentPage /> },
      { path: "settings", element: <PaymentPage /> },
      { path: "profile", element: <ProfilePage /> },
      { path: "*", element: <NotFoundPage /> },
    ],
  },
]);

export const AppRouter: React.FC = () => {
  return <RouterProvider router={router} />;
};
