import React, { useState, useRef, useEffect } from "react";
import { Search, Bell, User, LogOut, Wallet, Shield } from "lucide-react";
import { IconButton } from "@/components/ui/IconButton";
import logoSvg from "@/assets/logo.svg";
import { NavLink, useNavigate } from "react-router-dom";
import { clearAuthSession, getUserName } from "@/features/auth/storage";

export const Topbar: React.FC = () => {
  const [isMenuOpen, setIsMenuOpen] = useState(false);
  const [isNotifOpen, setIsNotifOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);
  const notifRef = useRef<HTMLDivElement>(null);
  const navigate = useNavigate();
  const userName = getUserName();
  const initials = userName
    .split(" ")
    .filter(Boolean)
    .slice(-2)
    .map((part) => part[0]?.toUpperCase())
    .join("") || "?";

  // Close dropdown when clicking outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setIsMenuOpen(false);
      }
      if (notifRef.current && !notifRef.current.contains(event.target as Node)) {
        setIsNotifOpen(false);
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  const handleLogout = () => {
    setIsMenuOpen(false);
    // BUG thật đã sửa: bản cũ chỉ navigate("/login") mà KHÔNG xoá session — token vẫn
    // còn trong localStorage, RequireAuth vẫn coi là đã đăng nhập.
    clearAuthSession();
    navigate("/login");
  };

  return (
    <header className="flex justify-between items-center h-16 px-4 md:px-8 sticky top-0 z-40 bg-white/80 backdrop-blur-xl border-b border-slate-200/60 shadow-xs dark:bg-[#0B0E11]/90 dark:border-white/10">
      {/* Mobile Brand Logo */}
      <div className="md:hidden">
        <NavLink to="/">
          <img src={logoSvg} alt="AloSM AI Booking" className="h-9 w-auto" />
        </NavLink>
      </div>

      <div className="flex-1 hidden md:block" />

      {/* Right Search & Icons */}
      <div className="flex items-center gap-4">
        {/* Search Input */}
        <div className="relative w-48 sm:w-64 focus-within:ring-2 focus-within:ring-[#00D1C1]/20 rounded-xl transition-all">
          <Search className="w-4 h-4 absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-400 dark:text-slate-500" />
          <input
            type="text"
            placeholder="Tìm kiếm..."
            className="w-full h-10 pl-10 pr-4 bg-slate-50 rounded-xl border border-slate-200 focus:outline-none focus:border-[#00D1C1] text-xs font-medium text-slate-800 placeholder:text-slate-400 transition-all dark:bg-white/5 dark:border-white/10 dark:text-slate-100 dark:placeholder:text-slate-500"
          />
        </div>

        {/* Notifications — trước đây bấm không có phản ứng gì (không có handler);
            chưa có hệ thống thông báo thật nên chỉ báo trạng thái trung thực thay vì
            giả vờ có danh sách thông báo. */}
        <div className="relative" ref={notifRef}>
          <IconButton
            icon={<Bell className="w-5 h-5 text-slate-600 hover:text-[#006a62] dark:text-slate-300 dark:hover:text-[#00D1C1]" />}
            label="Notifications"
            variant="ghost"
            size="md"
            onClick={() => setIsNotifOpen((open) => !open)}
            className={`rounded-full transition-all ${isNotifOpen ? "bg-[#00D1C1]/20 text-[#006a62]" : "hover:bg-slate-100 dark:hover:bg-white/10"}`}
          />
          {isNotifOpen && (
            <div className="absolute right-0 mt-2 w-64 bg-white rounded-2xl shadow-[0_8px_30px_rgba(0,0,0,0.12)] border border-slate-200/80 p-4 z-50 text-center dark:bg-[#12161A] dark:border-white/10">
              <p className="text-xs text-slate-500 dark:text-slate-400">Chưa có thông báo mới.</p>
            </div>
          )}
        </div>

        {/* Account Avatar Button with Dropdown */}
        <div className="relative" ref={dropdownRef}>
          <IconButton
            icon={<User className="w-5 h-5 text-slate-600 hover:text-[#006a62] dark:text-slate-300 dark:hover:text-[#00D1C1]" />}
            label="Account"
            variant="ghost"
            size="md"
            onClick={() => setIsMenuOpen(!isMenuOpen)}
            className={`rounded-full transition-all ${
              isMenuOpen ? "bg-[#00D1C1]/20 text-[#006a62]" : "hover:bg-slate-100 dark:hover:bg-white/10"
            }`}
          />

          {/* User Account Dropdown Menu */}
          {isMenuOpen && (
            <div className="absolute right-0 mt-2 w-64 bg-white rounded-2xl shadow-[0_8px_30px_rgba(0,0,0,0.12)] border border-slate-200/80 py-2 z-50 animate-in fade-in slide-in-from-top-2 duration-150 dark:bg-[#12161A] dark:border-white/10">
              {/* User Header */}
              <div className="px-4 py-3 border-b border-slate-100 flex items-center gap-3 dark:border-white/10">
                <div className="w-10 h-10 rounded-full bg-[#00D1C1]/20 text-[#006a62] flex items-center justify-center font-bold text-sm shrink-0">
                  {initials}
                </div>
                <div className="min-w-0 flex-1">
                  <p className="text-sm font-bold text-[#191C1E] dark:text-white truncate">{userName}</p>
                </div>
              </div>

              {/* Menu Items */}
              <div className="py-1">
                <NavLink
                  to="/profile"
                  onClick={() => setIsMenuOpen(false)}
                  className="flex items-center gap-3 px-4 py-2.5 text-xs font-semibold text-slate-700 hover:bg-slate-50 transition-colors dark:text-slate-300 dark:hover:bg-white/10"
                >
                  <Shield className="w-4 h-4 text-slate-400 dark:text-slate-500" />
                  <span>Hồ sơ cá nhân</span>
                </NavLink>

                {/* Bug thật đã sửa: trước trỏ tới "/payment" (thực chất là trang Cài
                    đặt, không phải ví) — mục "Phương thức thanh toán" thật nằm ở
                    ProfilePage, nên sửa lại trỏ đúng chỗ. */}
                <NavLink
                  to="/profile"
                  onClick={() => setIsMenuOpen(false)}
                  className="flex items-center gap-3 px-4 py-2.5 text-xs font-semibold text-slate-700 hover:bg-slate-50 transition-colors dark:text-slate-300 dark:hover:bg-white/10"
                >
                  <Wallet className="w-4 h-4 text-slate-400 dark:text-slate-500" />
                  <span>Ví AloSM Pay</span>
                </NavLink>
              </div>

              {/* Logout Button */}
              <div className="pt-1 border-t border-slate-100 dark:border-white/10">
                <button
                  type="button"
                  onClick={handleLogout}
                  className="w-full flex items-center gap-3 px-4 py-2.5 text-xs font-bold text-rose-600 hover:bg-rose-50 transition-colors cursor-pointer text-left dark:text-rose-400 dark:hover:bg-rose-500/10"
                >
                  <LogOut className="w-4 h-4 text-rose-600 dark:text-rose-400" />
                  <span>Đăng xuất</span>
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </header>
  );
};
