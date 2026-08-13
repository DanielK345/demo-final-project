import React, { useState } from "react";
import { Outlet } from "react-router-dom";
import { Sidebar } from "./Sidebar";
import { Topbar } from "./Topbar";
import { MobileNav } from "./MobileNav";

const SIDEBAR_COLLAPSED_KEY = "alosm_sidebar_collapsed";

function readStoredCollapsed(): boolean {
  try {
    return window.localStorage.getItem(SIDEBAR_COLLAPSED_KEY) === "1";
  } catch {
    return false;
  }
}

export const AppLayout: React.FC = () => {
  // Trạng thái thu/phóng sống ở đây (cha chung của Sidebar + khu nội dung chính) —
  // không cần Context riêng vì chỉ 2 component dùng. Nhớ lựa chọn qua localStorage
  // giống ThemeProvider, để không phải thu lại mỗi lần chuyển trang/tải lại.
  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState(readStoredCollapsed);

  const toggleSidebar = () => {
    setIsSidebarCollapsed((current) => {
      const next = !current;
      try {
        window.localStorage.setItem(SIDEBAR_COLLAPSED_KEY, next ? "1" : "0");
      } catch {
        // Bỏ qua nếu không lưu được — vẫn áp dụng cho phiên hiện tại.
      }
      return next;
    });
  };

  return (
    <div className="min-h-screen flex bg-[#F8F9FB] text-[#191C1E] dark:bg-[#0B0E11] dark:text-slate-100 font-sans antialiased transition-colors duration-200">
      <Sidebar collapsed={isSidebarCollapsed} onToggleCollapse={toggleSidebar} />
      {/* Không cần margin/width thủ công cho khu này — Sidebar co giãn trong cùng 1
          flex row, div flex-1 này tự nới rộng ra theo, mượt cùng nhịp với transition
          width của Sidebar (xem Sidebar.tsx) mà không bị giật/lệch khung 1 nhịp. */}
      <div className="flex-1 flex flex-col min-w-0 pb-24 md:pb-12">
        <Topbar />
        <main className="flex-1 pt-6 px-4 md:px-12 max-w-[1440px] w-full mx-auto">
          <Outlet />
        </main>
      </div>
      <MobileNav />
    </div>
  );
};
