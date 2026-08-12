import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Clock, ChevronRight, RotateCcw, Car, AlertCircle } from "lucide-react";
import { listBookings, locationLabel, statusLabel, type BookingSummary } from "@/features/activity/api";
import { redirectToLoginIfUnauthorized } from "@/features/auth/sessionGuard";

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

  if (error) {
    return (
      <div className="flex items-center gap-2 text-sm text-rose-700 bg-rose-50 border border-rose-200 rounded-xl p-4">
        <AlertCircle className="w-4 h-4 shrink-0" />
        <span>{error}</span>
      </div>
    );
  }

  if (bookings === null) {
    return <div className="text-sm text-slate-500 py-8 text-center">Đang tải lịch sử chuyến đi...</div>;
  }

  const filtered = bookings.filter((booking) => {
    if (activeFilter === "cancelled") return booking.status === "CANCELLED";
    if (activeFilter === "recent") return booking.status === "COMPLETED";
    return true;
  });

  if (filtered.length === 0) {
    return (
      <div className="text-center py-16 space-y-3">
        <Car className="w-10 h-10 text-slate-300 mx-auto" />
        <p className="text-sm text-slate-500">Chưa có chuyến đi nào ở đây.</p>
        <button
          type="button"
          onClick={() => navigate("/booking")}
          className="text-sm font-bold text-[#006a62] hover:underline"
        >
          Đặt xe ngay
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
            className="bg-white rounded-[24px] p-5 shadow-[0_4px_20px_rgba(16,18,19,0.05)] border border-slate-200/80 hover:shadow-md transition-shadow duration-200 flex flex-col md:flex-row gap-5 items-stretch overflow-hidden"
          >
            {/* Icon thay cho ảnh bản đồ giả — không có bản đồ tuyến đường thật */}
            <div className="w-full md:w-44 h-28 md:h-auto rounded-xl overflow-hidden bg-slate-100 shrink-0 relative border border-slate-200/60 flex items-center justify-center">
              <Car className={`w-10 h-10 ${isCancelled ? "text-slate-300" : "text-[#00D1C1]"}`} />
              <div className="absolute top-2 left-2">
                <span
                  className={`px-2.5 py-1 rounded-full text-[10px] font-bold uppercase tracking-wider ${
                    isCancelled
                      ? "bg-rose-100 text-rose-700 border border-rose-200"
                      : "bg-[#00D1C1]/20 text-[#006a62] border border-[#00D1C1]/30"
                  }`}
                >
                  {statusLabel(booking.status)}
                </span>
              </div>
            </div>

            <div className="flex-1 flex flex-col justify-between space-y-4 py-0.5">
              <div className="space-y-3">
                <div className="flex items-center justify-between text-xs text-slate-500 font-medium">
                  <div className="flex items-center gap-1.5">
                    <Clock className="w-3.5 h-3.5 text-slate-400" />
                    <span>{formatTime(booking.created_at)}</span>
                  </div>
                  <ChevronRight className="w-4 h-4 text-slate-400" />
                </div>

                <div className="space-y-2 relative pl-5">
                  <div className="absolute left-[5px] top-2 bottom-2 w-0.5 bg-slate-200 z-0" />
                  <div className="relative z-10 text-xs">
                    <div className="absolute -left-[19px] top-1 w-2.5 h-2.5 rounded-full border-2 border-[#00D1C1] bg-white" />
                    <p className="font-semibold text-[#191C1E] line-clamp-1">
                      {locationLabel(booking.pickup, "Chưa rõ điểm đón")}
                    </p>
                  </div>
                  <div className="relative z-10 text-xs pt-1">
                    <div className="absolute -left-[19px] top-2 w-2.5 h-2.5 rounded-full bg-[#006a62]" />
                    <p className="font-semibold text-[#191C1E] line-clamp-1">
                      {locationLabel(booking.destination, "Chưa rõ điểm đến")}
                    </p>
                  </div>
                </div>
              </div>

              <div className="flex items-center justify-between pt-3 border-t border-slate-100">
                <div>
                  <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider block">
                    Tổng cước
                  </span>
                  <span
                    className={`text-lg font-extrabold ${
                      isCancelled ? "line-through text-slate-400" : "text-[#191C1E]"
                    }`}
                  >
                    {formatFare(booking.estimated_fare, booking.currency)}
                  </span>
                </div>

                <button
                  type="button"
                  onClick={() =>
                    navigate("/booking", {
                      state: {
                        pickup: locationLabel(booking.pickup, ""),
                        dropoff: locationLabel(booking.destination, ""),
                      },
                    })
                  }
                  className={`px-4 py-2 rounded-xl font-bold text-xs flex items-center gap-1.5 transition-all duration-200 cursor-pointer ${
                    isCancelled
                      ? "bg-slate-100 text-slate-600 hover:bg-slate-200"
                      : "bg-[#006a62] hover:bg-[#00D1C1] text-white shadow-xs"
                  }`}
                >
                  <RotateCcw className="w-3.5 h-3.5" />
                  <span>Đặt lại chuyến này</span>
                </button>
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
};
