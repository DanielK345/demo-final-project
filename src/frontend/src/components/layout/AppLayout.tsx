import React from "react";
import { Outlet } from "react-router-dom";
import { Sidebar } from "./Sidebar";
import { Topbar } from "./Topbar";
import { MobileNav } from "./MobileNav";
import { VoiceAssistantProvider } from "@/features/ai-assistant/context/VoiceAssistantContext";
import { VoiceAIButton } from "@/features/ai-assistant/components/VoiceAIButton";
import { VoiceAssistantPopup } from "@/features/ai-assistant/components/VoiceAssistantPopup";

export const AppLayout: React.FC = () => {
  return (
    // Provider bọc TOÀN BỘ layout (không chỉ 1 trang) — Voice AI giờ là 1 nút nổi +
    // popup khả dụng ở MỌI trang sau đăng nhập (mục 2-3), không còn là trang
    // "/assistant" riêng. Mounted đúng 1 lần ở đây nên đóng/mở popup hay chuyển trang
    // không làm mất phiên hội thoại đang dở (Scenario 6, mục 26).
    <VoiceAssistantProvider>
      <div className="app-surface min-h-screen flex bg-[#F4FBFA] text-[#191C1E] dark:bg-[#0B0E11] dark:text-slate-100 font-sans antialiased transition-colors duration-200">
        {/* Sidebar tự thu/phóng theo rê chuột (thuần CSS, xem Sidebar.tsx) — không còn
            nút ghim mở cố định (đã gỡ vì lỗi), nên không cần state/localStorage nào ở
            đây nữa. */}
        <Sidebar />
        {/* Không cần margin/width thủ công cho khu này — Sidebar co giãn trong cùng 1
            flex row, div flex-1 này tự nới rộng ra theo, mượt cùng nhịp với transition
            width của Sidebar (xem Sidebar.tsx) mà không bị giật/lệch khung 1 nhịp. */}
        <div className="flex-1 flex flex-col min-w-0 pb-32 md:pb-12">
          <Topbar />
          <main className="flex-1 pt-5 px-4 sm:px-6 md:px-10 max-w-[1280px] w-full mx-auto">
            <Outlet />
          </main>
        </div>
        <MobileNav />
        <VoiceAIButton />
        <VoiceAssistantPopup />
      </div>
    </VoiceAssistantProvider>
  );
};
