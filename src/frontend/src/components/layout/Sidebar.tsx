import React from "react";
import { NavLink } from "react-router-dom";
import {
  Home,
  Grid,
  History,
  Sparkles,
  Settings,
  User,
  PanelLeftClose,
  PanelLeftOpen,
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

// Cùng 1 easing/duration cho mọi phần tử ăn theo lúc thu/phóng — lệch timing giữa
// các phần (khung, chữ, nút) là nguyên nhân phổ biến khiến animation trông "giật"
// thay vì mượt.
const COLLAPSE_TRANSITION = "duration-300 ease-in-out";

type SidebarProps = {
  collapsed: boolean;
  onToggleCollapse: () => void;
};

export const Sidebar: React.FC<SidebarProps> = ({ collapsed, onToggleCollapse }) => {
  return (
    <aside
      className={cn(
        "hidden md:flex flex-col border-r border-slate-200/70 bg-white/80 backdrop-blur-xl shrink-0 h-screen sticky top-0 z-50 py-6 relative",
        "transition-[width,padding] will-change-[width]",
        COLLAPSE_TRANSITION,
        "dark:border-white/10 dark:bg-[#0B0E11]/95",
        collapsed ? "w-20 px-2" : "w-64 px-4"
      )}
    >
      {/* Nút thu/phóng — nổi trên viền phải, luôn bấm được kể cả khi đã thu gọn */}
      <button
        type="button"
        onClick={onToggleCollapse}
        aria-label={collapsed ? "Mở rộng thanh điều hướng" : "Thu gọn thanh điều hướng"}
        title={collapsed ? "Mở rộng" : "Thu gọn"}
        className={cn(
          "absolute -right-3 top-9 w-6 h-6 rounded-full grid place-items-center z-10",
          "bg-white border border-slate-200 text-slate-500 shadow-sm cursor-pointer",
          "hover:text-[#006a62] hover:border-[#00D1C1]/50 hover:scale-110 active:scale-95",
          "transition-all duration-200",
          "dark:bg-[#12161A] dark:border-white/10 dark:text-slate-400 dark:hover:text-[#00D1C1]"
        )}
      >
        {collapsed ? <PanelLeftOpen className="w-3.5 h-3.5" /> : <PanelLeftClose className="w-3.5 h-3.5" />}
      </button>

      {/* Brand Header with Official AloSM AI Booking Logo — thu lại thì crop logo về
          đúng phần icon vuông bên trái (viewBox logo.svg đặt icon ở x:0-80/280), giữ
          nguyên 1 file ảnh, không cần thêm asset logo rút gọn riêng. */}
      <div className={cn("mb-8 flex items-center", collapsed ? "px-0 justify-center" : "px-2")}>
        <NavLink to="/" className="flex items-center group">
          <div
            className={cn(
              "overflow-hidden shrink-0 transition-[width]",
              COLLAPSE_TRANSITION,
              collapsed ? "w-10 h-10" : "w-[168px] h-12"
            )}
          >
            <img
              src={logoSvg}
              alt="AloSM AI Booking Logo"
              className={cn(
                // Chiều cao PHẢI khớp đúng chiều cao container ở cả 2 trạng thái —
                // lệch chiều cao sẽ khiến overflow-hidden cắt luôn theo chiều dọc
                // (mất nửa icon) thay vì chỉ cắt ngang phần chữ "AloSM" như ý muốn.
                "w-auto max-w-none group-hover:scale-102 transition-[height,transform] duration-200",
                collapsed ? "h-10" : "h-12"
              )}
            />
          </div>
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
                title={collapsed ? item.label : undefined}
                className={({ isActive }) =>
                  cn(
                    "flex items-center rounded-xl text-sm font-semibold active:scale-95",
                    "transition-[background-color,color,padding,justify-content] duration-200",
                    collapsed ? "justify-center px-0 py-3" : "gap-4 px-4 py-3",
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
                        "w-5 h-5 shrink-0 transition-transform duration-200",
                        isActive ? "text-[#00D1C1]" : "text-slate-500 dark:text-slate-400"
                      )}
                    />
                    {/* Chữ nhãn trượt/mờ dần theo width+opacity thay vì biến mất đột
                        ngột (hidden/display:none) — đây là phần quyết định cảm giác
                        "mượt" khi thu gọn. */}
                    <span
                      className={cn(
                        "overflow-hidden whitespace-nowrap transition-[width,opacity,margin]",
                        COLLAPSE_TRANSITION,
                        collapsed ? "w-0 opacity-0 -ml-4" : "w-auto opacity-100 ml-0"
                      )}
                    >
                      {item.label}
                    </span>
                  </>
                )}
              </NavLink>
            </li>
          );
        })}
      </ul>

      {/* Bottom Status / Footer info */}
      <div
        className={cn(
          "rounded-xl bg-slate-100/80 border border-slate-200/60 text-xs text-slate-500 flex items-center",
          "transition-[padding,justify-content]",
          COLLAPSE_TRANSITION,
          "dark:bg-white/5 dark:border-white/10 dark:text-slate-400",
          collapsed ? "justify-center px-2 py-3" : "justify-between px-4 py-3"
        )}
      >
        <div className="flex items-center gap-2">
          <span className="w-2 h-2 rounded-full bg-[#00D1C1] animate-pulse shrink-0" />
          <span
            className={cn(
              "overflow-hidden whitespace-nowrap font-medium text-slate-700 transition-[width,opacity]",
              COLLAPSE_TRANSITION,
              "dark:text-slate-200",
              collapsed ? "w-0 opacity-0" : "w-auto opacity-100"
            )}
          >
            Online
          </span>
        </div>
        <span
          className={cn(
            "overflow-hidden whitespace-nowrap text-[10px] font-mono text-slate-400 transition-[width,opacity]",
            COLLAPSE_TRANSITION,
            "dark:text-slate-500",
            collapsed ? "w-0 opacity-0" : "w-auto opacity-100"
          )}
        >
          v1.0
        </span>
      </div>
    </aside>
  );
};
