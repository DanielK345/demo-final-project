import React, { useEffect } from "react";
import { createBrowserRouter, Navigate, RouterProvider } from "react-router-dom";
import { RequireAuth } from "@/features/auth/RequireAuth";
import { AppLayout } from "@/components/layout/AppLayout";
import { useVoiceAssistant } from "@/features/ai-assistant/context/useVoiceAssistant";
import { LoginPage } from "@/pages/Login/LoginPage";
import { HomePage } from "@/pages/Home/HomePage";
import { BookingPage } from "@/pages/Booking/BookingPage";
import { TrackingPage } from "@/pages/Tracking/TrackingPage";
import { ActivityPage } from "@/pages/Activity/ActivityPage";
import { PaymentPage } from "@/pages/Payment/PaymentPage";
import { ProfilePage } from "@/pages/Profile/ProfilePage";
import { NotFoundPage } from "@/pages/NotFound/NotFoundPage";
import { PoliciesPage } from "@/pages/Policies/PoliciesPage";
import { CookieConsentBanner } from "@/features/policies/CookieConsentBanner";

// Voice AI không còn là trang riêng "/assistant" — giờ là nút nổi + popup khả dụng ở
// mọi trang (xem AppLayout.tsx). Route này chỉ còn để không phá các đường dẫn cũ đã
// lưu/đánh dấu (bookmark) hay bất kỳ chỗ nào lỡ còn trỏ tới "/assistant": mở popup
// thay vì hiện trang 404, rồi quay về Trang chủ.
const AssistantRedirect: React.FC = () => {
  const { open } = useVoiceAssistant();
  useEffect(() => {
    open();
  }, [open]);
  return <Navigate to="/" replace />;
};

// `/login` đứng riêng (chưa đăng nhập, chưa có gì để điều hướng tới). Mọi trang sau
// đăng nhập giờ lồng trong AppLayout (Sidebar/Topbar/MobileNav + VoiceAssistantProvider)
// để LUÔN có thanh điều hướng sang màn khác và Voice AI khả dụng xuyên suốt.
const router = createBrowserRouter([
  {
    path: "/login",
    element: <LoginPage />,
  },
  {
    path: "/policies",
    element: <PoliciesPage />,
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
      { path: "/assistant", element: <AssistantRedirect /> },
    ],
  },
  { path: "*", element: <NotFoundPage /> },
]);

export const AppRouter: React.FC = () => (
  <>
    <RouterProvider router={router} />
    <CookieConsentBanner />
  </>
);
