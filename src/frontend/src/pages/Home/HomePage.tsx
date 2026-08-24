import React, { useEffect, useState } from "react";
import { NavLink, useNavigate } from "react-router-dom";
import { ArrowRight, Bell, Bike, BriefcaseBusiness, CalendarClock, Car, ChevronRight, Gift, MapPin, Package, Plane, Search, ShieldCheck, Sparkles } from "lucide-react";
import { getUserName } from "@/features/auth/storage";
import { listBookings, locationLabel, type BookingSummary } from "@/features/activity/api";
import { redirectToLoginIfUnauthorized } from "@/features/auth/sessionGuard";
import { useVoiceAssistant } from "@/features/ai-assistant/context/useVoiceAssistant";

const quickServices = [
  { label: "Xe máy", icon: Bike, prompt: "Tôi muốn đặt xe máy.", tone: "from-cyan-100 to-teal-50" },
  { label: "Hẹn giờ", icon: CalendarClock, prompt: "Tôi muốn hẹn giờ đặt xe.", tone: "from-sky-100 to-cyan-50" },
  { label: "Liên tỉnh", icon: MapPin, prompt: "Tôi muốn đặt xe đi liên tỉnh.", tone: "from-emerald-100 to-cyan-50" },
  { label: "Giao hàng", icon: Package, prompt: "Tôi muốn đặt dịch vụ giao hàng.", tone: "from-amber-100 to-cyan-50" },
  { label: "Sân bay", icon: Plane, prompt: "Tôi muốn đặt xe đi sân bay.", tone: "from-blue-100 to-cyan-50" },
  { label: "Doanh nghiệp", icon: BriefcaseBusiness, prompt: "Tôi cần dịch vụ xe doanh nghiệp.", tone: "from-slate-100 to-cyan-50" },
  { label: "An toàn", icon: ShieldCheck, prompt: "Cho tôi biết về an toàn chuyến đi.", tone: "from-teal-100 to-cyan-50" },
  { label: "Ưu đãi", icon: Gift, prompt: "Tôi muốn xem ưu đãi đặt xe.", tone: "from-yellow-100 to-cyan-50" },
];

const heroImage = "https://lh3.googleusercontent.com/aida-public/AB6AXuDz__xU-VKyGvWrkMn6EuJ7j_L7aaVl3Ophlb-0dJM7tNhsDU9oVMOFtKU8tqDydyYMKhcg-rllg1Pk7VRhGAx6lMEU8gAq7ejasrB6RGO8b31U6Z6RM8jnBhbIuOBQrAydBBLWmBc7bHvxORcHrSnj6s99C7qpemBbFyxNiKDBRGhf_Gp1GjHusOvf-2loVNBIcTbKD0UaVymNzeRbziJ6J49JyPncxbTsPnhpkNHaU-Dn6Su7z-Yz";

export const HomePage: React.FC = () => {
  const navigate = useNavigate();
  const userName = getUserName();
  const { openWithPrefill, open } = useVoiceAssistant();
  const [recentBookings, setRecentBookings] = useState<BookingSummary[]>([]);

  useEffect(() => {
    let cancelled = false;
    listBookings().then((data) => !cancelled && setRecentBookings(data.slice(0, 2))).catch((cause) => {
      if (!cancelled) redirectToLoginIfUnauthorized(cause, navigate);
    });
    return () => { cancelled = true; };
  }, [navigate]);

  return (
    <div className="mx-auto max-w-6xl space-y-7 pb-10">
      <header className="flex items-center justify-between pt-1">
        <div><p className="text-xs font-bold uppercase tracking-[.18em] text-[#008F88]">AloSM mobility</p><h1 className="mt-1 text-2xl sm:text-3xl font-extrabold tracking-tight text-[#173132] dark:text-white">Chào {userName || "bạn"} 👋</h1></div>
        <button type="button" className="mobility-card grid h-12 w-12 place-items-center text-slate-600 dark:text-slate-200" aria-label="Thông báo"><Bell className="h-5 w-5" /></button>
      </header>

      <button type="button" onClick={open} className="mobility-input flex w-full items-center gap-4 px-5 py-5 text-left transition hover:-translate-y-0.5 hover:shadow-xl"><Search className="h-6 w-6 shrink-0 text-[#173132] dark:text-slate-100" /><span className="flex-1 text-lg font-semibold text-slate-400">Bạn muốn đi đâu?</span><span className="grid h-10 w-10 place-items-center rounded-2xl bg-[#00C9B7] text-white"><Sparkles className="h-5 w-5" /></span></button>

      <section className="soft-cyan-panel overflow-hidden rounded-[32px] p-5 sm:p-7 shadow-[0_16px_50px_rgba(0,143,136,.10)]"><div className="grid gap-5 md:grid-cols-[1.1fr_.9fr] md:items-center"><div><span className="inline-flex items-center gap-2 rounded-full bg-white/80 px-3 py-1.5 text-xs font-bold text-[#008F88]"><Sparkles className="h-4 w-4" /> AI đặt xe thông minh</span><h2 className="mt-4 text-2xl sm:text-4xl font-extrabold leading-tight text-[#173132]">Sáng bánh mật,<br />đặt xe đi cho lẹ nhé!</h2><div className="mt-5 flex flex-wrap gap-2">{["Đặt xe đi làm", "Đặt xe ra sân bay"].map((label) => <button key={label} type="button" onClick={() => openWithPrefill(label)} className="mobility-chip px-4 py-2 text-xs font-bold text-[#315052]">{label}</button>)}</div></div><div className="relative min-h-48 overflow-hidden rounded-[26px] bg-[#00C9B7]"><img src={heroImage} alt="Xe điện AloSM" className="absolute inset-0 h-full w-full object-cover" /><div className="absolute inset-0 bg-gradient-to-t from-[#073B3A]/60 to-transparent" /><button type="button" onClick={() => openWithPrefill("Tôi muốn đặt ô tô 4 chỗ.")} className="absolute bottom-4 left-4 right-4 flex items-center justify-between rounded-2xl bg-white/92 px-4 py-3 text-sm font-extrabold text-[#173132] backdrop-blur">Đặt ô tô ngay <ArrowRight className="h-4 w-4 text-[#00C9B7]" /></button></div></div></section>

      <section><div className="mb-4 flex items-center justify-between"><h2 className="text-xl sm:text-2xl font-extrabold text-[#173132] dark:text-white">Dịch vụ của bạn</h2><NavLink to="/booking" className="flex items-center text-xs font-bold text-[#008F88]">Xem tất cả <ChevronRight className="h-4 w-4" /></NavLink></div><div className="grid grid-cols-4 gap-3 sm:grid-cols-8">{quickServices.map(({ label, icon: Icon, prompt, tone }) => <button key={label} type="button" onClick={() => openWithPrefill(prompt)} className="group flex flex-col items-center gap-2 text-center"><span className={`grid aspect-square w-full max-w-[82px] place-items-center rounded-[24px] bg-gradient-to-br ${tone} border border-white shadow-[0_8px_24px_rgba(0,143,136,.08)] transition group-hover:-translate-y-1`}><Icon className="h-7 w-7 text-[#00B9AE]" /></span><span className="text-[11px] font-semibold text-slate-700 dark:text-slate-300">{label}</span></button>)}</div></section>

      <section className="grid gap-4 md:grid-cols-2"><button type="button" onClick={() => openWithPrefill("Tôi muốn đặt xe máy.")} className="mobility-card flex min-h-44 items-center justify-between overflow-hidden p-6 text-left"><div><span className="text-xs font-bold text-[#008F88]">DI CHUYỂN LINH HOẠT</span><h3 className="mt-2 text-2xl font-extrabold text-[#173132] dark:text-white">Đặt xe máy</h3><p className="mt-2 max-w-xs text-sm text-slate-500">Nhanh chóng, tiện lợi và thân thiện với môi trường.</p></div><span className="grid h-24 w-24 shrink-0 place-items-center rounded-[30px] bg-gradient-to-br from-cyan-100 to-teal-50"><Bike className="h-12 w-12 text-[#00B9AE]" /></span></button><button type="button" onClick={() => openWithPrefill("Tôi muốn đặt ô tô.")} className="mobility-card flex min-h-44 items-center justify-between overflow-hidden p-6 text-left"><div><span className="text-xs font-bold text-[#008F88]">ÊM ÁI MỖI CHUYẾN</span><h3 className="mt-2 text-2xl font-extrabold text-[#173132] dark:text-white">Đặt ô tô</h3><p className="mt-2 max-w-xs text-sm text-slate-500">Không gian thoải mái, tài xế chuyên nghiệp.</p></div><span className="grid h-24 w-24 shrink-0 place-items-center rounded-[30px] bg-gradient-to-br from-sky-100 to-cyan-50"><Car className="h-12 w-12 text-[#36BDE3]" /></span></button></section>

      <section className="mobility-card p-5 sm:p-6"><div className="flex items-center justify-between"><div><p className="text-xs font-bold uppercase tracking-wider text-slate-400">Chuyến gần đây</p><h2 className="mt-1 text-xl font-extrabold text-[#173132] dark:text-white">Đi lại chỉ với một chạm</h2></div><NavLink to="/activity" className="grid h-10 w-10 place-items-center rounded-full bg-[#E7FBF9] text-[#008F88]"><ArrowRight className="h-5 w-5" /></NavLink></div><div className="mt-5 grid gap-3 md:grid-cols-2">{recentBookings.length ? recentBookings.map((booking) => <button key={booking.booking_id} type="button" onClick={() => openWithPrefill(`Đặt lại chuyến đến ${locationLabel(booking.destination, "điểm đến cũ")}.`)} className="flex items-center gap-4 rounded-2xl bg-[#F6FAFA] p-4 text-left dark:bg-white/5"><span className="grid h-11 w-11 place-items-center rounded-2xl bg-white text-[#00C9B7] shadow-sm dark:bg-white/10"><MapPin className="h-5 w-5" /></span><span className="min-w-0 flex-1"><strong className="block truncate text-sm text-[#173132] dark:text-white">{locationLabel(booking.destination, "Điểm đến")}</strong><small className="block truncate text-slate-400">{locationLabel(booking.pickup, "Điểm đón")}</small></span><ChevronRight className="h-4 w-4 text-slate-400" /></button>) : <p className="col-span-2 rounded-2xl bg-[#F6FAFA] p-5 text-center text-sm text-slate-400 dark:bg-white/5">Chưa có chuyến gần đây. Hãy bắt đầu chuyến đầu tiên!</p>}</div></section>
    </div>
  );
};