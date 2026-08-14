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
    <nav className="md:hidden fixed bottom-0 left-0 w-full bg-white/90 backdrop-blur-xl border-t border-slate-200/80 flex justify-around py-2.5 pb-5 z-50 shadow-lg dark:bg-[#0B0E11]/95 dark:border-white/10">
      {mobileItems.map((item) => {
        const Icon = item.icon;
        return (
          <NavLink
            key={item.path}
            to={item.path}
            end
            className={({ isActive }) =>
              cn(
                "flex flex-col items-center gap-1 text-xs font-semibold transition-colors",
                isActive
                  ? "text-[#00D1C1]"
                  : "text-slate-500 hover:text-[#006a62] dark:text-slate-400 dark:hover:text-[#00D1C1]"
              )
            }
          >
            <Icon className="w-5 h-5" />
            <span className="text-[11px]">{item.label}</span>
          </NavLink>
        );
      })}
    </nav>
  );
};
