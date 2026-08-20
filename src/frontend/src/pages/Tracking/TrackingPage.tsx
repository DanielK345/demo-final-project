import React, { useEffect, useState, useMemo } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { TrackingCard } from "@/features/tracking/components/TrackingCard";
import type { TrackingTripDetails } from "@/features/tracking/types";
import { getTripStatus, TRIP_STATUS_TEXT, type TripStatusResponse } from "@/features/tracking/api";
import { redirectToLoginIfUnauthorized } from "@/features/auth/sessionGuard";
import { useVoiceAssistant } from "@/features/ai-assistant/context/useVoiceAssistant";
import { Navigation, AlertCircle, Sparkles } from "lucide-react";
import { RideMap } from "@/features/maps/components/RideMap";
import { resolveTrip } from "@/features/maps/api";
import type { LocationResult, RouteResult } from "@/features/maps/types";

const POLL_INTERVAL_MS = 4000;

const STATUS_MAP: Record<TripStatusResponse["status"], TrackingTripDetails["status"]> = {
  SEARCHING_DRIVER: "searching",
  DRIVER_ASSIGNED: "accepted",
  ARRIVING: "arriving",
  ON_TRIP: "in_transit",
  COMPLETED: "completed",
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
  const [pickupLoc, setPickupLoc] = useState<LocationResult | null>(null);
  const [destLoc, setDestLoc] = useState<LocationResult | null>(null);
  const [routeData, setRouteData] = useState<RouteResult | null>(null);

  // Resolve trip route coordinates from pickup and destination
  useEffect(() => {
    const pickupQuery = routeState?.pickup || "Đại học Bách Khoa Hà Nội";
    const destQuery = routeState?.destination || "Hồ Hoàn Kiếm, Hà Nội";

    let active = true;
    resolveTrip({
      pickup: pickupQuery,
      destination: destQuery,
      sessionId: routeState?.sessionId,
    })
      .then((res) => {
        if (!active) return;
        setPickupLoc(res.pickup);
        setDestLoc(res.destination);
        setRouteData(res.route);
      })
      .catch((err) => {
        console.warn("Map resolve trip fallback:", err);
        if (!active) return;
        // Graceful fallback to default Hanoi central points
        setPickupLoc({
          id: "p_hust",
          name: pickupQuery,
          display_name: pickupQuery,
          lat: 21.0074,
          lon: 105.8431,
        });
        setDestLoc({
          id: "p_sword",
          name: destQuery,
          display_name: destQuery,
          lat: 21.0285,
          lon: 105.8542,
        });
      });

    return () => {
      active = false;
    };
  }, [routeState?.pickup, routeState?.destination, routeState?.sessionId]);

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

  // Compute live driver coordinates along the route geometry based on trip status
  const driverLiveLocation = useMemo(() => {
    if (!trip?.driver) return null;
    const coords = routeData?.geometry?.coordinates;
    if (!coords || coords.length === 0) {
      if (pickupLoc) {
        return { lat: pickupLoc.lat - 0.002, lon: pickupLoc.lon - 0.002, heading: 45 };
      }
      return null;
    }

    if (trip.status === "searching") return null;
    if (trip.status === "accepted") {
      const [lon, lat] = coords[0];
      return { lat: lat - 0.003, lon: lon - 0.002, heading: 30 };
    }
    if (trip.status === "arriving") {
      const [lon, lat] = coords[0];
      return { lat, lon, heading: 90 };
    }
    if (trip.status === "in_transit") {
      const midIdx = Math.floor(coords.length / 2);
      const [lon, lat] = coords[midIdx];
      return { lat, lon, heading: 60 };
    }
    if (trip.status === "completed") {
      const [lon, lat] = coords[coords.length - 1];
      return { lat, lon, heading: 0 };
    }
    return null;
  }, [trip?.driver, trip?.status, routeData?.geometry?.coordinates, pickupLoc]);

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
          className="mt-2 inline-flex items-center gap-2 px-6 py-3 rounded-xl bg-[#00C9B7] text-white font-bold text-sm hover:bg-[#008F88] transition-colors"
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
            Cập nhật vị trí tài xế và hành trình di chuyển trực tiếp trên bản đồ OpenStreetMap
          </p>
        </div>

        <div className="flex items-center gap-2 bg-[#00C9B7]/10 text-[#008F88] dark:text-[#00C9B7] px-3.5 py-1.5 rounded-full border border-[#00C9B7]/30 text-xs font-semibold">
          <Navigation className="w-4 h-4 text-[#00C9B7] animate-spin-slow" />
          <span>Cập nhật mỗi {POLL_INTERVAL_MS / 1000}s</span>
        </div>
      </div>

      {/* Main Grid: Left Map View & Right Details */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-start">
        {/* Left Column: Interactive OpenStreetMap with Leaflet */}
        <div className="lg:col-span-7 h-[460px] rounded-[24px] overflow-hidden relative border border-slate-200 dark:border-white/10 shadow-md">
          <RideMap
            pickup={pickupLoc}
            destination={destLoc}
            driverLocation={driverLiveLocation}
            route={routeData}
            className="w-full h-full"
          />
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
