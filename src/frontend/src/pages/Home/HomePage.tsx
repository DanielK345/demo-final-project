import React, { useEffect, useState } from "react";
import { NavLink, useNavigate } from "react-router-dom";
import {
  Sparkles,
  ArrowRight,
  Car,
  Crown,
  PlaneTakeoff,
  Briefcase,
  RotateCcw,
  MoreHorizontal,
} from "lucide-react";
import { getUserName } from "@/features/auth/storage";
import { listBookings, locationLabel, type BookingSummary } from "@/features/activity/api";
import { redirectToLoginIfUnauthorized } from "@/features/auth/sessionGuard";

export const HomePage: React.FC = () => {
  const navigate = useNavigate();
  const userName = getUserName();
  const [recentBookings, setRecentBookings] = useState<BookingSummary[]>([]);

  useEffect(() => {
    let cancelled = false;
    listBookings()
      .then((data) => {
        if (!cancelled) setRecentBookings(data.slice(0, 2));
      })
      .catch((cause) => {
        if (cancelled) return;
        redirectToLoginIfUnauthorized(cause, navigate);
        // Danh sách chuyến gần đây không phải nội dung thiết yếu của trang chủ — lỗi
        // tải được bỏ qua lặng lẽ ở đây (không chặn phần còn lại của trang), khác với
        // ActivityPage nơi đây LÀ nội dung chính, phải báo lỗi rõ ràng.
      });
    return () => {
      cancelled = true;
    };
  }, [navigate]);

  // Mọi nút đặt xe trên trang chủ giờ nối thẳng vào Agentic AI Assistant (đúng yêu
  // cầu: không tự bấm chọn dịch vụ/điền form nữa) — điều hướng sang /assistant kèm
  // `state.prefill`, AssistantPage tự gửi câu này ngay khi vào (xem AssistantPage.tsx)
  // giống hệt cơ chế quick-chip có sẵn, để agent tiếp quản hỏi xác nhận + đặt xe.
  const goToAssistant = (prefill: string) => {
    navigate("/assistant", { state: { prefill } });
  };

  const heroEvBg =
    "https://lh3.googleusercontent.com/aida-public/AB6AXuDz__xU-VKyGvWrkMn6EuJ7j_L7aaVl3Ophlb-0dJM7tNhsDU9oVMOFtKU8tqDydyYMKhcg-rllg1Pk7VRhGAx6lMEU8gAq7ejasrB6RGO8b31U6Z6RM8jnBhbIuOBQrAydBBLWmBc7bHvxORcHrSnj6s99C7qpemBbFyxNiKDBRGhf_Gp1GjHusOvf-2loVNBIcTbKD0UaVymNzeRbziJ6J49JyPncxbTsPnhpkNHaU-Dn6Su7z-Yz";

  const taxiImg =
    "https://lh3.googleusercontent.com/aida-public/AB6AXuDj_WooqtDLqEavzUHrfPdQxg5VQa531E5qcJpzikUOAHnA8nfJova0M0BJAZcyrAFmL_NtO05s9X1gfol0tgIQ1CtzNRIBgLOd1KqvvAWI6Tm5ZA12Nzd4wHFUOkgUY4muFpJ2yLefMaZvKfckfQf5hmwB4JZq-XaqWAM94ENRyW2zj72ntwojdxQxzXSbhHnwwDhZ28PxV75hVdnQfAnU_kD2po3CyLAoeNn7b6S7160sp2Yq7Xa1";

  const premiumImg =
    "https://lh3.googleusercontent.com/aida-public/AB6AXuDSszSjnPB--yu-oslQ7gLZOyO7UOBtifob125by_K-J0ONF57P4mlOdXWmpw8G-T-TT6ulAJLzPxpOKCuRRASP2rLM5BFzFA3UxA3H-6mSKWrZmyrUPt2yIV2Dgav_vVxx3Jt_6rt9qGoYQYUMC9w8qr8WUbpzariYcvX2oXANH2aAD4hdGdknYMmcKTCc0T17CJr0wogzHoUvW6O6hvduXl2SSq9yTyCFWIZoCvtEPzNkVSfX_m5W";

  const airportImg =
    "https://lh3.googleusercontent.com/aida-public/AB6AXuCjds2Uo7OpAZHXPuhSj9tfjmgtVcIpAG-eHlw__25tw6BgeffZGPaE5eZVrXQI7VSTw56eFijlrKt_56LmTaTVid5YKmAAl4me7LkONv61jy8ZsnKlGDKwrTGyhuM7vn52K3oVXUzyqCl86JBQwU2QuhIuhfMfpQrKrttBAU1bgSRD_fXGS5hfaLshNy0JoxhDGRn4SiPlOsx5vfP9O11s3bljyzsJVkSu3XNoeDBtqXw02hHhy3iG";

  return (
    <div className="space-y-8 pb-12">
      {/* Header Section (Personalization & Greeting) */}
      <section className="flex justify-between items-end">
        <div>
          <h1 className="text-3xl md:text-4xl font-extrabold text-[#191C1E] dark:text-white tracking-tight">
            Chào {userName},
          </h1>
          <p className="text-base md:text-lg text-slate-500 dark:text-slate-400 mt-2">
            Bạn muốn đi đâu hôm nay?
          </p>
        </div>

        {/* AI Assistant Prompt Card (Right side, Desktop) */}
        <NavLink
          to="/assistant"
          className="hidden lg:flex items-center gap-4 bg-white p-4 rounded-2xl shadow-[0px_4px_20px_rgba(16,18,19,0.05)] border border-slate-200/80 cursor-pointer group hover:shadow-md transition-all dark:bg-[#12161A] dark:border-white/10"
        >
          <div className="w-10 h-10 rounded-full bg-gradient-to-br from-[#00D1C1] to-[#006a62] flex items-center justify-center text-white shadow-md shadow-[#00D1C1]/30 group-hover:scale-105 transition-transform">
            <Sparkles className="w-5 h-5" />
          </div>
          <div>
            <p className="text-xs font-bold text-[#191C1E] dark:text-white">Hỏi trợ lý AI</p>
            <p className="text-[11px] text-slate-400 dark:text-slate-500 font-medium font-mono">"Đặt xe ra sân bay"</p>
          </div>
        </NavLink>
      </section>

      {/* Hero Carousel Banner */}
      <section className="relative w-full h-[300px] md:h-[400px] rounded-2xl overflow-hidden group cursor-pointer shadow-md">
        <div
          className="absolute inset-0 bg-cover bg-center w-full h-full transition-transform duration-700 group-hover:scale-105"
          style={{ backgroundImage: `url('${heroEvBg}')` }}
        />
        <div className="absolute inset-0 bg-gradient-to-t from-[#101213]/90 via-[#101213]/40 to-transparent" />

        <div className="absolute bottom-0 left-0 p-6 md:p-10 w-full md:w-2/3">
          <span className="inline-block px-3 py-1 mb-4 rounded bg-[#00D1C1]/20 text-[#00D1C1] text-xs font-semibold backdrop-blur-md border border-[#00D1C1]/30">
            Ưu đãi độc quyền
          </span>
          <h2 className="text-2xl md:text-4xl font-extrabold text-white mb-2 leading-tight">
            Trải nghiệm AloSM Premium
          </h2>
          <p className="text-sm md:text-base text-slate-200 mb-6">
            Giảm 20% cho chuyến đi đầu tiên với dòng xe điện cao cấp VF9.
          </p>
          <button
            type="button"
            onClick={() =>
              goToAssistant(
                "Tôi muốn đặt xe AloSM Premium (hạng sang) để nhận ưu đãi giảm 20% cho chuyến đầu tiên.",
              )
            }
            className="inline-flex items-center gap-2 bg-[#00D1C1] hover:bg-[#006a62] text-white font-bold text-xs px-6 py-3 rounded-[12px] transition-colors shadow-lg shadow-[#00D1C1]/20 cursor-pointer"
          >
            <Sparkles className="w-4 h-4" />
            AI đặt xe ngay
          </button>
        </div>
      </section>

      {/* Service Discovery (Bento Grid) */}
      <section>
        <h3 className="text-2xl font-extrabold text-[#191C1E] dark:text-white mb-6">Dịch vụ nổi bật</h3>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {/* Card 1: AloSM Taxi */}
          <button
            type="button"
            onClick={() => goToAssistant("Tôi muốn đặt xe AloSM Taxi loại 4 chỗ.")}
            className="text-left bg-white rounded-2xl border border-slate-200/80 shadow-[0px_4px_20px_rgba(16,18,19,0.05)] overflow-hidden flex flex-col group cursor-pointer hover:shadow-md transition-shadow dark:bg-[#12161A] dark:border-white/10"
          >
            <div className="h-48 relative overflow-hidden bg-slate-100 dark:bg-white/5">
              <div
                className="absolute inset-0 bg-cover bg-center transition-transform duration-500 group-hover:scale-105"
                style={{ backgroundImage: `url('${taxiImg}')` }}
              />
              <div className="absolute inset-0 bg-gradient-to-t from-[#101213]/60 to-transparent opacity-0 group-hover:opacity-100 transition-opacity" />
            </div>
            <div className="p-6 flex-1 flex flex-col justify-between">
              <div>
                <div className="flex justify-between items-start mb-2">
                  <h4 className="text-lg font-bold text-[#191C1E] dark:text-white">AloSM Taxi</h4>
                  <Car className="w-5 h-5 text-[#00D1C1]" />
                </div>
                <p className="text-xs text-slate-500 dark:text-slate-400 leading-relaxed">
                  Di chuyển hàng ngày nhanh chóng, êm ái và không phát thải.
                </p>
              </div>

              <div className="mt-6 flex items-center text-[#006a62] dark:text-[#00D1C1] text-xs font-bold group-hover:translate-x-1 transition-transform">
                <Sparkles className="w-3.5 h-3.5 mr-1.5" />
                <span>AI đặt xe ngay</span>
                <ArrowRight className="w-4 h-4 ml-1" />
              </div>
            </div>
          </button>

          {/* Card 2: AloSM Premium */}
          <button
            type="button"
            onClick={() => goToAssistant("Tôi muốn đặt xe AloSM Premium loại hạng sang.")}
            className="text-left bg-white rounded-2xl border border-slate-200/80 shadow-[0px_4px_20px_rgba(16,18,19,0.05)] overflow-hidden flex flex-col group cursor-pointer hover:shadow-md transition-shadow dark:bg-[#12161A] dark:border-white/10"
          >
            <div className="h-48 relative overflow-hidden bg-slate-100 dark:bg-white/5">
              <div
                className="absolute inset-0 bg-cover bg-center transition-transform duration-500 group-hover:scale-105"
                style={{ backgroundImage: `url('${premiumImg}')` }}
              />
              <div className="absolute inset-0 bg-gradient-to-t from-[#101213]/60 to-transparent opacity-0 group-hover:opacity-100 transition-opacity" />
            </div>
            <div className="p-6 flex-1 flex flex-col justify-between">
              <div>
                <div className="flex justify-between items-start mb-2">
                  <h4 className="text-lg font-bold text-[#191C1E] dark:text-white">AloSM Premium</h4>
                  <Crown className="w-5 h-5 text-[#00D1C1]" />
                </div>
                <p className="text-xs text-slate-500 dark:text-slate-400 leading-relaxed">
                  Dịch vụ đẳng cấp với dòng xe sang trọng, không gian riêng tư.
                </p>
              </div>

              <div className="mt-6 flex items-center text-[#006a62] dark:text-[#00D1C1] text-xs font-bold group-hover:translate-x-1 transition-transform">
                <Sparkles className="w-3.5 h-3.5 mr-1.5" />
                <span>AI đặt xe ngay</span>
                <ArrowRight className="w-4 h-4 ml-1" />
              </div>
            </div>
          </button>

          {/* Card 3: AloSM Sân bay */}
          <button
            type="button"
            onClick={() => goToAssistant("Tôi muốn đặt xe AloSM Sân bay, đưa đón sân bay đúng giờ.")}
            className="text-left bg-white rounded-2xl border border-slate-200/80 shadow-[0px_4px_20px_rgba(16,18,19,0.05)] overflow-hidden flex flex-col group cursor-pointer hover:shadow-md transition-shadow dark:bg-[#12161A] dark:border-white/10"
          >
            <div className="h-48 relative overflow-hidden bg-slate-100 dark:bg-white/5">
              <div
                className="absolute inset-0 bg-cover bg-center transition-transform duration-500 group-hover:scale-105"
                style={{ backgroundImage: `url('${airportImg}')` }}
              />
              <div className="absolute inset-0 bg-gradient-to-t from-[#101213]/60 to-transparent opacity-0 group-hover:opacity-100 transition-opacity" />
            </div>
            <div className="p-6 flex-1 flex flex-col justify-between">
              <div>
                <div className="flex justify-between items-start mb-2">
                  <h4 className="text-lg font-bold text-[#191C1E] dark:text-white">AloSM Sân bay</h4>
                  <PlaneTakeoff className="w-5 h-5 text-[#00D1C1]" />
                </div>
                <p className="text-xs text-slate-500 dark:text-slate-400 leading-relaxed">
                  Đưa đón sân bay đúng giờ, xe rộng rãi cho nhiều hành lý.
                </p>
              </div>

              <div className="mt-6 flex items-center text-[#006a62] dark:text-[#00D1C1] text-xs font-bold group-hover:translate-x-1 transition-transform">
                <Sparkles className="w-3.5 h-3.5 mr-1.5" />
                <span>AI đặt xe ngay</span>
                <ArrowRight className="w-4 h-4 ml-1" />
              </div>
            </div>
          </button>
        </div>
      </section>

      {/* Secondary Promo & Recent Activity Section */}
      <section className="grid grid-cols-1 lg:grid-cols-12 gap-6 pt-4">
        {/* Promo Banner (Spans 8 cols) */}
        <div className="lg:col-span-8 rounded-2xl overflow-hidden relative bg-gradient-to-br from-[#00D1C1] to-[#006a62] text-white p-8 md:p-12 flex flex-col justify-center items-start shadow-lg shadow-[#00D1C1]/10">
          {/* Abstract Glow Decor */}
          <div className="absolute top-0 right-0 w-64 h-64 bg-white/10 rounded-full blur-3xl -translate-y-1/2 translate-x-1/4 pointer-events-none" />

          <div className="relative z-10 w-full md:w-3/4">
            <h3 className="text-2xl md:text-3xl font-extrabold text-white mb-4">
              Di chuyển liên tỉnh dễ dàng
            </h3>
            <p className="text-sm text-white/90 mb-8 leading-relaxed">
              Trải nghiệm hành trình dài thoải mái, an toàn với chi phí tối ưu cùng dàn xe điện thế hệ mới.
            </p>
            <button
              type="button"
              className="border-2 border-white text-white hover:bg-white hover:text-[#006a62] font-bold text-xs px-6 py-3 rounded-[12px] transition-colors cursor-pointer"
            >
              Khám phá bảng giá
            </button>
          </div>
        </div>

        {/* Recent Activity (Spans 4 cols) */}
        <div className="lg:col-span-4 rounded-2xl bg-white p-6 border border-slate-200/80 shadow-[0px_4px_20px_rgba(16,18,19,0.05)] flex flex-col justify-between dark:bg-[#12161A] dark:border-white/10">
          <div>
            <div className="flex justify-between items-center mb-6">
              <h4 className="text-xs font-bold text-slate-400 dark:text-slate-500 uppercase tracking-wider">
                Chuyến đi gần đây
              </h4>
              <button
                type="button"
                className="text-slate-400 hover:text-slate-600 dark:text-slate-500 dark:hover:text-slate-300 transition-colors p-1 rounded cursor-pointer"
              >
                <MoreHorizontal className="w-5 h-5" />
              </button>
            </div>

            {recentBookings.length === 0 ? (
              <p className="text-xs text-slate-400 dark:text-slate-500 py-4 text-center">Chưa có chuyến đi nào gần đây.</p>
            ) : (
              <div className="flex flex-col gap-4">
                {recentBookings.map((booking) => (
                  <div
                    key={booking.booking_id}
                    className="flex items-center gap-4 p-3 rounded-xl hover:bg-slate-50 dark:hover:bg-white/5 transition-colors cursor-pointer"
                  >
                    <div className="w-10 h-10 rounded-xl bg-slate-100 dark:bg-white/10 flex items-center justify-center text-slate-600 dark:text-slate-300 shrink-0">
                      <Briefcase className="w-5 h-5" />
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="text-xs font-bold text-[#191C1E] dark:text-white truncate">
                        {locationLabel(booking.destination, "Chưa rõ điểm đến")}
                      </p>
                      <p className="text-[10px] text-slate-400 dark:text-slate-500 truncate">
                        {locationLabel(booking.pickup, "Chưa rõ điểm đón")}
                      </p>
                    </div>
                    <button
                      type="button"
                      onClick={() =>
                        goToAssistant(
                          `Tôi muốn đặt lại chuyến từ ${locationLabel(booking.pickup, "điểm đón cũ")} đến ${locationLabel(booking.destination, "điểm đến cũ")}.`,
                        )
                      }
                      title="AI đặt lại chuyến này"
                      className="text-[#00D1C1] hover:bg-[#00D1C1]/10 p-2 rounded-full transition-colors cursor-pointer"
                    >
                      <RotateCcw className="w-4 h-4" />
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>

          <NavLink to="/activity" className="block mt-6">
            <button
              type="button"
              className="w-full py-3 text-center text-[#006a62] dark:text-[#00D1C1] font-bold text-xs hover:bg-slate-50 dark:hover:bg-white/5 rounded-xl transition-colors border border-slate-200 dark:border-white/10 cursor-pointer"
            >
              Xem tất cả lịch sử
            </button>
          </NavLink>
        </div>
      </section>
    </div>
  );
};
