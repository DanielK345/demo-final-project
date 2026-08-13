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

// `/login` đứng riêng (chưa đăng nhập, chưa có gì để điều hướng tới). Mọi trang sau
// đăng nhập — kể cả `/assistant` — giờ lồng trong AppLayout (Sidebar/Topbar/
// MobileNav) để LUÔN có thanh điều hướng sang màn khác, theo đúng yêu cầu (trước đây
// AssistantPage đứng riêng, chỉ có 1 link "Trang chủ" tự chế — không phải taskbar
// thật). AssistantPage tự vẽ nền tối riêng cho khu vực nội dung của nó (xem
// AssistantPage.tsx), Sidebar/Topbar vẫn giữ giao diện sáng nhất quán với các trang
// khác — tránh đổi nguyên bộ khung sang tối (ảnh hưởng mọi trang, rủi ro/công sức lớn
// hơn nhiều so với yêu cầu).
const router = createBrowserRouter([
  {
    path: "/login",
    element: <LoginPage />,
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
      { path: "/assistant", element: <AssistantPage /> },
    ],
  },
  { path: "*", element: <NotFoundPage /> },
]);

export const AppRouter: React.FC = () => {
  return <RouterProvider router={router} />;
};
