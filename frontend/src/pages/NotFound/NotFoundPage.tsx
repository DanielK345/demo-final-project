import React from "react";
import { NavLink } from "react-router-dom";
import { AlertCircle, Home } from "lucide-react";
import { Button } from "@/components/ui/Button";

export const NotFoundPage: React.FC = () => {
  return (
    <div className="min-h-[60vh] flex flex-col items-center justify-center text-center space-y-4">
      <div className="w-16 h-16 rounded-2xl bg-rose-500/10 border border-rose-500/30 text-rose-400 flex items-center justify-center shadow-xl">
        <AlertCircle className="w-8 h-8" />
      </div>
      <h1 className="text-3xl font-extrabold text-slate-100">404 — Không tìm thấy trang</h1>
      <p className="text-xs text-slate-400 max-w-sm">
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
