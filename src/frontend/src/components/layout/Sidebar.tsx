import React from "react";
import { NavLink } from "react-router-dom";
import { Home, Grid, History, Sparkles, Settings, User } from "lucide-react";
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

// Cùng 1 easing/duration cho mọi phần tử ăn theo lúc rê chuột mở/thu — lệch timing
// giữa các phần (khung, chữ) là nguyên nhân phổ biến khiến animation trông "giật"
// thay vì mượt.
const COLLAPSE_TRANSITION = "duration-300 ease-in-out";

// Sidebar luôn ở dải hẹp (w-20) mặc định, tự mở ra khi rê chuột qua và tự thu lại
// khi rê ra — thuần CSS `:hover`/`:focus-within` (Tailwind named group
// `group/sidebar`), không qua state React, để phản hồi tức thì, không có độ trễ
// round-trip re-render. (Trước đây có thêm nút ghim mở cố định thủ công — đã bỏ vì
// lỗi; giờ chỉ còn đúng 1 cơ chế duy nhất, tự động hoàn toàn.) `:focus-within` đảm
// bảo người dùng bàn phím (Tab) cũng thấy được nhãn mà không cần chuột.
const REVEAL_JUSTIFY_START_ON_HOVER = "group-hover/sidebar:justify-start group-focus-within/sidebar:justify-start";

export const Sidebar: React.FC = () => {
  return (
    <>
      {/* Ô giữ chỗ trong hàng flex — LUÔN giữ đúng bề rộng dải hẹp (w-20), không đổi
          theo hover. Nhờ vậy nội dung chính bên cạnh không bị đẩy/giật mỗi lần rê
          chuột qua xem trước; sidebar thật (bên dưới) nổi đè lên trên như 1 lớp phủ. */}
      <div aria-hidden className="hidden md:block h-screen w-20 shrink-0" />
      <aside
        className={cn(
          "hidden md:flex flex-col fixed left-0 top-0 h-screen border-r border-slate-200/70",
          "bg-white/95 backdrop-blur-xl shrink-0 z-50 py-6 relative group/sidebar",
          "w-20 px-2 hover:w-64 hover:px-4 hover:shadow-2xl focus-within:w-64 focus-within:px-4 focus-within:shadow-2xl",
          "transition-[width,padding,box-shadow] will-change-[width]",
          COLLAPSE_TRANSITION,
          "dark:border-white/10 dark:bg-[#0B0E11]/95"
        )}
      >
        {/* Brand Header with Official AloSM AI Booking Logo — mặc định crop logo về
            đúng phần icon vuông bên trái (viewBox logo.svg đặt icon ở x:0-80/280), lộ
            đầy đủ logo khi rê chuột mở ra. Giữ nguyên 1 file ảnh, không cần thêm asset
            logo rút gọn riêng. Ảnh giữ NGUYÊN 1 chiều cao cố định (h-12) ở mọi trạng
            thái — chỉ đổi bề rộng khung crop — để không phải đồng bộ 2 animation
            chiều cao khác nhau cùng lúc. */}
        <div
          className={cn(
            "mb-8 flex items-center px-0 justify-center",
            REVEAL_JUSTIFY_START_ON_HOVER,
            "group-hover/sidebar:px-2 group-focus-within/sidebar:px-2"
          )}
        >
          <NavLink to="/" className="flex items-center group/logo">
            <div
              className={cn(
                "overflow-hidden shrink-0 h-12 w-12 transition-[width]",
                COLLAPSE_TRANSITION,
                "group-hover/sidebar:w-[168px] group-focus-within/sidebar:w-[168px]"
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
                  title={item.label}
                  className={({ isActive }) =>
                    cn(
                      "flex items-center rounded-xl text-sm font-semibold active:scale-95",
                      "justify-center px-0 py-3 gap-0",
                      REVEAL_JUSTIFY_START_ON_HOVER,
                      "group-hover/sidebar:px-4 group-hover/sidebar:gap-4 group-focus-within/sidebar:px-4 group-focus-within/sidebar:gap-4",
                      "transition-[background-color,color,padding,gap,justify-content] duration-200",
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
                          (group-hover/sidebar) — đây là phần quyết định cảm giác
                          "mượt" + "tự động". */}
                      <span
                        className={cn(
                          "overflow-hidden whitespace-nowrap w-0 opacity-0 -ml-4",
                          "group-hover/sidebar:w-auto group-hover/sidebar:opacity-100 group-hover/sidebar:ml-0",
                          "group-focus-within/sidebar:w-auto group-focus-within/sidebar:opacity-100 group-focus-within/sidebar:ml-0",
                          "transition-[width,opacity,margin]",
                          COLLAPSE_TRANSITION
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
            "justify-center px-2 py-3",
            "group-hover/sidebar:justify-between group-hover/sidebar:px-4 group-focus-within/sidebar:justify-between group-focus-within/sidebar:px-4",
            "transition-[padding,justify-content] duration-200",
            "dark:bg-white/5 dark:border-white/10 dark:text-slate-400"
          )}
        >
          <div className="flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-[#00D1C1] animate-pulse shrink-0" />
            <span
              className={cn(
                "overflow-hidden whitespace-nowrap font-medium text-slate-700 w-0 opacity-0",
                "group-hover/sidebar:w-auto group-hover/sidebar:opacity-100",
                "group-focus-within/sidebar:w-auto group-focus-within/sidebar:opacity-100",
                "transition-[width,opacity]",
                COLLAPSE_TRANSITION,
                "dark:text-slate-200"
              )}
            >
              Online
            </span>
          </div>
          <span
            className={cn(
              "overflow-hidden whitespace-nowrap text-[10px] font-mono text-slate-400 w-0 opacity-0",
              "group-hover/sidebar:w-auto group-hover/sidebar:opacity-100",
              "group-focus-within/sidebar:w-auto group-focus-within/sidebar:opacity-100",
              "transition-[width,opacity]",
              COLLAPSE_TRANSITION,
              "dark:text-slate-500"
            )}
          >
            v1.0
          </span>
        </div>
      </aside>
    </>
  );
};
