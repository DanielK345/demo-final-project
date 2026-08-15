import React, { useState } from "react";
import { ArrowRight, Lock, Phone, UserRound } from "lucide-react";
import { useNavigate } from "react-router-dom";
import logoSvg from "@/assets/logo.svg";
import { login, register } from "@/features/auth/api";
import { saveAuthSession } from "@/features/auth/storage";

export const LoginForm: React.FC = () => {
  const [isRegistering, setIsRegistering] = useState(false);
  const [fullName, setFullName] = useState("");
  const [phone, setPhone] = useState("0901234567");
  const [password, setPassword] = useState("Password123!");
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const navigate = useNavigate();

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    setError(null);
    setIsLoading(true);
    try {
      const result = isRegistering
        ? await register(fullName, phone, password)
        : await login(phone, password);
      saveAuthSession({
        access_token: result.access_token,
        user_id: result.user_id,
        full_name: result.full_name,
        session_id: result.session_id,
      });
      navigate("/");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Không thể đăng nhập");
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="bg-white w-full max-w-md rounded-3xl p-8 relative z-10 shadow-xl border border-slate-200 flex flex-col items-center dark:bg-[#12161A] dark:border-white/10">
      <img src={logoSvg} alt="AloSM Voice" className="h-14 w-auto mb-5" />
      <h1 className="text-2xl font-extrabold text-[#191C1E] dark:text-white">{isRegistering ? "Tạo tài khoản" : "Chào mừng trở lại"}</h1>
      <p className="text-sm text-slate-500 dark:text-slate-400 text-center mt-2">Đăng nhập để đặt xe bằng giọng nói hoặc tin nhắn.</p>
      <form onSubmit={handleSubmit} className="w-full mt-7 space-y-4">
        {isRegistering && <label className="block text-xs font-bold text-slate-700 dark:text-slate-300">HỌ VÀ TÊN
          <span className="relative block mt-2"><UserRound className="w-5 h-5 absolute left-3 top-3 text-slate-400 dark:text-slate-500" /><input required value={fullName} onChange={(e) => setFullName(e.target.value)} className="w-full pl-10 p-3 rounded-xl border border-slate-200 bg-slate-50 dark:border-white/10 dark:bg-white/5 dark:text-white" placeholder="Nguyễn Văn A" /></span>
        </label>}
        <label className="block text-xs font-bold text-slate-700 dark:text-slate-300">SỐ ĐIỆN THOẠI
          <span className="relative block mt-2"><Phone className="w-5 h-5 absolute left-3 top-3 text-slate-400 dark:text-slate-500" /><input required value={phone} onChange={(e) => setPhone(e.target.value)} className="w-full pl-10 p-3 rounded-xl border border-slate-200 bg-slate-50 dark:border-white/10 dark:bg-white/5 dark:text-white" placeholder="0901234567" /></span>
        </label>
        <label className="block text-xs font-bold text-slate-700 dark:text-slate-300">MẬT KHẨU
          <span className="relative block mt-2"><Lock className="w-5 h-5 absolute left-3 top-3 text-slate-400 dark:text-slate-500" /><input required type="password" value={password} onChange={(e) => setPassword(e.target.value)} className="w-full pl-10 p-3 rounded-xl border border-slate-200 bg-slate-50 dark:border-white/10 dark:bg-white/5 dark:text-white" /></span>
        </label>
        {error && <p role="alert" className="text-sm text-rose-600 bg-rose-50 p-3 rounded-xl dark:text-rose-300 dark:bg-rose-500/10">{error}</p>}
        <button disabled={isLoading} className="w-full bg-[#00D1C1] hover:bg-[#006a62] disabled:opacity-60 text-white font-bold rounded-xl py-3 flex justify-center gap-2">
          {isLoading ? "Đang xử lý..." : isRegistering ? "Tạo tài khoản" : "Đăng nhập"}<ArrowRight className="w-5 h-5" />
        </button>
      </form>
      <button type="button" onClick={() => { setIsRegistering(!isRegistering); setError(null); }} className="mt-6 text-sm font-semibold text-[#006a62] dark:text-[#00D1C1]">
        {isRegistering ? "Đã có tài khoản? Đăng nhập" : "Chưa có tài khoản? Đăng ký"}
      </button>
      {!isRegistering && <p className="mt-5 text-xs text-slate-400 dark:text-slate-500">Tài khoản demo: 0901234567 / Password123!</p>}
    </div>
  );
};
