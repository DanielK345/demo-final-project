import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Bell, Shield, Globe, Palette, Sun, Moon, Check, AlertCircle, Loader2 } from "lucide-react";
import { getSettings, updateSettings, changePassword, type UserSettings } from "@/features/settings/api";
import { redirectToLoginIfUnauthorized } from "@/features/auth/sessionGuard";

export const PaymentPage: React.FC = () => {
  const navigate = useNavigate();
  const [settings, setSettings] = useState<UserSettings | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [savedField, setSavedField] = useState<string | null>(null);

  const [isChangingPassword, setIsChangingPassword] = useState(false);
  const [oldPassword, setOldPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [passwordError, setPasswordError] = useState<string | null>(null);
  const [passwordSaved, setPasswordSaved] = useState(false);
  const [isSubmittingPassword, setIsSubmittingPassword] = useState(false);

  useEffect(() => {
    let cancelled = false;
    getSettings()
      .then((data) => {
        if (!cancelled) setSettings(data);
      })
      .catch((cause) => {
        if (cancelled) return;
        if (redirectToLoginIfUnauthorized(cause, navigate)) return;
        setError(cause instanceof Error ? cause.message : "Không thể tải cài đặt.");
      });
    return () => {
      cancelled = true;
    };
  }, [navigate]);

  const applyUpdate = async (field: keyof UserSettings, value: UserSettings[keyof UserSettings]) => {
    if (!settings) return;
    const previous = settings;
    setSettings({ ...settings, [field]: value });
    try {
      const updated = await updateSettings({ [field]: value });
      setSettings(updated);
      setSavedField(field);
      setTimeout(() => setSavedField(null), 1500);
    } catch (cause) {
      setSettings(previous);
      if (redirectToLoginIfUnauthorized(cause, navigate)) return;
      setError(cause instanceof Error ? cause.message : "Không thể lưu thay đổi.");
    }
  };

  const handleSubmitPassword = async (event: React.FormEvent) => {
    event.preventDefault();
    setPasswordError(null);
    setIsSubmittingPassword(true);
    try {
      await changePassword(oldPassword, newPassword);
      setPasswordSaved(true);
      setOldPassword("");
      setNewPassword("");
      setTimeout(() => {
        setPasswordSaved(false);
        setIsChangingPassword(false);
      }, 1500);
    } catch (cause) {
      if (redirectToLoginIfUnauthorized(cause, navigate)) return;
      setPasswordError(cause instanceof Error ? cause.message : "Không thể đổi mật khẩu.");
    } finally {
      setIsSubmittingPassword(false);
    }
  };

  if (error) {
    return (
      <p className="flex items-center gap-2 text-sm text-rose-700 bg-rose-50 border border-rose-200 rounded-xl p-3">
        <AlertCircle className="w-4 h-4 shrink-0" />
        <span>{error}</span>
      </p>
    );
  }

  if (!settings) {
    return <div className="text-sm text-slate-500 py-8 text-center">Đang tải cài đặt...</div>;
  }

  const Toggle: React.FC<{ field: keyof UserSettings; checked: boolean }> = ({ field, checked }) => (
    <div className="flex items-center gap-2">
      {savedField === field && <Check className="w-3.5 h-3.5 text-[#00D1C1]" />}
      <button
        type="button"
        onClick={() => applyUpdate(field, !checked)}
        className={`w-12 h-6 rounded-full transition-colors relative cursor-pointer ${
          checked ? "bg-[#00D1C1]" : "bg-slate-200"
        }`}
      >
        <span
          className={`absolute top-0.5 left-0.5 w-5 h-5 bg-white rounded-full transition-transform shadow-xs ${
            checked ? "translate-x-6" : "translate-x-0"
          }`}
        />
      </button>
    </div>
  );

  return (
    <div className="space-y-8 pb-12">
      {/* Page Title */}
      <div>
        <h1 className="text-3xl md:text-4xl font-extrabold text-[#191C1E] mb-2 tracking-tight">
          Cài đặt
        </h1>
        <p className="text-sm md:text-base text-slate-500">
          Quản lý tuỳ chọn thông báo, bảo mật và giao diện.
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
              <div className="flex items-center justify-between py-2 border-b border-slate-100">
                <div>
                  <h3 className="text-sm font-bold text-[#191C1E]">Push Notifications</h3>
                  <p className="text-xs text-slate-500 mt-0.5">Nhận thông báo tức thời trên thiết bị.</p>
                </div>
                <Toggle field="push_notifications" checked={settings.push_notifications} />
              </div>

              <div className="flex items-center justify-between py-2 border-b border-slate-100">
                <div>
                  <h3 className="text-sm font-bold text-[#191C1E]">Email Notifications</h3>
                  <p className="text-xs text-slate-500 mt-0.5">Tổng hợp hàng ngày và ưu đãi.</p>
                </div>
                <Toggle field="email_notifications" checked={settings.email_notifications} />
              </div>

              <div className="flex items-center justify-between py-2">
                <div>
                  <h3 className="text-sm font-bold text-[#191C1E]">SMS Notifications</h3>
                  <p className="text-xs text-slate-500 mt-0.5">Cảnh báo bảo mật và cập nhật chuyến đi quan trọng.</p>
                </div>
                <Toggle field="sms_notifications" checked={settings.sms_notifications} />
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
              <div className="py-2 border-b border-slate-100">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                  <div>
                    <h3 className="text-sm font-bold text-[#191C1E]">Mật khẩu</h3>
                    <p className="text-xs text-slate-500 mt-0.5">Đổi mật khẩu đăng nhập của bạn.</p>
                  </div>
                  <button
                    type="button"
                    onClick={() => setIsChangingPassword((open) => !open)}
                    className="px-5 py-2 rounded-xl bg-transparent border border-slate-700 text-slate-800 font-semibold text-xs hover:bg-slate-100 transition-colors whitespace-nowrap cursor-pointer"
                  >
                    {isChangingPassword ? "Đóng" : "Thay đổi mật khẩu"}
                  </button>
                </div>

                {isChangingPassword && (
                  <form onSubmit={handleSubmitPassword} className="mt-4 space-y-3">
                    <input
                      type="password"
                      required
                      placeholder="Mật khẩu hiện tại"
                      value={oldPassword}
                      onChange={(event) => setOldPassword(event.target.value)}
                      className="w-full rounded-xl border border-slate-200 bg-slate-50 px-4 py-2.5 text-sm outline-none focus:border-[#00D1C1]"
                    />
                    <input
                      type="password"
                      required
                      minLength={8}
                      placeholder="Mật khẩu mới (tối thiểu 8 ký tự)"
                      value={newPassword}
                      onChange={(event) => setNewPassword(event.target.value)}
                      className="w-full rounded-xl border border-slate-200 bg-slate-50 px-4 py-2.5 text-sm outline-none focus:border-[#00D1C1]"
                    />
                    {passwordError && (
                      <p className="text-xs text-rose-600 bg-rose-50 rounded-lg p-2.5">{passwordError}</p>
                    )}
                    <button
                      type="submit"
                      disabled={isSubmittingPassword}
                      className="flex items-center justify-center gap-2 rounded-xl bg-[#00D1C1] text-white font-bold text-xs px-5 py-2.5 hover:bg-[#006a62] transition-colors disabled:opacity-60"
                    >
                      {isSubmittingPassword && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
                      {passwordSaved ? (
                        <>
                          <Check className="w-3.5 h-3.5" /> Đã lưu
                        </>
                      ) : (
                        "Xác nhận đổi mật khẩu"
                      )}
                    </button>
                  </form>
                )}
              </div>

              {/* 2FA */}
              <div className="flex items-center justify-between py-2">
                <div>
                  <h3 className="text-sm font-bold text-[#191C1E]">Xác thực 2 yếu tố (2FA)</h3>
                  <p className="text-xs text-slate-500 mt-0.5">
                    Sắp ra mắt — lựa chọn của bạn được lưu lại nhưng chưa được áp dụng khi đăng nhập.
                  </p>
                </div>
                <Toggle field="two_factor_enabled" checked={settings.two_factor_enabled} />
              </div>
            </div>
          </section>
        </div>

        {/* Right Column: Language, Theme (4 columns) */}
        <div className="lg:col-span-4 space-y-8">
          {/* Section 3: Language */}
          <section className="bg-white/90 backdrop-blur-xl rounded-[16px] p-6 lg:p-8 shadow-[0px_4px_20px_rgba(16,18,19,0.05)] border border-slate-200/80">
            <div className="flex items-center mb-6">
              <Globe className="w-6 h-6 text-[#00D1C1] mr-3" />
              <h2 className="text-xl font-bold text-[#191C1E]">Ngôn ngữ</h2>
            </div>

            <div className="relative">
              <select
                value={settings.language}
                onChange={(event) => applyUpdate("language", event.target.value)}
                className="w-full bg-white border border-slate-200 text-[#191C1E] text-sm font-medium rounded-xl px-4 py-3 focus:outline-none focus:border-[#00D1C1] focus:ring-1 focus:ring-[#00D1C1] transition-all cursor-pointer"
              >
                <option value="vi">Tiếng Việt</option>
                <option value="en">English</option>
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
              <button
                type="button"
                onClick={() => applyUpdate("theme", "light")}
                className={`p-4 rounded-xl border-2 text-center transition-all cursor-pointer ${
                  settings.theme === "light"
                    ? "border-[#00D1C1] bg-[#00D1C1]/5 text-[#006a62] font-bold"
                    : "border-slate-200 bg-white text-slate-600 hover:border-slate-300"
                }`}
              >
                <Sun className="w-7 h-7 mx-auto mb-2 text-[#006a62]" />
                <p className="text-sm font-semibold">Sáng</p>
              </button>

              <button
                type="button"
                onClick={() => applyUpdate("theme", "dark")}
                className={`p-4 rounded-xl border-2 text-center transition-all cursor-pointer bg-[#101213] ${
                  settings.theme === "dark"
                    ? "border-[#00D1C1] text-white font-bold"
                    : "border-slate-700 text-slate-300 hover:border-slate-500"
                }`}
              >
                <Moon className="w-7 h-7 mx-auto mb-2 text-[#00D1C1]" />
                <p className="text-sm font-semibold text-white">Tối</p>
              </button>
            </div>
          </section>
        </div>
      </div>
    </div>
  );
};
