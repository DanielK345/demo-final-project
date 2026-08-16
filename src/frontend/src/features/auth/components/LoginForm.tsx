import React, { useState } from "react";
import { ArrowLeft, ArrowRight, Lock, Phone, ShieldCheck, UserRound } from "lucide-react";
import { useNavigate } from "react-router-dom";
import logoSvg from "@/assets/logo.svg";
import { isTwoFactorChallenge, login, register, verifyTwoFactorLogin } from "@/features/auth/api";
import { saveAuthSession } from "@/features/auth/storage";

export const LoginForm: React.FC = () => {
  const [isRegistering, setIsRegistering] = useState(false);
  const [fullName, setFullName] = useState("");
  const [phone, setPhone] = useState("0901234567");
  const [password, setPassword] = useState("Password123!");
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const navigate = useNavigate();

  // Bước 2 của đăng nhập khi tài khoản đã bật 2FA thật (xem PaymentPage.tsx) — mật
  // khẩu đúng nhưng chưa đủ, cần thêm mã từ app authenticator.
  const [pendingToken, setPendingToken] = useState<string | null>(null);
  const [twoFactorCode, setTwoFactorCode] = useState("");

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    setError(null);
    setIsLoading(true);
    try {
      if (isRegistering) {
        const result = await register(fullName, phone, password);
        saveAuthSession({
          access_token: result.access_token,
          user_id: result.user_id,
          full_name: result.full_name,
          session_id: result.session_id,
        });
        navigate("/");
        return;
      }
      const result = await login(phone, password);
      if (isTwoFactorChallenge(result)) {
        setPendingToken(result.pending_token);
        return;
      }
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

  const handleVerifyTwoFactor = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!pendingToken) return;
    setError(null);
    setIsLoading(true);
    try {
      const result = await verifyTwoFactorLogin(pendingToken, twoFactorCode);
      saveAuthSession({
        access_token: result.access_token,
        user_id: result.user_id,
        full_name: result.full_name,
        session_id: result.session_id,
      });
      navigate("/");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Mã xác thực không đúng");
    } finally {
      setIsLoading(false);
    }
  };

  if (pendingToken) {
    return (
      <div className="bg-white w-full max-w-md rounded-3xl p-8 relative z-10 shadow-xl border border-slate-200 flex flex-col items-center dark:bg-[#12161A] dark:border-white/10">
        <div className="w-14 h-14 rounded-full bg-[#00D1C1]/10 flex items-center justify-center mb-5">
          <ShieldCheck className="w-7 h-7 text-[#006a62] dark:text-[#00D1C1]" />
        </div>
        <h1 className="text-2xl font-extrabold text-[#191C1E] dark:text-white">Xác thực 2 lớp</h1>
        <p className="text-sm text-slate-500 dark:text-slate-400 text-center mt-2">
          Nhập mã 6 số từ app authenticator của bạn (Google Authenticator, Authy...).
        </p>
        <form onSubmit={handleVerifyTwoFactor} className="w-full mt-7 space-y-4">
          <input
            required
            autoFocus
            inputMode="numeric"
            pattern="[0-9]{6}"
            maxLength={6}
            value={twoFactorCode}
            onChange={(event) => setTwoFactorCode(event.target.value.replace(/\D/g, "").slice(0, 6))}
            placeholder="000000"
            className="w-full p-3 rounded-xl border border-slate-200 bg-slate-50 text-center font-mono text-lg tracking-[0.4em] dark:border-white/10 dark:bg-white/5 dark:text-white"
          />
          {error && <p role="alert" className="text-sm text-rose-600 bg-rose-50 p-3 rounded-xl dark:text-rose-300 dark:bg-rose-500/10">{error}</p>}
          <button disabled={isLoading || twoFactorCode.length !== 6} className="w-full bg-[#00D1C1] hover:bg-[#006a62] disabled:opacity-60 text-white font-bold rounded-xl py-3 flex justify-center gap-2">
            {isLoading ? "Đang xác thực..." : "Xác nhận"}<ArrowRight className="w-5 h-5" />
          </button>
        </form>
        <button
          type="button"
          onClick={() => {
            setPendingToken(null);
            setTwoFactorCode("");
            setError(null);
          }}
          className="mt-6 flex items-center gap-1.5 text-sm font-semibold text-slate-500 dark:text-slate-400"
        >
          <ArrowLeft className="w-4 h-4" />
          Quay lại đăng nhập
        </button>
      </div>
    );
  }

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
