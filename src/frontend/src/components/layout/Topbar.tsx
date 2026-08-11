import React, { useState, useRef, useEffect } from "react";
import { Search, Bell, User, LogOut, Wallet, Shield } from "lucide-react";
import { IconButton } from "@/components/ui/IconButton";
import logoSvg from "@/assets/logo.svg";
import { NavLink, useNavigate } from "react-router-dom";

export const Topbar: React.FC = () => {
  const [isMenuOpen, setIsMenuOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);
  const navigate = useNavigate();

  // Close dropdown when clicking outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setIsMenuOpen(false);
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  const handleLogout = () => {
    setIsMenuOpen(false);
    navigate("/login");
  };

  return (
    <header className="flex justify-between items-center h-16 px-4 md:px-8 sticky top-0 z-40 bg-white/80 backdrop-blur-xl border-b border-slate-200/60 shadow-xs">
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
          <Search className="w-4 h-4 absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-400" />
          <input
            type="text"
            placeholder="Tìm kiếm..."
            className="w-full h-10 pl-10 pr-4 bg-slate-50 rounded-xl border border-slate-200 focus:outline-none focus:border-[#00D1C1] text-xs font-medium text-slate-800 placeholder:text-slate-400 transition-all"
          />
        </div>

        {/* Notifications */}
        <IconButton
          icon={<Bell className="w-5 h-5 text-slate-600 hover:text-[#006a62]" />}
          label="Notifications"
          variant="ghost"
          size="md"
          className="rounded-full hover:bg-slate-100"
        />

        {/* Account Avatar Button with Dropdown */}
        <div className="relative" ref={dropdownRef}>
          <IconButton
            icon={<User className="w-5 h-5 text-slate-600 hover:text-[#006a62]" />}
            label="Account"
            variant="ghost"
            size="md"
            onClick={() => setIsMenuOpen(!isMenuOpen)}
            className={`rounded-full transition-all ${
              isMenuOpen ? "bg-[#00D1C1]/20 text-[#006a62]" : "hover:bg-slate-100"
            }`}
          />

          {/* User Account Dropdown Menu */}
          {isMenuOpen && (
            <div className="absolute right-0 mt-2 w-64 bg-white rounded-2xl shadow-[0_8px_30px_rgba(0,0,0,0.12)] border border-slate-200/80 py-2 z-50 animate-in fade-in slide-in-from-top-2 duration-150">
              {/* User Header */}
              <div className="px-4 py-3 border-b border-slate-100 flex items-center gap-3">
                <div className="w-10 h-10 rounded-full bg-[#00D1C1]/20 text-[#006a62] flex items-center justify-center font-bold text-sm shrink-0">
                  NV
                </div>
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-1.5">
                    <p className="text-sm font-bold text-[#191C1E] truncate">Nguyễn Văn Việt</p>
                    <span className="bg-amber-100 text-amber-700 text-[9px] font-bold px-1.5 py-0.5 rounded">
                      Gold
                    </span>
                  </div>
                  <p className="text-xs text-slate-400 truncate">viet.nguyen@alosm.vn</p>
                </div>
              </div>

              {/* Menu Items */}
              <div className="py-1">
                <NavLink
                  to="/profile"
                  onClick={() => setIsMenuOpen(false)}
                  className="flex items-center gap-3 px-4 py-2.5 text-xs font-semibold text-slate-700 hover:bg-slate-50 transition-colors"
                >
                  <Shield className="w-4 h-4 text-slate-400" />
                  <span>Hồ sơ cá nhân</span>
                </NavLink>

                <NavLink
                  to="/payment"
                  onClick={() => setIsMenuOpen(false)}
                  className="flex items-center gap-3 px-4 py-2.5 text-xs font-semibold text-slate-700 hover:bg-slate-50 transition-colors"
                >
                  <Wallet className="w-4 h-4 text-slate-400" />
                  <span>Ví AloSM Pay</span>
                </NavLink>
              </div>

              {/* Logout Button */}
              <div className="pt-1 border-t border-slate-100">
                <button
                  type="button"
                  onClick={handleLogout}
                  className="w-full flex items-center gap-3 px-4 py-2.5 text-xs font-bold text-rose-600 hover:bg-rose-50 transition-colors cursor-pointer text-left"
                >
                  <LogOut className="w-4 h-4 text-rose-600" />
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
