import React from "react";
import { Outlet } from "react-router-dom";
import { Sidebar } from "./Sidebar";
import { Topbar } from "./Topbar";
import { MobileNav } from "./MobileNav";

export const AppLayout: React.FC = () => {
  return (
    <div className="min-h-screen flex bg-[#F8F9FB] text-[#191C1E] dark:bg-[#0B0E11] dark:text-slate-100 font-sans antialiased transition-colors duration-200">
      <Sidebar />
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
