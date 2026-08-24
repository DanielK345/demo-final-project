import React from "react";
import { NavLink } from "react-router-dom";
import { AlertCircle, Home } from "lucide-react";
import { Button } from "@/components/ui/Button";

export const NotFoundPage: React.FC = () => {
  return (
    // Bug thật đã sửa: bản cũ dùng text-slate-100/text-slate-400 (gần trắng) — trang
    // này KHÔNG nằm trong AppLayout (route top-level riêng), nền thật là #F4FBFA
    // (sáng), nên chữ gần như vô hình. Đổi sang màu tối chuẩn của các trang khác, kèm
    // biến thể `dark:` để theo đúng theme toàn site (đọc trực tiếp từ class "dark"
    // trên <html>, không cần AppLayout bọc ngoài).
    <div className="min-h-screen flex flex-col items-center justify-center text-center space-y-4 bg-[#F4FBFA] dark:bg-[#0B0E11] px-4">
      <div className="w-16 h-16 rounded-2xl bg-rose-500/10 border border-rose-500/30 text-rose-500 flex items-center justify-center shadow-xl">
        <AlertCircle className="w-8 h-8" />
      </div>
      <h1 className="text-3xl font-extrabold text-[#191C1E] dark:text-white">404 — Không tìm thấy trang</h1>
      <p className="text-sm text-slate-500 dark:text-slate-400 max-w-sm">
        Trang bạn đang truy cập không tồn tại hoặc đã được di chuyển.
      </p>
      <NavLink to="/">
        <Button variant="primary" size="md" leftIcon={<Home className="w-4 h-4" />}>
          Về Trang chủ
        </Button>
      </NavLink>
    </div>
  );
};
