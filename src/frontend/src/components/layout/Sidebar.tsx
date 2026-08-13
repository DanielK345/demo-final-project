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

// Khi `collapsed`, sidebar tự mở ra lúc rê chuột qua (thuần CSS `:hover`/
// `:focus-within` — không qua state React, để phản hồi tức thì, không có độ trễ
// round-trip re-render). Toàn bộ set class dưới đây phải khớp y hệt trạng thái
// "ghim mở cố định" (collapsed=false) để lúc rê chuột trông y như đã mở thật, không
// phải bản xem trước nửa vời.
const REVEAL_JUSTIFY_START_ON_HOVER = "group-hover/sidebar:justify-start group-focus-within/sidebar:justify-start";

type SidebarProps = {
  collapsed: boolean;
  onToggleCollapse: () => void;
};

export const Sidebar: React.FC<SidebarProps> = ({ collapsed, onToggleCollapse }) => {
  return (
    <>
      {/* Ô giữ chỗ trong hàng flex — LUÔN giữ đúng bề rộng đã ghim (w-20/w-64), không
          đổi theo hover. Nhờ vậy nội dung chính bên cạnh không bị đẩy/giật mỗi lần rê
          chuột qua xem trước; sidebar thật (bên dưới) nổi đè lên trên như 1 lớp phủ. */}
      <div
        aria-hidden
        className={cn(
          "hidden md:block h-screen shrink-0 transition-[width]",
          COLLAPSE_TRANSITION,
          collapsed ? "w-20" : "w-64"
        )}
      />
      <aside
        className={cn(
          "hidden md:flex flex-col fixed left-0 top-0 h-screen border-r border-slate-200/70",
          "bg-white/95 backdrop-blur-xl shrink-0 z-50 py-6 relative group/sidebar",
          "transition-[width,padding,box-shadow] will-change-[width]",
          COLLAPSE_TRANSITION,
          "dark:border-white/10 dark:bg-[#0B0E11]/95",
          collapsed
            ? "w-20 px-2 hover:w-64 hover:px-4 hover:shadow-2xl focus-within:w-64 focus-within:px-4 focus-within:shadow-2xl"
            : "w-64 px-4"
        )}
      >
        {/* Nút thu/phóng — ghim mở cố định (bỏ chế độ tự mở/gập theo hover) hoặc gập
            lại về dải hẹp; luôn bấm được kể cả khi đang chỉ xem trước qua hover. */}
        <button
          type="button"
          onClick={onToggleCollapse}
          aria-label={collapsed ? "Ghim mở thanh điều hướng" : "Thu gọn thanh điều hướng"}
          title={collapsed ? "Ghim mở" : "Thu gọn"}
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
            nguyên 1 file ảnh, không cần thêm asset logo rút gọn riêng. Ảnh giữ NGUYÊN
            1 chiều cao cố định (h-12) ở mọi trạng thái — chỉ đổi bề rộng khung crop —
            để không phải đồng bộ 2 animation chiều cao khác nhau cùng lúc. */}
        <div
          className={cn(
            "mb-8 flex items-center",
            collapsed ? cn("px-0 justify-center", REVEAL_JUSTIFY_START_ON_HOVER, "group-hover/sidebar:px-2 group-focus-within/sidebar:px-2") : "px-2 justify-start"
          )}
        >
          <NavLink to="/" className="flex items-center group/logo">
            <div
              className={cn(
                "overflow-hidden shrink-0 h-12 transition-[width]",
                COLLAPSE_TRANSITION,
                collapsed ? "w-12 group-hover/sidebar:w-[168px] group-focus-within/sidebar:w-[168px]" : "w-[168px]"
              )}
            >
              <img
                src={logoSvg}
                alt="AloSM AI Booking Logo"
                className="h-12 w-auto max-w-none group-hover/logo:scale-102 transition-transform duration-200"
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
                      "transition-[background-color,color,padding,gap,justify-content] duration-200",
                      collapsed
                        ? cn("justify-center px-0 py-3 gap-0", REVEAL_JUSTIFY_START_ON_HOVER, "group-hover/sidebar:px-4 group-hover/sidebar:gap-4 group-focus-within/sidebar:px-4 group-focus-within/sidebar:gap-4")
                        : "gap-4 px-4 py-3 justify-start",
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
                          ngột (hidden/display:none), và tự hiện lại khi rê chuột qua
                          lúc đang thu gọn (group-hover/sidebar) — đây là phần quyết
                          định cảm giác "mượt" + "tự động". */}
                      <span
                        className={cn(
                          "overflow-hidden whitespace-nowrap transition-[width,opacity,margin]",
                          COLLAPSE_TRANSITION,
                          collapsed
                            ? cn(
                                "w-0 opacity-0 -ml-4",
                                "group-hover/sidebar:w-auto group-hover/sidebar:opacity-100 group-hover/sidebar:ml-0",
                                "group-focus-within/sidebar:w-auto group-focus-within/sidebar:opacity-100 group-focus-within/sidebar:ml-0"
                              )
                            : "w-auto opacity-100 ml-0"
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
            "transition-[padding,justify-content] duration-200",
            "dark:bg-white/5 dark:border-white/10 dark:text-slate-400",
            collapsed
              ? "justify-center px-2 py-3 group-hover/sidebar:justify-between group-hover/sidebar:px-4 group-focus-within/sidebar:justify-between group-focus-within/sidebar:px-4"
              : "justify-between px-4 py-3"
          )}
        >
          <div className="flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-[#00D1C1] animate-pulse shrink-0" />
            <span
              className={cn(
                "overflow-hidden whitespace-nowrap font-medium text-slate-700 transition-[width,opacity]",
                COLLAPSE_TRANSITION,
                "dark:text-slate-200",
                collapsed
                  ? cn(
                      "w-0 opacity-0",
                      "group-hover/sidebar:w-auto group-hover/sidebar:opacity-100",
                      "group-focus-within/sidebar:w-auto group-focus-within/sidebar:opacity-100"
                    )
                  : "w-auto opacity-100"
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
              collapsed
                ? cn(
                    "w-0 opacity-0",
                    "group-hover/sidebar:w-auto group-hover/sidebar:opacity-100",
                    "group-focus-within/sidebar:w-auto group-focus-within/sidebar:opacity-100"
                  )
                : "w-auto opacity-100"
            )}
          >
            v1.0
          </span>
        </div>
      </aside>
    </>
  );
};
