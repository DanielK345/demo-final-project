import React, { useState } from "react";
import { Mail, Lock, Eye, EyeOff, ArrowRight } from "lucide-react";
import { useNavigate } from "react-router-dom";
import logoSvg from "@/assets/logo.svg";

export const LoginForm: React.FC = () => {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [rememberMe, setRememberMe] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const navigate = useNavigate();

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setIsLoading(true);
    setTimeout(() => {
      setIsLoading(false);
      navigate("/");
    }, 1000);
  };

  return (
    <div className="bg-white w-full max-w-md rounded-2xl p-8 relative z-10 shadow-[0px_4px_20px_rgba(16,18,19,0.05)] border border-slate-200/80 flex flex-col items-center">
      {/* Disclaimer Tag */}
      <span className="text-[10px] font-mono text-amber-700 bg-amber-50 border border-amber-200 px-3 py-1 rounded-full mb-6 text-center">
        Auth UI Prototype — Backend Integration Pending
      </span>

      {/* Logo Area */}
      <div className="mb-6 flex flex-col items-center">
        <img src={logoSvg} alt="AloSM AI Booking Logo" className="h-14 w-auto mb-4" />
        <h1 className="text-2xl font-extrabold text-[#191C1E] mb-1">Welcome Back</h1>
        <p className="text-sm text-slate-500 text-center">
          Log in to your AloSM account to continue.
        </p>
      </div>

      {/* Login Form */}
      <form onSubmit={handleSubmit} className="w-full flex flex-col gap-4">
        {/* Email */}
        <div>
          <label
            htmlFor="email"
            className="block text-xs font-bold text-slate-700 mb-2 uppercase tracking-wider"
          >
            Email or Username
          </label>
          <div className="relative">
            <Mail className="w-5 h-5 absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
            <input
              id="email"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="Enter your email"
              required
              className="w-full pl-10 pr-4 py-3 rounded-xl border border-slate-200 bg-slate-50 text-[#191C1E] focus:outline-none focus:border-[#00D1C1] focus:ring-2 focus:ring-[#00D1C1]/20 transition-all text-sm font-medium placeholder:text-slate-400"
            />
          </div>
        </div>

        {/* Password */}
        <div>
          <label
            htmlFor="password"
            className="block text-xs font-bold text-slate-700 mb-2 uppercase tracking-wider"
          >
            Password
          </label>
          <div className="relative">
            <Lock className="w-5 h-5 absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
            <input
              id="password"
              type={showPassword ? "text" : "password"}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="••••••••"
              required
              className="w-full pl-10 pr-10 py-3 rounded-xl border border-slate-200 bg-slate-50 text-[#191C1E] focus:outline-none focus:border-[#00D1C1] focus:ring-2 focus:ring-[#00D1C1]/20 transition-all text-sm font-medium placeholder:text-slate-400"
            />
            <button
              type="button"
              onClick={() => setShowPassword(!showPassword)}
              className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-[#00D1C1] transition-colors cursor-pointer"
            >
              {showPassword ? <EyeOff className="w-5 h-5" /> : <Eye className="w-5 h-5" />}
            </button>
          </div>
        </div>

        {/* Remember me & Forgot Password */}
        <div className="flex items-center justify-between mt-1 text-xs font-medium">
          <label className="flex items-center gap-2 cursor-pointer text-slate-600">
            <input
              type="checkbox"
              checked={rememberMe}
              onChange={(e) => setRememberMe(e.target.checked)}
              className="rounded text-[#00D1C1] focus:ring-[#00D1C1]/20 border-slate-300 w-4 h-4"
            />
            <span>Remember me</span>
          </label>
          <a
            href="#"
            onClick={(e) => e.preventDefault()}
            className="text-[#00D1C1] hover:text-[#006a62] transition-colors"
          >
            Forgot password?
          </a>
        </div>

        {/* Submit Button */}
        <button
          type="submit"
          disabled={isLoading}
          className="w-full bg-[#00D1C1] hover:bg-[#006a62] text-white font-bold rounded-xl py-3 text-sm shadow-md transition-colors mt-2 flex items-center justify-center gap-2 cursor-pointer disabled:opacity-60"
        >
          {isLoading ? (
            <span>Signing In...</span>
          ) : (
            <>
              <span>Sign In</span>
              <ArrowRight className="w-4 h-4" />
            </>
          )}
        </button>
      </form>

      {/* Social Divider */}
      <div className="w-full flex items-center gap-4 my-6">
        <div className="h-px bg-slate-200 flex-1" />
        <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider">
          Or continue with
        </span>
        <div className="h-px bg-slate-200 flex-1" />
      </div>

      {/* Social Logins */}
      <div className="w-full flex gap-3">
        <button
          type="button"
          className="flex-1 flex items-center justify-center gap-2 py-2.5 rounded-xl border border-slate-200 bg-white hover:bg-slate-50 transition-colors text-xs font-bold text-[#191C1E] cursor-pointer"
        >
          <svg className="w-4 h-4" viewBox="0 0 24 24">
            <path
              fill="#4285F4"
              d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"
            />
            <path
              fill="#34A853"
              d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
            />
            <path
              fill="#FBBC05"
              d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.06H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.94l2.85-2.22.81-.63z"
            />
            <path
              fill="#EA4335"
              d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.06l3.66 2.84c.87-2.6 3.3-4.52 6.16-4.52z"
            />
          </svg>
          <span>Google</span>
        </button>

        <button
          type="button"
          className="flex-1 flex items-center justify-center gap-2 py-2.5 rounded-xl border border-slate-200 bg-white hover:bg-slate-50 transition-colors text-xs font-bold text-[#191C1E] cursor-pointer"
        >
          <svg className="w-4 h-4 fill-current" viewBox="0 0 24 24">
            <path d="M18.71 19.5c-.83 1.24-1.71 2.45-3.05 2.47-1.34.03-1.77-.79-3.29-.79-1.53 0-2 .77-3.27.82-1.31.05-2.3-1.32-3.14-2.53C4.25 17 2.94 12.45 4.7 9.39c.87-1.52 2.43-2.48 4.12-2.51 1.28-.02 2.5.87 3.29.87.78 0 2.26-1.07 3.81-.91.65.03 2.47.26 3.64 1.98-.09.06-2.17 1.28-2.15 3.81.03 3.02 2.65 4.03 2.68 4.04-.03.07-.42 1.44-1.38 2.83M15.97 6.32c.67-.82 1.13-1.96.99-3.11-.97.04-2.17.65-2.86 1.46-.61.72-1.15 1.88-.99 3.01 1.09.08 2.22-.54 2.86-1.36z" />
          </svg>
          <span>Apple</span>
        </button>
      </div>

      <p className="mt-8 text-xs text-slate-500 text-center font-medium">
        Don't have an account?{" "}
        <a href="#" className="text-[#00D1C1] font-bold hover:text-[#006a62] transition-colors">
          Sign up
        </a>
      </p>
    </div>
  );
};
