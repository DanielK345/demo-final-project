import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  Bell,
  Shield,
  Globe,
  Palette,
  Sun,
  Moon,
  Check,
  AlertCircle,
  Loader2,
  ShieldCheck,
  KeyRound,
} from "lucide-react";
import {
  getSettings,
  updateSettings,
  changePassword,
  setupTwoFactor,
  confirmTwoFactor,
  disableTwoFactor,
  type UserSettings,
  type TwoFactorSetup,
} from "@/features/settings/api";
import { redirectToLoginIfUnauthorized } from "@/features/auth/sessionGuard";
import { useTheme } from "@/app/providers/useTheme";

export const PaymentPage: React.FC = () => {
  const navigate = useNavigate();
  const { setTheme } = useTheme();
  const [settings, setSettings] = useState<UserSettings | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [savedField, setSavedField] = useState<string | null>(null);

  const [isChangingPassword, setIsChangingPassword] = useState(false);
  const [oldPassword, setOldPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [passwordError, setPasswordError] = useState<string | null>(null);
  const [passwordSaved, setPasswordSaved] = useState(false);
  const [isSubmittingPassword, setIsSubmittingPassword] = useState(false);

  // 2FA thật (TOTP) — "setup" là bước đang chờ nhập mã xác thực từ app authenticator
  // sau khi đã lấy secret; chưa bật thật cho tới khi confirmTwoFactor() thành công.
  const [twoFactorSetup, setTwoFactorSetup] = useState<TwoFactorSetup | null>(null);
  const [twoFactorCode, setTwoFactorCode] = useState("");
  const [twoFactorError, setTwoFactorError] = useState<string | null>(null);
  const [isTwoFactorBusy, setIsTwoFactorBusy] = useState(false);

  useEffect(() => {
    let cancelled = false;
    getSettings()
      .then((data) => {
        if (cancelled) return;
        setSettings(data);
        // Backend là nguồn đồng bộ chéo thiết bị — áp lại theme cục bộ theo giá trị
        // đã lưu (idempotent nếu đã trùng) để nhất quán khi đăng nhập trên máy khác.
        if (data.theme === "dark" || data.theme === "light") {
          setTheme(data.theme);
        }
      })
      .catch((cause) => {
        if (cancelled) return;
        if (redirectToLoginIfUnauthorized(cause, navigate)) return;
        setError(cause instanceof Error ? cause.message : "Không thể tải cài đặt.");
      });
    return () => {
      cancelled = true;
    };
  }, [navigate, setTheme]);

  const applyUpdate = async (field: keyof UserSettings, value: UserSettings[keyof UserSettings]) => {
    if (!settings) return;
    const previous = settings;
    setSettings({ ...settings, [field]: value });
    // Đổi giao diện ngay lập tức (không chờ round-trip API) — cảm giác phản hồi
    // tức thì, đúng tinh thần 1 cú bấm là đổi theme cho toàn site.
    if (field === "theme" && (value === "dark" || value === "light")) {
      setTheme(value);
    }
    try {
      const updated = await updateSettings({ [field]: value });
      setSettings(updated);
      setSavedField(field);
      setTimeout(() => setSavedField(null), 1500);
    } catch (cause) {
      setSettings(previous);
      if (field === "theme" && (previous.theme === "dark" || previous.theme === "light")) {
        setTheme(previous.theme);
      }
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

  const handleStartTwoFactorSetup = async () => {
    setTwoFactorError(null);
    setIsTwoFactorBusy(true);
    try {
      const setup = await setupTwoFactor();
      setTwoFactorSetup(setup);
    } catch (cause) {
      if (redirectToLoginIfUnauthorized(cause, navigate)) return;
      setTwoFactorError(cause instanceof Error ? cause.message : "Không thể bắt đầu bật 2FA.");
    } finally {
      setIsTwoFactorBusy(false);
    }
  };

  const handleCancelTwoFactorSetup = () => {
    setTwoFactorSetup(null);
    setTwoFactorCode("");
    setTwoFactorError(null);
  };

  const handleConfirmTwoFactor = async (event: React.FormEvent) => {
    event.preventDefault();
    setTwoFactorError(null);
    setIsTwoFactorBusy(true);
    try {
      await confirmTwoFactor(twoFactorCode);
      setSettings((current) => (current ? { ...current, two_factor_enabled: true } : current));
      setTwoFactorSetup(null);
      setTwoFactorCode("");
    } catch (cause) {
      if (redirectToLoginIfUnauthorized(cause, navigate)) return;
      setTwoFactorError(cause instanceof Error ? cause.message : "Mã xác thực không đúng.");
    } finally {
      setIsTwoFactorBusy(false);
    }
  };

  const handleDisableTwoFactor = async () => {
    setTwoFactorError(null);
    setIsTwoFactorBusy(true);
    try {
      await disableTwoFactor();
      setSettings((current) => (current ? { ...current, two_factor_enabled: false } : current));
    } catch (cause) {
      if (redirectToLoginIfUnauthorized(cause, navigate)) return;
      setTwoFactorError(cause instanceof Error ? cause.message : "Không thể tắt 2FA.");
    } finally {
      setIsTwoFactorBusy(false);
    }
  };

  if (error) {
    return (
      <p className="flex items-center gap-2 text-sm text-rose-700 bg-rose-50 border border-rose-200 rounded-xl p-3 dark:text-rose-300 dark:bg-rose-500/10 dark:border-rose-500/30">
        <AlertCircle className="w-4 h-4 shrink-0" />
        <span>{error}</span>
      </p>
    );
  }

  if (!settings) {
    return <div className="text-sm text-slate-500 dark:text-slate-400 py-8 text-center">Đang tải cài đặt...</div>;
  }

  const Toggle: React.FC<{ field: keyof UserSettings; checked: boolean }> = ({ field, checked }) => (
    <div className="flex items-center gap-2">
      {savedField === field && <Check className="w-3.5 h-3.5 text-[#00D1C1]" />}
      <button
        type="button"
        onClick={() => applyUpdate(field, !checked)}
        className={`w-12 h-6 rounded-full transition-colors relative cursor-pointer ${
          checked ? "bg-[#00D1C1]" : "bg-slate-200 dark:bg-white/10"
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
        <h1 className="text-3xl md:text-4xl font-extrabold text-[#191C1E] dark:text-white mb-2 tracking-tight">
          Cài đặt
        </h1>
        <p className="text-sm md:text-base text-slate-500 dark:text-slate-400">
          Quản lý tuỳ chọn thông báo, bảo mật và giao diện.
        </p>
      </div>

      {/* Main Settings Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-start">
        {/* Left Column: Notifications & Security (8 columns) */}
        <div className="lg:col-span-8 space-y-8">
          {/* Section 1: Notifications */}
          <section className="bg-white/90 backdrop-blur-xl rounded-[16px] p-6 lg:p-8 shadow-[0px_4px_20px_rgba(16,18,19,0.05)] border border-slate-200/80 dark:bg-[#12161A]/90 dark:border-white/10">
            <div className="flex items-center mb-6">
              <Bell className="w-6 h-6 text-[#00D1C1] mr-3" />
              <h2 className="text-xl font-bold text-[#191C1E] dark:text-white">Thông báo</h2>
            </div>

            <div className="space-y-6">
              <div className="flex items-center justify-between py-2 border-b border-slate-100 dark:border-white/10">
                <div>
                  <h3 className="text-sm font-bold text-[#191C1E] dark:text-white">Push Notifications</h3>
                  <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">Nhận thông báo tức thời trên thiết bị.</p>
                </div>
                <Toggle field="push_notifications" checked={settings.push_notifications} />
              </div>

              <div className="flex items-center justify-between py-2 border-b border-slate-100 dark:border-white/10">
                <div>
                  <h3 className="text-sm font-bold text-[#191C1E] dark:text-white">Email Notifications</h3>
                  <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">Tổng hợp hàng ngày và ưu đãi.</p>
                </div>
                <Toggle field="email_notifications" checked={settings.email_notifications} />
              </div>

              <div className="flex items-center justify-between py-2">
                <div>
                  <h3 className="text-sm font-bold text-[#191C1E] dark:text-white">SMS Notifications</h3>
                  <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">Cảnh báo bảo mật và cập nhật chuyến đi quan trọng.</p>
                </div>
                <Toggle field="sms_notifications" checked={settings.sms_notifications} />
              </div>
            </div>
          </section>

          {/* Section 2: Security */}
          <section className="bg-white/90 backdrop-blur-xl rounded-[16px] p-6 lg:p-8 shadow-[0px_4px_20px_rgba(16,18,19,0.05)] border border-slate-200/80 dark:bg-[#12161A]/90 dark:border-white/10">
            <div className="flex items-center mb-6">
              <Shield className="w-6 h-6 text-[#00D1C1] mr-3" />
              <h2 className="text-xl font-bold text-[#191C1E] dark:text-white">Bảo mật</h2>
            </div>

            <div className="space-y-6">
              {/* Password */}
              <div className="py-2 border-b border-slate-100 dark:border-white/10">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                  <div>
                    <h3 className="text-sm font-bold text-[#191C1E] dark:text-white">Mật khẩu</h3>
                    <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">Đổi mật khẩu đăng nhập của bạn.</p>
                  </div>
                  <button
                    type="button"
                    onClick={() => setIsChangingPassword((open) => !open)}
                    className="px-5 py-2 rounded-xl bg-transparent border border-slate-700 text-slate-800 font-semibold text-xs hover:bg-slate-100 transition-colors whitespace-nowrap cursor-pointer dark:border-white/20 dark:text-slate-100 dark:hover:bg-white/10"
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
                      className="w-full rounded-xl border border-slate-200 bg-slate-50 px-4 py-2.5 text-sm outline-none focus:border-[#00D1C1] dark:border-white/10 dark:bg-white/5 dark:text-white"
                    />
                    <input
                      type="password"
                      required
                      minLength={8}
                      placeholder="Mật khẩu mới (tối thiểu 8 ký tự)"
                      value={newPassword}
                      onChange={(event) => setNewPassword(event.target.value)}
                      className="w-full rounded-xl border border-slate-200 bg-slate-50 px-4 py-2.5 text-sm outline-none focus:border-[#00D1C1] dark:border-white/10 dark:bg-white/5 dark:text-white"
                    />
                    {passwordError && (
                      <p className="text-xs text-rose-600 bg-rose-50 rounded-lg p-2.5 dark:text-rose-300 dark:bg-rose-500/10">{passwordError}</p>
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
              <div className="py-2">
                <div className="flex items-center justify-between">
                  <div>
                    <h3 className="text-sm font-bold text-[#191C1E] dark:text-white">Xác thực 2 yếu tố (2FA)</h3>
                    <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
                      {settings.two_factor_enabled
                        ? "Đã bật — cần thêm mã từ app authenticator (vd Google Authenticator) mỗi lần đăng nhập."
                        : "Bảo vệ tài khoản bằng mã TOTP từ app authenticator, ngoài mật khẩu."}
                    </p>
                  </div>
                  {settings.two_factor_enabled ? (
                    <span className="inline-flex items-center gap-1.5 text-xs font-bold text-emerald-700 bg-emerald-50 border border-emerald-200 rounded-full px-3 py-1.5 dark:text-emerald-300 dark:bg-emerald-500/10 dark:border-emerald-500/30">
                      <ShieldCheck className="w-3.5 h-3.5" />
                      Đã bật
                    </span>
                  ) : (
                    !twoFactorSetup && (
                      <button
                        type="button"
                        onClick={handleStartTwoFactorSetup}
                        disabled={isTwoFactorBusy}
                        className="px-5 py-2 rounded-xl bg-transparent border border-slate-700 text-slate-800 font-semibold text-xs hover:bg-slate-100 transition-colors whitespace-nowrap cursor-pointer disabled:opacity-60 dark:border-white/20 dark:text-slate-100 dark:hover:bg-white/10"
                      >
                        Bật xác thực 2 lớp
                      </button>
                    )
                  )}
                </div>

                {settings.two_factor_enabled && (
                  <button
                    type="button"
                    onClick={handleDisableTwoFactor}
                    disabled={isTwoFactorBusy}
                    className="mt-3 text-xs font-semibold text-rose-600 hover:underline disabled:opacity-60 dark:text-rose-400"
                  >
                    {isTwoFactorBusy ? "Đang tắt..." : "Tắt xác thực 2 lớp"}
                  </button>
                )}

                {/* Bước thiết lập: secret vừa tạo CHƯA thật sự bật cho tới khi nhập
                    đúng 1 mã sinh ra từ nó — tránh tự khoá tài khoản bằng secret
                    chưa từng verify. */}
                {twoFactorSetup && (
                  <form onSubmit={handleConfirmTwoFactor} className="mt-4 space-y-3 rounded-xl border border-slate-200 bg-slate-50 p-4 dark:border-white/10 dark:bg-white/5">
                    <p className="text-xs font-semibold text-slate-700 dark:text-slate-300 flex items-center gap-1.5">
                      <KeyRound className="w-3.5 h-3.5 text-[#00D1C1]" />
                      Thêm mã bí mật sau vào app authenticator (Google Authenticator, Authy...):
                    </p>
                    <p className="font-mono text-sm font-bold tracking-wider text-[#191C1E] bg-white border border-slate-200 rounded-lg px-3 py-2 select-all break-all dark:bg-[#0B0E11] dark:border-white/10 dark:text-white">
                      {twoFactorSetup.secret}
                    </p>
                    <p className="text-[11px] text-slate-500 dark:text-slate-400">
                      Hoặc dùng liên kết:{" "}
                      <a
                        href={twoFactorSetup.otpauth_url}
                        className="font-mono text-[#006a62] dark:text-[#00D1C1] underline break-all"
                      >
                        {twoFactorSetup.otpauth_url}
                      </a>
                    </p>
                    <input
                      required
                      inputMode="numeric"
                      pattern="[0-9]{6}"
                      maxLength={6}
                      placeholder="Nhập mã 6 số"
                      value={twoFactorCode}
                      onChange={(event) => setTwoFactorCode(event.target.value.replace(/\D/g, "").slice(0, 6))}
                      className="w-full rounded-xl border border-slate-200 bg-white px-4 py-2.5 text-sm tracking-[0.3em] text-center font-mono outline-none focus:border-[#00D1C1] dark:border-white/10 dark:bg-[#0B0E11] dark:text-white"
                    />
                    {twoFactorError && (
                      <p className="text-xs text-rose-600 bg-rose-50 rounded-lg p-2.5 dark:text-rose-300 dark:bg-rose-500/10">
                        {twoFactorError}
                      </p>
                    )}
                    <div className="flex gap-2">
                      <button
                        type="submit"
                        disabled={isTwoFactorBusy || twoFactorCode.length !== 6}
                        className="flex items-center justify-center gap-2 rounded-xl bg-[#00D1C1] text-white font-bold text-xs px-5 py-2.5 hover:bg-[#006a62] transition-colors disabled:opacity-60"
                      >
                        {isTwoFactorBusy && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
                        Xác nhận bật 2FA
                      </button>
                      <button
                        type="button"
                        onClick={handleCancelTwoFactorSetup}
                        className="rounded-xl border border-slate-200 text-slate-600 font-semibold text-xs px-5 py-2.5 hover:bg-slate-100 transition-colors dark:border-white/10 dark:text-slate-300 dark:hover:bg-white/10"
                      >
                        Huỷ
                      </button>
                    </div>
                  </form>
                )}
                {!twoFactorSetup && twoFactorError && (
                  <p className="mt-3 text-xs text-rose-600 bg-rose-50 rounded-lg p-2.5 dark:text-rose-300 dark:bg-rose-500/10">
                    {twoFactorError}
                  </p>
                )}
              </div>
            </div>
          </section>
        </div>

        {/* Right Column: Language, Theme (4 columns) */}
        <div className="lg:col-span-4 space-y-8">
          {/* Section 3: Language */}
          <section className="bg-white/90 backdrop-blur-xl rounded-[16px] p-6 lg:p-8 shadow-[0px_4px_20px_rgba(16,18,19,0.05)] border border-slate-200/80 dark:bg-[#12161A]/90 dark:border-white/10">
            <div className="flex items-center mb-6">
              <Globe className="w-6 h-6 text-[#00D1C1] mr-3" />
              <h2 className="text-xl font-bold text-[#191C1E] dark:text-white">Ngôn ngữ</h2>
            </div>

            <div className="relative">
              <select
                value={settings.language}
                onChange={(event) => applyUpdate("language", event.target.value)}
                className="w-full bg-white border border-slate-200 text-[#191C1E] text-sm font-medium rounded-xl px-4 py-3 focus:outline-none focus:border-[#00D1C1] focus:ring-1 focus:ring-[#00D1C1] transition-all cursor-pointer dark:bg-white/5 dark:border-white/10 dark:text-white"
              >
                <option value="vi">Tiếng Việt</option>
                <option value="en">English</option>
              </select>
            </div>
          </section>

          {/* Section 4: Theme / Appearance */}
          <section className="bg-white/90 backdrop-blur-xl rounded-[16px] p-6 lg:p-8 shadow-[0px_4px_20px_rgba(16,18,19,0.05)] border border-slate-200/80 dark:bg-[#12161A]/90 dark:border-white/10">
            <div className="flex items-center mb-6">
              <Palette className="w-6 h-6 text-[#00D1C1] mr-3" />
              <h2 className="text-xl font-bold text-[#191C1E] dark:text-white">Giao diện</h2>
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
