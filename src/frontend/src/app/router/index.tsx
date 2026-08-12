import React from "react";
import { createBrowserRouter, RouterProvider } from "react-router-dom";
import { RequireAuth } from "@/features/auth/RequireAuth";
import { AppLayout } from "@/components/layout/AppLayout";
import { AssistantPage } from "@/pages/Assistant/AssistantPage";
import { LoginPage } from "@/pages/Login/LoginPage";
import { HomePage } from "@/pages/Home/HomePage";
import { BookingPage } from "@/pages/Booking/BookingPage";
import { TrackingPage } from "@/pages/Tracking/TrackingPage";
import { ActivityPage } from "@/pages/Activity/ActivityPage";
import { PaymentPage } from "@/pages/Payment/PaymentPage";
import { ProfilePage } from "@/pages/Profile/ProfilePage";
import { NotFoundPage } from "@/pages/NotFound/NotFoundPage";

// `/login` và `/assistant` đứng riêng, KHÔNG bọc AppLayout — AssistantPage tự quản lý
// header/logout riêng, đã chạy thật và test kỹ, không đổi để tránh rủi ro không cần
// thiết. Các trang còn lại (trước đây không route nào trỏ tới, xem mustdo.md mục 1)
// giờ lồng trong AppLayout (Sidebar + Topbar + MobileNav, xem components/layout/) —
// đúng thiết kế gốc của Sidebar (nav item "/", "/booking", "/activity", "/payment",
// "/profile" đã có sẵn, chỉ chưa từng được route tới).
const router = createBrowserRouter([
  {
    path: "/login",
    element: <LoginPage />,
  },
  {
    path: "/assistant",
    element: (
      <RequireAuth>
        <AssistantPage />
      </RequireAuth>
    ),
  },
  {
    element: (
      <RequireAuth>
        <AppLayout />
      </RequireAuth>
    ),
    children: [
      { path: "/", element: <HomePage /> },
      { path: "/booking", element: <BookingPage /> },
      { path: "/tracking", element: <TrackingPage /> },
      { path: "/activity", element: <ActivityPage /> },
      { path: "/payment", element: <PaymentPage /> },
      { path: "/profile", element: <ProfilePage /> },
    ],
  },
  { path: "*", element: <NotFoundPage /> },
]);

export const AppRouter: React.FC = () => {
  return <RouterProvider router={router} />;
};
