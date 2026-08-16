import React from "react";
import { NavLink } from "react-router-dom";
import { Home, Grid, History, User } from "lucide-react";
import { cn } from "@/utils/cn";

const mobileItems = [
  { path: "/", label: "Home", icon: Home },
  { path: "/booking", label: "Dịch vụ", icon: Grid },
  { path: "/activity", label: "Hoạt động", icon: History },
  { path: "/profile", label: "Tài khoản", icon: User },
];

export const MobileNav: React.FC = () => {
  return (
    <nav className="md:hidden fixed bottom-5 left-1/2 -translate-x-1/2 w-[calc(100%-2rem)] max-w-md h-[72px] px-2 bg-white/88 backdrop-blur-2xl border border-white/90 rounded-[28px] flex items-center justify-around z-50 shadow-[0_16px_48px_rgba(19,73,74,0.2)] dark:bg-[#102021]/90 dark:border-white/10">
      {mobileItems.map((item) => {
        const Icon = item.icon;
        return (
          <NavLink
            key={item.path}
            to={item.path}
            end
            className={({ isActive }) =>
              cn(
                "relative min-w-14 h-14 rounded-[22px] flex flex-col items-center justify-center gap-0.5 text-xs font-semibold transition-all duration-200",
                isActive
                  ? "text-[#00C9B7] bg-[#E7FBF9] shadow-[inset_0_0_0_1px_rgba(0,201,183,.16),0_6px_18px_rgba(0,201,183,.2)] dark:bg-[#00C9B7]/15"
                  : "text-slate-500 hover:text-[#008F88] dark:text-slate-400 dark:hover:text-[#00C9B7]"
              )
            }
          >
            <Icon className="w-5 h-5" />
            <span className="text-[9px]">{item.label}</span>
          </NavLink>
        );
      })}
    </nav>
  );
};
