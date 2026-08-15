import React, { useEffect, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { TrackingCard } from "@/features/tracking/components/TrackingCard";
import type { TrackingTripDetails } from "@/features/tracking/types";
import { getTripStatus, TRIP_STATUS_TEXT, type TripStatusResponse } from "@/features/tracking/api";
import { redirectToLoginIfUnauthorized } from "@/features/auth/sessionGuard";
import { useVoiceAssistant } from "@/features/ai-assistant/context/useVoiceAssistant";
import { Navigation, AlertCircle, Sparkles } from "lucide-react";

const POLL_INTERVAL_MS = 4000;

const STATUS_MAP: Record<TripStatusResponse["status"], TrackingTripDetails["status"]> = {
  SEARCHING_DRIVER: "searching",
  DRIVER_ASSIGNED: "accepted",
  ARRIVING: "arriving",
  ON_TRIP: "in_transit",
  COMPLETED: "completed",
};

// Toạ độ % thuần minh hoạ trên ảnh nền tĩnh — KHÔNG phải GPS thật (chưa có Maps
// provider, xem mustdo.md mục 3). Trước đây marker tài xế đứng yên 1 chỗ cố định bất
// kể trạng thái/ETA thật đổi thế nào; giờ marker DI CHUYỂN thật theo đúng trạng thái
// thật trả về từ TripService mỗi lần poll (mô phỏng nâng cao — không cần API key).
const PICKUP_POINT = { left: 30, top: 55 };
const DESTINATION_POINT = { left: 76, top: 22 };
const DRIVER_WAYPOINT: Record<TrackingTripDetails["status"], { left: number; top: number } | null> = {
  searching: null,
  accepted: { left: 88, top: 82 },
  arriving: { left: 44, top: 64 },
  in_transit: { left: 54, top: 40 },
  completed: DESTINATION_POINT,
};

export const TrackingPage: React.FC = () => {
  const location = useLocation();
  const navigate = useNavigate();
  const { open: openAssistant } = useVoiceAssistant();
  const routeState = location.state as
    | { sessionId?: string; bookingId?: string; pickup?: string; destination?: string }
    | undefined;

  const [trip, setTrip] = useState<TrackingTripDetails | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  useEffect(() => {
    if (!routeState?.sessionId || !routeState?.bookingId) return;
    let cancelled = false;

    const poll = async () => {
      try {
        const status = await getTripStatus(routeState.sessionId!);
        if (cancelled) return;
        setTrip({
          bookingId: routeState.bookingId!,
          status: STATUS_MAP[status.status],
          statusText: TRIP_STATUS_TEXT[status.status],
          pickup: routeState.pickup || "Điểm đón",
          destination: routeState.destination || "Điểm đến",
          eta: status.eta_minutes != null ? `${status.eta_minutes} phút` : "--",
          driver:
            status.driver_name != null
              ? {
                  name: status.driver_name,
                  avatar:
                    "https://images.unsplash.com/photo-1534528741775-53994a69daeb?w=150&auto=format&fit=crop&q=80",
                  vehicleName: status.vehicle || "",
                  licensePlate: status.license_plate || "",
                  rating: status.driver_rating ?? 4.8,
                  phone: status.driver_phone || "",
                }
              : undefined,
        });
      } catch (error) {
        if (cancelled) return;
        if (redirectToLoginIfUnauthorized(error, navigate)) return;
        setNotice(error instanceof Error ? error.message : "Không thể tải trạng thái chuyến đi.");
      }
    };

    poll();
    const interval = window.setInterval(poll, POLL_INTERVAL_MS);
    return () => {
      cancelled = true;
      window.clearInterval(interval);
    };
  }, [routeState?.sessionId, routeState?.bookingId, routeState?.pickup, routeState?.destination, navigate]);

  const mapBgUrl =
    "https://lh3.googleusercontent.com/aida-public/AB6AXuA9-JzFmj0AFqu7hGXvp5QIBGayZ8Rrag3Fm12h_x1kQKe_pXhdufywgmE5vI7IJqsWE86ZRyMAWaR8aBdxLx2GfX3QSadKDT6ry12dxcTw6bXLeLOa58DPFA9ktZeMIYIdpfRWPLjyPZsk_E0epFY73vGCx1dVFQgGYEC_yxnaFJK8XvffhhUJK7merVrPneWWBdLgXEpWwj0kum89ioxKPu_uRO-Fzy9oa1xSexiY1zO8IJhvmSrI";

  if (!routeState?.sessionId || !routeState?.bookingId) {
    return (
      <div className="max-w-2xl mx-auto py-16 text-center space-y-4">
        <AlertCircle className="w-10 h-10 text-slate-300 dark:text-slate-600 mx-auto" />
        <h1 className="text-xl font-bold text-[#191C1E] dark:text-white">Chưa có chuyến đi nào đang theo dõi</h1>
        <p className="text-sm text-slate-500 dark:text-slate-400">
          Nhờ AI Assistant đặt xe để bắt đầu theo dõi hành trình trực tiếp tại đây.
        </p>
        <button
          type="button"
          onClick={openAssistant}
          className="mt-2 inline-flex items-center gap-2 px-6 py-3 rounded-xl bg-[#00D1C1] text-white font-bold text-sm hover:bg-[#006a62] transition-colors"
        >
          <Sparkles className="w-4 h-4" />
          AI đặt xe ngay
        </button>
      </div>
    );
  }

  return (
    <div className="space-y-6 pb-12">
      {notice && (
        <div className="p-3.5 rounded-xl bg-amber-50 border border-amber-200 text-amber-800 text-xs flex items-center gap-2 dark:bg-amber-500/10 dark:border-amber-500/30 dark:text-amber-300">
          <AlertCircle className="w-4 h-4 text-amber-600 dark:text-amber-400 shrink-0" />
          <span>{notice}</span>
        </div>
      )}

      {/* Page Title */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-extrabold text-[#191C1E] dark:text-white tracking-tight">
            Theo dõi chuyến đi
          </h1>
          <p className="text-sm text-slate-500 dark:text-slate-400 mt-0.5">
            Cập nhật vị trí tài xế và hành trình di chuyển trực tiếp
          </p>
        </div>

        <div className="flex items-center gap-2 bg-[#00D1C1]/10 text-[#006a62] dark:text-[#00D1C1] px-3.5 py-1.5 rounded-full border border-[#00D1C1]/30 text-xs font-semibold">
          <Navigation className="w-4 h-4 text-[#00D1C1] animate-spin-slow" />
          <span>Cập nhật mỗi {POLL_INTERVAL_MS / 1000}s</span>
        </div>
      </div>

      {/* Main Grid: Left Map View & Right Details */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-start">
        {/* Left Column: Simulated Map Display */}
        <div className="lg:col-span-7 h-[460px] rounded-[24px] overflow-hidden relative border border-slate-200 dark:border-white/10 shadow-md">
          <div
            className="w-full h-full bg-cover bg-center"
            style={{ backgroundImage: `url(${mapBgUrl})` }}
          />
          <div className="absolute inset-0 bg-gradient-to-t from-slate-900/40 via-transparent to-transparent pointer-events-none" />
          <div
            className="absolute -translate-x-1/2 -translate-y-1/2 flex flex-col items-center"
            style={{ left: `${PICKUP_POINT.left}%`, top: `${PICKUP_POINT.top}%` }}
          >
            <div className="px-2.5 py-1 bg-[#191C1E] text-white text-[10px] font-bold rounded-lg shadow-md mb-1">
              Điểm đón
            </div>
            <div className="w-4 h-4 bg-[#00D1C1] rounded-full border-2 border-white shadow-lg animate-ping" />
          </div>
          <div
            className="absolute -translate-x-1/2 -translate-y-1/2 flex flex-col items-center"
            style={{ left: `${DESTINATION_POINT.left}%`, top: `${DESTINATION_POINT.top}%` }}
          >
            <div className="px-2.5 py-1 bg-[#006a62] text-white text-[10px] font-bold rounded-lg shadow-md mb-1">
              Điểm đến
            </div>
            <div className="w-4 h-4 bg-white rounded-full border-2 border-[#006a62] shadow-lg" />
          </div>
          {trip?.driver &&
            (() => {
              const point = DRIVER_WAYPOINT[trip.status];
              if (!point) return null;
              return (
                <div
                  className="absolute -translate-x-1/2 -translate-y-1/2 flex flex-col items-center transition-[left,top] duration-[1400ms] ease-in-out"
                  style={{ left: `${point.left}%`, top: `${point.top}%` }}
                >
                  <div className="px-2.5 py-1 bg-[#006a62] text-white text-[10px] font-bold rounded-lg shadow-md mb-1 flex items-center gap-1">
                    <span>Tài xế ({trip.eta})</span>
                  </div>
                  <div className="w-8 h-8 rounded-full bg-white shadow-xl flex items-center justify-center text-[#006a62] border-2 border-[#00D1C1]">
                    <Navigation className="w-4 h-4 transform rotate-45" />
                  </div>
                </div>
              );
            })()}
        </div>

        {/* Right Column: Tracking Detail Card */}
        <div className="lg:col-span-5 space-y-6">
          {trip ? (
            <TrackingCard trip={trip} />
          ) : (
            <div className="bg-white rounded-[24px] p-6 border border-slate-200/80 text-sm text-slate-500 dark:bg-[#12161A] dark:border-white/10 dark:text-slate-400">
              Đang tải trạng thái chuyến đi...
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
