import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Clock, ChevronRight, RotateCcw, Car, AlertCircle, Sparkles } from "lucide-react";
import { listBookings, locationLabel, statusLabel, type BookingSummary } from "@/features/activity/api";
import { redirectToLoginIfUnauthorized } from "@/features/auth/sessionGuard";
import { useVoiceAssistant } from "@/features/ai-assistant/context/useVoiceAssistant";

interface ActivityListProps {
  activeFilter?: string;
}

function formatTime(iso: string | null): string {
  if (!iso) return "";
  try {
    return new Date(iso).toLocaleString("vi-VN", {
      day: "2-digit",
      month: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return "";
  }
}

function formatFare(fare: number | null, currency: string): string {
  if (fare == null) return "--";
  return `${fare.toLocaleString("vi-VN")} ${currency === "VND" ? "₫" : currency}`;
}

export const ActivityList: React.FC<ActivityListProps> = ({ activeFilter = "all" }) => {
  const navigate = useNavigate();
  const { open, openWithPrefill } = useVoiceAssistant();
  const [bookings, setBookings] = useState<BookingSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    listBookings()
      .then((data) => {
        if (!cancelled) setBookings(data);
      })
      .catch((cause) => {
        if (cancelled) return;
        if (redirectToLoginIfUnauthorized(cause, navigate)) return;
        setError(cause instanceof Error ? cause.message : "Không thể tải lịch sử chuyến đi.");
      });
    return () => {
      cancelled = true;
    };
  }, [navigate]);

  // Đặt lại 1 chuyến đã có giờ cũng nối thẳng vào AI Assistant (kèm sẵn tuyến đường
  // cũ trong câu mở đầu) thay vì tự mở form/modal riêng — cùng 1 đường đặt xe duy
  // nhất trong toàn app, xem BookingPage.tsx/HomePage.tsx.
  const rebookViaAssistant = (booking: BookingSummary) => {
    const pickup = locationLabel(booking.pickup, "điểm đón cũ");
    const destination = locationLabel(booking.destination, "điểm đến cũ");
    openWithPrefill(`Tôi muốn đặt lại chuyến từ ${pickup} đến ${destination}.`);
  };

  if (error) {
    return (
      <div className="flex items-center gap-2 text-sm text-rose-700 bg-rose-50 border border-rose-200 rounded-xl p-4 dark:text-rose-300 dark:bg-rose-500/10 dark:border-rose-500/30">
        <AlertCircle className="w-4 h-4 shrink-0" />
        <span>{error}</span>
      </div>
    );
  }

  if (bookings === null) {
    return <div className="text-sm text-slate-500 dark:text-slate-400 py-8 text-center">Đang tải lịch sử chuyến đi...</div>;
  }

  // Bug thật đã sửa: filter "last_month" (chip "Tháng trước" ở ActivityPage.tsx)
  // trước đây không có nhánh xử lý, rơi xuống `return true` giống hệt "all" — bấm
  // vào không lọc được gì, âm thầm sai chứ không lỗi rõ ràng.
  const filtered = bookings.filter((booking) => {
    if (activeFilter === "cancelled") return booking.status === "CANCELLED";
    if (activeFilter === "recent") return booking.status === "COMPLETED";
    if (activeFilter === "last_month") {
      if (!booking.created_at) return false;
      const createdAt = new Date(booking.created_at).getTime();
      const thirtyDaysAgo = Date.now() - 30 * 24 * 60 * 60 * 1000;
      return createdAt >= thirtyDaysAgo;
    }
    return true;
  });

  if (filtered.length === 0) {
    return (
      <div className="text-center py-16 space-y-3">
        <Car className="w-10 h-10 text-slate-300 dark:text-slate-600 mx-auto" />
        <p className="text-sm text-slate-500 dark:text-slate-400">Chưa có chuyến đi nào ở đây.</p>
        <button
          type="button"
          onClick={open}
          className="inline-flex items-center gap-1.5 text-sm font-bold text-[#006a62] dark:text-[#00D1C1] hover:underline"
        >
          <Sparkles className="w-4 h-4" />
          AI đặt xe ngay
        </button>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {filtered.map((booking) => {
        const isCancelled = booking.status === "CANCELLED";
        return (
          <div
            key={booking.booking_id}
            className="bg-white rounded-[24px] p-5 shadow-[0_4px_20px_rgba(16,18,19,0.05)] border border-slate-200/80 hover:shadow-md transition-shadow duration-200 flex flex-col md:flex-row gap-5 items-stretch overflow-hidden dark:bg-[#12161A] dark:border-white/10"
          >
            {/* Icon thay cho ảnh bản đồ giả — không có bản đồ tuyến đường thật */}
            <div className="w-full md:w-44 h-28 md:h-auto rounded-xl overflow-hidden bg-slate-100 shrink-0 relative border border-slate-200/60 flex items-center justify-center dark:bg-white/5 dark:border-white/10">
              <Car className={`w-10 h-10 ${isCancelled ? "text-slate-300 dark:text-slate-600" : "text-[#00D1C1]"}`} />
              <div className="absolute top-2 left-2">
                <span
                  className={`px-2.5 py-1 rounded-full text-[10px] font-bold uppercase tracking-wider ${
                    isCancelled
                      ? "bg-rose-100 text-rose-700 border border-rose-200 dark:bg-rose-500/10 dark:text-rose-300 dark:border-rose-500/30"
                      : "bg-[#00D1C1]/20 text-[#006a62] border border-[#00D1C1]/30 dark:text-[#00D1C1]"
                  }`}
                >
                  {statusLabel(booking.status)}
                </span>
              </div>
            </div>

            <div className="flex-1 flex flex-col justify-between space-y-4 py-0.5">
              <div className="space-y-3">
                <div className="flex items-center justify-between text-xs text-slate-500 dark:text-slate-400 font-medium">
                  <div className="flex items-center gap-1.5">
                    <Clock className="w-3.5 h-3.5 text-slate-400 dark:text-slate-500" />
                    <span>{formatTime(booking.created_at)}</span>
                  </div>
                  <ChevronRight className="w-4 h-4 text-slate-400 dark:text-slate-500" />
                </div>

                <div className="space-y-2 relative pl-5">
                  <div className="absolute left-[5px] top-2 bottom-2 w-0.5 bg-slate-200 dark:bg-white/10 z-0" />
                  <div className="relative z-10 text-xs">
                    <div className="absolute -left-[19px] top-1 w-2.5 h-2.5 rounded-full border-2 border-[#00D1C1] bg-white dark:bg-[#12161A]" />
                    <p className="font-semibold text-[#191C1E] dark:text-slate-100 line-clamp-1">
                      {locationLabel(booking.pickup, "Chưa rõ điểm đón")}
                    </p>
                  </div>
                  <div className="relative z-10 text-xs pt-1">
                    <div className="absolute -left-[19px] top-2 w-2.5 h-2.5 rounded-full bg-[#006a62] dark:bg-[#00D1C1]" />
                    <p className="font-semibold text-[#191C1E] dark:text-slate-100 line-clamp-1">
                      {locationLabel(booking.destination, "Chưa rõ điểm đến")}
                    </p>
                  </div>
                </div>
              </div>

              <div className="flex items-center justify-between pt-3 border-t border-slate-100 dark:border-white/10">
                <div>
                  <span className="text-[10px] font-bold text-slate-400 dark:text-slate-500 uppercase tracking-wider block">
                    Tổng cước
                  </span>
                  <span
                    className={`text-lg font-extrabold ${
                      isCancelled ? "line-through text-slate-400 dark:text-slate-600" : "text-[#191C1E] dark:text-white"
                    }`}
                  >
                    {formatFare(booking.estimated_fare, booking.currency)}
                  </span>
                </div>

                <button
                  type="button"
                  onClick={() => rebookViaAssistant(booking)}
                  className={`px-4 py-2 rounded-xl font-bold text-xs flex items-center gap-1.5 transition-all duration-200 cursor-pointer ${
                    isCancelled
                      ? "bg-slate-100 text-slate-600 hover:bg-slate-200 dark:bg-white/10 dark:text-slate-300 dark:hover:bg-white/20"
                      : "bg-[#006a62] hover:bg-[#00D1C1] text-white shadow-xs"
                  }`}
                >
                  <RotateCcw className="w-3.5 h-3.5" />
                  <span>AI đặt lại chuyến này</span>
                </button>
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
};
