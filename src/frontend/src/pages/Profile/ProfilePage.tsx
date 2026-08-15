import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  Star,
  BadgeCheck,
  CreditCard,
  PlusCircle,
  Wallet,
  Ticket,
  AlertCircle,
} from "lucide-react";
import { getCurrentUser, type CurrentUser } from "@/features/auth/api";
import { redirectToLoginIfUnauthorized } from "@/features/auth/sessionGuard";

export const ProfilePage: React.FC = () => {
  const navigate = useNavigate();
  const [user, setUser] = useState<CurrentUser | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    getCurrentUser()
      .then((data) => {
        if (!cancelled) setUser(data);
      })
      .catch((cause) => {
        if (cancelled) return;
        if (redirectToLoginIfUnauthorized(cause, navigate)) return;
        setError(cause instanceof Error ? cause.message : "Không thể tải thông tin tài khoản.");
      });
    return () => {
      cancelled = true;
    };
  }, [navigate]);

  const initials = user?.full_name
    ? user.full_name
        .split(" ")
        .slice(-2)
        .map((part) => part[0])
        .join("")
        .toUpperCase()
    : "?";

  return (
    <div className="max-w-[1024px] mx-auto space-y-8 pb-16">
      {/* Page Header */}
      <header className="mb-2">
        <h1 className="text-3xl md:text-4xl font-extrabold text-[#191C1E] dark:text-white tracking-tight">
          Tài khoản
        </h1>
      </header>

      {error && (
        <p className="flex items-center gap-2 text-sm text-rose-700 bg-rose-50 border border-rose-200 rounded-xl p-3 dark:text-rose-300 dark:bg-rose-500/10 dark:border-rose-500/30">
          <AlertCircle className="w-4 h-4 shrink-0" />
          <span>{error}</span>
        </p>
      )}

      {/* Bento Grid Layout for Account Info */}
      <div className="grid grid-cols-1 md:grid-cols-12 gap-6">
        {/* Profile Header Card (8 cols on desktop) */}
        <div className="md:col-span-12 lg:col-span-8 bg-white rounded-2xl p-6 md:p-8 shadow-[0px_4px_20px_rgba(16,18,19,0.05)] border border-slate-200/80 flex flex-col md:flex-row items-center md:items-start gap-6 relative overflow-hidden group dark:bg-[#12161A] dark:border-white/10">
          <div className="absolute -top-24 -right-24 w-64 h-64 bg-[#00D1C1]/5 rounded-full blur-3xl group-hover:bg-[#00D1C1]/10 transition-colors duration-500 pointer-events-none" />

          <div className="relative w-24 h-24 md:w-32 md:h-32 rounded-full border-4 border-white shadow-sm shrink-0 z-10 bg-[#00D1C1]/15 text-[#006a62] dark:text-[#00D1C1] flex items-center justify-center text-3xl font-extrabold dark:border-white/10">
            {initials}
          </div>

          <div className="flex-1 text-center md:text-left z-10 pt-1">
            <h2 className="text-2xl font-extrabold text-[#191C1E] dark:text-white mb-1">
              {user?.full_name || "Đang tải..."}
            </h2>
            <div className="inline-flex items-center gap-1.5 px-3.5 py-1 rounded-full bg-[#006a62] text-white text-xs font-semibold shadow-xs mb-4">
              <Star className="w-4 h-4 fill-current text-amber-300" />
              <span>{user?.role === "CUSTOMER" ? "Khách hàng" : user?.role || ""}</span>
            </div>
          </div>
        </div>

        {/* Account Information Card (4 cols on desktop) */}
        <div className="md:col-span-12 lg:col-span-4 bg-white rounded-2xl p-6 shadow-[0px_4px_20px_rgba(16,18,19,0.05)] border border-slate-200/80 flex flex-col justify-between hover:shadow-md transition-shadow dark:bg-[#12161A] dark:border-white/10">
          <div>
            <h3 className="text-lg font-bold text-[#191C1E] dark:text-white mb-4 flex items-center gap-2">
              <BadgeCheck className="w-5 h-5 text-slate-500 dark:text-slate-400" />
              <span>Thông tin cá nhân</span>
            </h3>

            <div className="space-y-4 text-xs font-medium text-slate-600 dark:text-slate-300">
              <div className="flex justify-between items-center border-b border-slate-100 dark:border-white/10 pb-2.5">
                <span className="text-slate-400 dark:text-slate-500 font-bold uppercase">Số điện thoại</span>
                <span className="font-bold text-[#191C1E] dark:text-white">{user?.phone || "--"}</span>
              </div>
              <div className="flex justify-between items-center border-b border-slate-100 dark:border-white/10 pb-2.5">
                <span className="text-slate-400 dark:text-slate-500 font-bold uppercase">Mã khách hàng</span>
                <span className="font-bold text-[#191C1E] dark:text-white truncate max-w-[160px]" title={user?.user_id}>
                  {user?.user_id || "--"}
                </span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-slate-400 dark:text-slate-500 font-bold uppercase">Email</span>
                <span className="font-bold text-slate-400 dark:text-slate-500">Chưa cập nhật</span>
              </div>
            </div>
          </div>
        </div>

        {/* Payment Methods Section (8 cols on desktop) — chưa tích hợp cổng thanh toán
            thật (xem mustdo.md mục 2), không hiển thị số dư/thẻ giả */}
        <div className="md:col-span-12 lg:col-span-8 bg-white rounded-2xl p-6 md:p-8 shadow-[0px_4px_20px_rgba(16,18,19,0.05)] border border-slate-200/80 dark:bg-[#12161A] dark:border-white/10">
          <div className="flex justify-between items-end mb-6">
            <h3 className="text-lg font-bold text-[#191C1E] dark:text-white flex items-center gap-2">
              <CreditCard className="w-5 h-5 text-slate-500 dark:text-slate-400" />
              <span>Phương thức thanh toán</span>
            </h3>
          </div>

          <div className="flex flex-col items-center justify-center gap-3 py-8 text-center border-2 border-dashed border-slate-200 dark:border-white/10 rounded-xl">
            <Wallet className="w-8 h-8 text-slate-300 dark:text-slate-600" />
            <p className="text-sm text-slate-500 dark:text-slate-400">Chưa liên kết phương thức thanh toán nào.</p>
            <button
              type="button"
              disabled
              title="Tính năng đang được phát triển"
              className="text-slate-400 dark:text-slate-500 font-bold text-xs flex items-center gap-1 cursor-not-allowed"
            >
              <PlusCircle className="w-4 h-4" />
              <span>Thêm phương thức (sắp ra mắt)</span>
            </button>
          </div>
        </div>

        {/* Rewards / Coupons Section (4 cols on desktop) */}
        <div className="md:col-span-12 lg:col-span-4 bg-white rounded-2xl p-6 shadow-[0px_4px_20px_rgba(16,18,19,0.05)] border border-slate-200/80 flex flex-col h-full dark:bg-[#12161A] dark:border-white/10">
          <h3 className="text-lg font-bold text-[#191C1E] dark:text-white mb-4 flex items-center gap-2">
            <Ticket className="w-5 h-5 text-slate-500 dark:text-slate-400" />
            <span>Ưu đãi của tôi</span>
          </h3>

          <div className="flex-1 flex flex-col items-center justify-center gap-2 text-center text-slate-400 dark:text-slate-500 py-6">
            <Ticket className="w-8 h-8 text-slate-300 dark:text-slate-600" />
            <p className="text-xs">Chưa có ưu đãi nào.</p>
          </div>
        </div>
      </div>
    </div>
  );
};
