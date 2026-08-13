import React from "react";
import { NavLink } from "react-router-dom";
import {
  Home,
  Grid,
  History,
  Sparkles,
  Settings,
  User,
} from "lucide-react";
import { cn } from "@/utils/cn";
import logoSvg from "@/assets/logo.svg";

const navItems = [
  { path: "/", label: "Home", icon: Home },
  { path: "/booking", label: "Services", icon: Grid },
  { path: "/activity", label: "Activity", icon: History },
  { path: "/assistant", label: "AI Assistant", icon: Sparkles },
  { path: "/payment", label: "Settings", icon: Settings },
  { path: "/profile", label: "Account", icon: User },
];

export const Sidebar: React.FC = () => {
  return (
    <aside className="hidden md:flex flex-col w-64 border-r border-slate-200/70 bg-white/80 backdrop-blur-xl shrink-0 h-screen sticky top-0 z-50 py-6 px-4 dark:border-white/10 dark:bg-[#0B0E11]/95">
      {/* Brand Header with Official AloSM AI Booking Logo */}
      <div className="mb-8 px-2">
        <NavLink to="/" className="flex items-center group">
          <img
            src={logoSvg}
            alt="AloSM AI Booking Logo"
            className="h-12 w-auto group-hover:scale-102 transition-transform duration-200"
          />
        </NavLink>
      </div>

      {/* Main Navigation */}
      <ul className="flex flex-col gap-2 flex-1">
        {navItems.map((item) => {
          const Icon = item.icon;
          return (
            <li key={item.path}>
              <NavLink
                to={item.path}
                end
                className={({ isActive }) =>
                  cn(
                    "flex items-center gap-4 px-4 py-3 rounded-xl text-sm font-semibold transition-all duration-200 active:scale-95",
                    isActive
                      ? "text-[#006a62] bg-[#00D1C1]/10 font-bold shadow-xs dark:text-[#00D1C1] dark:bg-[#00D1C1]/15"
                      : "text-slate-600 hover:bg-[#00D1C1]/10 hover:text-[#006a62] dark:text-slate-400 dark:hover:bg-white/10 dark:hover:text-[#00D1C1]"
                  )
                }
              >
                {({ isActive }) => (
                  <>
                    <Icon
                      className={cn(
                        "w-5 h-5 transition-transform duration-200",
                        isActive ? "text-[#00D1C1]" : "text-slate-500 dark:text-slate-400"
                      )}
                    />
                    <span>{item.label}</span>
                  </>
                )}
              </NavLink>
            </li>
          );
        })}
      </ul>

      {/* Bottom Status / Footer info */}
      <div className="px-4 py-3 rounded-xl bg-slate-100/80 border border-slate-200/60 text-xs text-slate-500 flex items-center justify-between dark:bg-white/5 dark:border-white/10 dark:text-slate-400">
        <div className="flex items-center gap-2">
          <span className="w-2 h-2 rounded-full bg-[#00D1C1] animate-pulse" />
          <span className="font-medium text-slate-700 dark:text-slate-200">Online</span>
        </div>
        <span className="text-[10px] font-mono text-slate-400 dark:text-slate-500">v1.0</span>
      </div>
    </aside>
  );
};
