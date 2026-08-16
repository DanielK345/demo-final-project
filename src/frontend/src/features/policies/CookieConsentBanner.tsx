import React, { useState } from "react";
import { CURRENT_POLICY_VERSION } from "@/features/policies/api";

const STORAGE_KEY = `alosm_cookie_consent_v${CURRENT_POLICY_VERSION}`;

type Choice = "essential" | "all";

export const CookieConsentBanner: React.FC = () => {
  const [choice, setChoice] = useState<Choice | null>(() => {
    const stored = localStorage.getItem(STORAGE_KEY);
    return stored === "essential" || stored === "all" ? stored : null;
  });

  const choose = (value: Choice) => {
    localStorage.setItem(STORAGE_KEY, value);
    setChoice(value);
  };

  if (choice) return null;

  return (
    <aside role="dialog" aria-label="Lựa chọn cookie" className="fixed inset-x-3 bottom-3 z-[100] mx-auto max-w-3xl rounded-3xl border border-slate-200 bg-white p-5 shadow-2xl dark:border-white/10 dark:bg-[#12161A]">
      <h2 className="font-extrabold text-[#173132] dark:text-white">Quyền riêng tư và cookie</h2>
      <p className="mt-2 text-sm leading-6 text-slate-600 dark:text-slate-300">
        AloSM luôn dùng lưu trữ thiết yếu cho đăng nhập và phiên làm việc. Cookie hoặc lưu trữ tùy chọn chỉ được bật khi bạn đồng ý riêng. Hiện ứng dụng chưa cài công cụ quảng cáo bên thứ ba.
      </p>
      <p className="mt-2 text-xs text-amber-700 dark:text-amber-300">
        Phiên bản chính sách {CURRENT_POLICY_VERSION}. <a className="font-bold underline" href="/policies?section=cookies">Xem chính sách</a>
      </p>
      <div className="mt-4 flex flex-wrap justify-end gap-2">
        <button type="button" onClick={() => choose("essential")} className="rounded-xl border border-slate-300 px-4 py-2 text-sm font-bold text-slate-600 dark:border-white/20 dark:text-slate-200">Chỉ thiết yếu</button>
        <button type="button" onClick={() => choose("all")} className="rounded-xl bg-[#00C9B7] px-4 py-2 text-sm font-bold text-white">Đồng ý tất cả</button>
      </div>
    </aside>
  );
};
