import React, { useState } from "react";
import { Bell, Shield, Globe, Palette, Sun, Moon, Check } from "lucide-react";

export const PaymentPage: React.FC = () => {
  const [pushEnabled, setPushEnabled] = useState(true);
  const [emailEnabled, setEmailEnabled] = useState(false);
  const [smsEnabled, setSmsEnabled] = useState(true);
  const [twoFactorEnabled, setTwoFactorEnabled] = useState(false);
  const [language, setLanguage] = useState("vi");
  const [theme, setTheme] = useState<"light" | "dark">("light");
  const [isSaved, setIsSaved] = useState(false);

  const handleSave = () => {
    setIsSaved(true);
    setTimeout(() => setIsSaved(false), 2000);
  };

  return (
    <div className="space-y-8 pb-12">
      {/* Page Title */}
      <div>
        <h1 className="text-3xl md:text-4xl font-extrabold text-[#191C1E] mb-2 tracking-tight">
          Cài đặt
        </h1>
        <p className="text-sm md:text-base text-slate-500">
          Manage your preferences and security settings.
        </p>
      </div>

      {/* Main Settings Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-start">
        {/* Left Column: Notifications & Security (8 columns) */}
        <div className="lg:col-span-8 space-y-8">
          {/* Section 1: Notifications */}
          <section className="bg-white/90 backdrop-blur-xl rounded-[16px] p-6 lg:p-8 shadow-[0px_4px_20px_rgba(16,18,19,0.05)] border border-slate-200/80">
            <div className="flex items-center mb-6">
              <Bell className="w-6 h-6 text-[#00D1C1] mr-3" />
              <h2 className="text-xl font-bold text-[#191C1E]">Thông báo</h2>
            </div>

            <div className="space-y-6">
              {/* Push Notifications */}
              <div className="flex items-center justify-between py-2 border-b border-slate-100">
                <div>
                  <h3 className="text-sm font-bold text-[#191C1E]">Push Notifications</h3>
                  <p className="text-xs text-slate-500 mt-0.5">
                    Receive real-time alerts on your device.
                  </p>
                </div>
                <button
                  type="button"
                  onClick={() => setPushEnabled(!pushEnabled)}
                  className={`w-12 h-6 rounded-full transition-colors relative cursor-pointer ${
                    pushEnabled ? "bg-[#00D1C1]" : "bg-slate-200"
                  }`}
                >
                  <span
                    className={`absolute top-0.5 left-0.5 w-5 h-5 bg-white rounded-full transition-transform shadow-xs ${
                      pushEnabled ? "translate-x-6" : "translate-x-0"
                    }`}
                  />
                </button>
              </div>

              {/* Email Notifications */}
              <div className="flex items-center justify-between py-2 border-b border-slate-100">
                <div>
                  <h3 className="text-sm font-bold text-[#191C1E]">Email Notifications</h3>
                  <p className="text-xs text-slate-500 mt-0.5">
                    Daily summaries and promotional offers.
                  </p>
                </div>
                <button
                  type="button"
                  onClick={() => setEmailEnabled(!emailEnabled)}
                  className={`w-12 h-6 rounded-full transition-colors relative cursor-pointer ${
                    emailEnabled ? "bg-[#00D1C1]" : "bg-slate-200"
                  }`}
                >
                  <span
                    className={`absolute top-0.5 left-0.5 w-5 h-5 bg-white rounded-full transition-transform shadow-xs ${
                      emailEnabled ? "translate-x-6" : "translate-x-0"
                    }`}
                  />
                </button>
              </div>

              {/* SMS Notifications */}
              <div className="flex items-center justify-between py-2">
                <div>
                  <h3 className="text-sm font-bold text-[#191C1E]">SMS Notifications</h3>
                  <p className="text-xs text-slate-500 mt-0.5">
                    Critical security alerts and trip updates.
                  </p>
                </div>
                <button
                  type="button"
                  onClick={() => setSmsEnabled(!smsEnabled)}
                  className={`w-12 h-6 rounded-full transition-colors relative cursor-pointer ${
                    smsEnabled ? "bg-[#00D1C1]" : "bg-slate-200"
                  }`}
                >
                  <span
                    className={`absolute top-0.5 left-0.5 w-5 h-5 bg-white rounded-full transition-transform shadow-xs ${
                      smsEnabled ? "translate-x-6" : "translate-x-0"
                    }`}
                  />
                </button>
              </div>
            </div>
          </section>

          {/* Section 2: Security */}
          <section className="bg-white/90 backdrop-blur-xl rounded-[16px] p-6 lg:p-8 shadow-[0px_4px_20px_rgba(16,18,19,0.05)] border border-slate-200/80">
            <div className="flex items-center mb-6">
              <Shield className="w-6 h-6 text-[#00D1C1] mr-3" />
              <h2 className="text-xl font-bold text-[#191C1E]">Bảo mật</h2>
            </div>

            <div className="space-y-6">
              {/* Password */}
              <div className="flex flex-col sm:flex-row sm:items-center justify-between py-2 border-b border-slate-100 gap-4">
                <div>
                  <h3 className="text-sm font-bold text-[#191C1E]">Mật khẩu</h3>
                  <p className="text-xs text-slate-500 mt-0.5">Last changed 3 months ago.</p>
                </div>
                <button
                  type="button"
                  className="px-5 py-2 rounded-xl bg-transparent border border-slate-700 text-slate-800 font-semibold text-xs hover:bg-slate-100 transition-colors whitespace-nowrap cursor-pointer"
                >
                  Thay đổi mật khẩu
                </button>
              </div>

              {/* 2FA */}
              <div className="flex items-center justify-between py-2">
                <div>
                  <h3 className="text-sm font-bold text-[#191C1E]">Xác thực 2 yếu tố (2FA)</h3>
                  <p className="text-xs text-slate-500 mt-0.5">
                    Thêm một lớp bảo mật cho tài khoản của bạn.
                  </p>
                </div>
                <button
                  type="button"
                  onClick={() => setTwoFactorEnabled(!twoFactorEnabled)}
                  className={`w-12 h-6 rounded-full transition-colors relative cursor-pointer ${
                    twoFactorEnabled ? "bg-[#00D1C1]" : "bg-slate-200"
                  }`}
                >
                  <span
                    className={`absolute top-0.5 left-0.5 w-5 h-5 bg-white rounded-full transition-transform shadow-xs ${
                      twoFactorEnabled ? "translate-x-6" : "translate-x-0"
                    }`}
                  />
                </button>
              </div>
            </div>
          </section>
        </div>

        {/* Right Column: Language, Theme & Save (4 columns) */}
        <div className="lg:col-span-4 space-y-8">
          {/* Section 3: Language */}
          <section className="bg-white/90 backdrop-blur-xl rounded-[16px] p-6 lg:p-8 shadow-[0px_4px_20px_rgba(16,18,19,0.05)] border border-slate-200/80">
            <div className="flex items-center mb-6">
              <Globe className="w-6 h-6 text-[#00D1C1] mr-3" />
              <h2 className="text-xl font-bold text-[#191C1E]">Ngôn ngữ</h2>
            </div>

            <div className="relative">
              <select
                value={language}
                onChange={(e) => setLanguage(e.target.value)}
                className="w-full bg-white border border-slate-200 text-[#191C1E] text-sm font-medium rounded-xl px-4 py-3 focus:outline-none focus:border-[#00D1C1] focus:ring-1 focus:ring-[#00D1C1] transition-all cursor-pointer"
              >
                <option value="vi">Tiếng Việt</option>
                <option value="en">English</option>
                <option value="fr">Français</option>
              </select>
            </div>
          </section>

          {/* Section 4: Theme / Appearance */}
          <section className="bg-white/90 backdrop-blur-xl rounded-[16px] p-6 lg:p-8 shadow-[0px_4px_20px_rgba(16,18,19,0.05)] border border-slate-200/80">
            <div className="flex items-center mb-6">
              <Palette className="w-6 h-6 text-[#00D1C1] mr-3" />
              <h2 className="text-xl font-bold text-[#191C1E]">Giao diện</h2>
            </div>

            <div className="grid grid-cols-2 gap-4">
              {/* Light Mode */}
              <button
                type="button"
                onClick={() => setTheme("light")}
                className={`p-4 rounded-xl border-2 text-center transition-all cursor-pointer ${
                  theme === "light"
                    ? "border-[#00D1C1] bg-[#00D1C1]/5 text-[#006a62] font-bold"
                    : "border-slate-200 bg-white text-slate-600 hover:border-slate-300"
                }`}
              >
                <Sun className="w-7 h-7 mx-auto mb-2 text-[#006a62]" />
                <p className="text-sm font-semibold">Sáng</p>
              </button>

              {/* Dark Mode */}
              <button
                type="button"
                onClick={() => setTheme("dark")}
                className={`p-4 rounded-xl border-2 text-center transition-all cursor-pointer bg-[#101213] ${
                  theme === "dark"
                    ? "border-[#00D1C1] text-white font-bold"
                    : "border-slate-700 text-slate-300 hover:border-slate-500"
                }`}
              >
                <Moon className="w-7 h-7 mx-auto mb-2 text-[#00D1C1]" />
                <p className="text-sm font-semibold text-white">Tối</p>
              </button>
            </div>
          </section>

          {/* Save Button */}
          <div className="pt-2 flex justify-end">
            <button
              type="button"
              onClick={handleSave}
              className="w-full lg:w-auto bg-[#00D1C1] hover:bg-[#006a62] text-white px-8 py-3 rounded-xl font-bold text-sm shadow-lg shadow-[#00D1C1]/20 transition-all flex items-center justify-center gap-2 cursor-pointer active:scale-98"
            >
              {isSaved ? (
                <>
                  <Check className="w-4 h-4" />
                  <span>Đã lưu!</span>
                </>
              ) : (
                <span>Lưu thay đổi</span>
              )}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
