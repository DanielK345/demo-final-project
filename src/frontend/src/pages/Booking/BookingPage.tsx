import React, { useState, useEffect } from "react";
import { Clock3, Sparkles, Users, ArrowRight, MapPin } from "lucide-react";
import { MOCK_SERVICES_CATALOG } from "@/features/booking/mockData";
import { useVoiceAssistant } from "@/features/ai-assistant/context/useVoiceAssistant";
import { LocationAutocomplete, RideMap, calculateRoute } from "@/features/maps";
import type { LocationResult, RouteResult } from "@/features/maps";

const VEHICLE_LABEL: Record<"MOTORBIKE" | "CAR_4" | "CAR_7" | "LUXURY", string> = {
  MOTORBIKE: "xe máy",
  CAR_4: "ô tô 4 chỗ",
  CAR_7: "ô tô 7 chỗ",
  LUXURY: "xe cao cấp",
};

export const BookingPage: React.FC = () => {
  const { openWithPrefill } = useVoiceAssistant();

  const [pickup, setPickup] = useState<LocationResult | null>({
    id: "default_pickup",
    name: "Đại học Bách Khoa Hà Nội",
    display_name: "Đại học Bách Khoa Hà Nội, Hai Bà Trưng, Hà Nội",
    lat: 21.0074,
    lon: 105.8431,
  });

  const [destination, setDestination] = useState<LocationResult | null>(null);
  const [route, setRoute] = useState<RouteResult | null>(null);
  const [isCalculatingRoute, setIsCalculatingRoute] = useState(false);

  // Recalculate route whenever pickup or destination changes
  useEffect(() => {
    if (!pickup || !destination) {
      setRoute(null);
      return;
    }

    let active = true;
    setIsCalculatingRoute(true);

    calculateRoute({
      pickup: { lat: pickup.lat, lon: pickup.lon },
      destination: { lat: destination.lat, lon: destination.lon },
    })
      .then((res) => {
        if (!active) return;
        setRoute(res);
      })
      .catch((err) => {
        console.warn("Route calculation failed:", err);
      })
      .finally(() => {
        if (active) setIsCalculatingRoute(false);
      });

    return () => {
      active = false;
    };
  }, [pickup, destination]);

  const handleBookVehicle = (serviceId: "MOTORBIKE" | "CAR_4" | "CAR_7" | "LUXURY", serviceName: string) => {
    const pickupName = pickup?.name || pickup?.display_name || "vị trí hiện tại";
    const destName = destination?.name || destination?.display_name;

    if (destName) {
      openWithPrefill(
        `Tôi muốn đặt xe ${serviceName} loại ${VEHICLE_LABEL[serviceId]} đón tại ${pickupName} đến ${destName}.`
      );
    } else {
      openWithPrefill(`Tôi muốn đặt xe ${serviceName} loại ${VEHICLE_LABEL[serviceId]} đón tại ${pickupName}.`);
    }
  };

  return (
    <div className="mx-auto max-w-5xl space-y-8 pb-16">
      {/* Header */}
      <header className="pt-2">
        <p className="text-xs font-bold uppercase tracking-[.18em] text-[#008F88]">Chọn hành trình & dịch vụ</p>
        <h1 className="mt-1 text-3xl font-extrabold tracking-tight text-[#173132] dark:text-white">
          Bạn muốn đi đâu hôm nay?
        </h1>
        <p className="mt-2 text-sm text-slate-500 dark:text-slate-400">
          Tra cứu lộ trình chính xác qua bản đồ OpenStreetMap và đặt xe thông minh với AI.
        </p>
      </header>

      {/* Interactive Map & Search Section */}
      <section className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
        {/* Search Inputs Card */}
        <div className="lg:col-span-5 space-y-4 bg-white dark:bg-[#12161A] p-5 rounded-[24px] border border-slate-200/80 dark:border-white/10 shadow-sm">
          <div className="flex items-center gap-2 pb-2 border-b border-slate-100 dark:border-white/5">
            <MapPin className="w-5 h-5 text-[#00C9B7]" />
            <h2 className="text-base font-extrabold text-[#173132] dark:text-white">Điểm đón & Điểm đến</h2>
          </div>

          <LocationAutocomplete
            label="ĐIỂM ĐÓN"
            placeholder="Nhập địa điểm đón..."
            value={pickup?.name || pickup?.display_name || ""}
            iconType="pickup"
            onSelect={(loc) => setPickup(loc)}
          />

          <LocationAutocomplete
            label="ĐIỂM ĐẾN"
            placeholder="Nhập điểm đến của bạn..."
            value={destination?.name || destination?.display_name || ""}
            iconType="destination"
            onSelect={(loc) => setDestination(loc)}
          />

          {route && (
            <div className="mt-3 p-3.5 bg-[#EFFBFA] dark:bg-white/5 rounded-xl border border-[#00C9B7]/20 flex items-center justify-between text-xs">
              <div>
                <span className="text-slate-500 dark:text-slate-400 block text-[11px]">Khoảng cách đường đi</span>
                <span className="font-bold text-[#173132] dark:text-white text-sm">
                  {route.distance_km} km
                </span>
              </div>
              <div className="text-right">
                <span className="text-slate-500 dark:text-slate-400 block text-[11px]">Thời gian dự kiến</span>
                <span className="font-bold text-[#008F88] dark:text-[#00C9B7] text-sm">
                  ~{route.duration_minutes} phút
                </span>
              </div>
            </div>
          )}

          <button
            type="button"
            onClick={() => handleBookVehicle("CAR_4", "AloCar 4 chỗ")}
            className="w-full mt-2 py-3.5 px-4 rounded-xl bg-gradient-to-r from-[#00C9B7] to-[#008F88] text-white font-extrabold text-sm shadow-md shadow-[#00C9B7]/20 flex items-center justify-center gap-2 hover:opacity-95 transition-opacity"
          >
            <Sparkles className="w-4 h-4" />
            {isCalculatingRoute ? "Đang tính đường..." : "Gọi AI Đặt xe cho lộ trình này"}
            <ArrowRight className="w-4 h-4" />
          </button>
        </div>

        {/* Live Leaflet Map Preview */}
        <div className="lg:col-span-7 h-[360px] lg:h-[400px] rounded-[24px] overflow-hidden border border-slate-200/80 dark:border-white/10 shadow-sm relative">
          <RideMap
            pickup={pickup}
            destination={destination}
            route={route}
            className="w-full h-full"
          />
        </div>
      </section>

      {/* Services Catalog */}
      <section className="mobility-card overflow-hidden p-2 sm:p-3">
        <div className="px-4 pb-2 pt-4">
          <h2 className="text-xl font-extrabold text-[#173132] dark:text-white">Phương tiện gợi ý</h2>
          <p className="text-xs text-slate-400 mt-0.5">Chọn phương tiện để AI tự động đặt theo lộ trình trên</p>
        </div>
        <div className="space-y-2">
          {MOCK_SERVICES_CATALOG.map((service, index) => (
            <button
              key={service.id}
              type="button"
              onClick={() => handleBookVehicle(service.id, service.name)}
              className="group flex w-full items-center gap-4 rounded-[24px] p-3 text-left transition hover:bg-[#EFFBFA] dark:hover:bg-white/5 sm:p-4"
            >
              <span className="h-24 w-28 shrink-0 overflow-hidden rounded-[22px] bg-gradient-to-br from-cyan-50 to-teal-100">
                <img src={service.image} alt="" className="h-full w-full object-cover transition group-hover:scale-105" />
              </span>
              <span className="min-w-0 flex-1">
                <span className="flex items-start justify-between gap-3">
                  <strong className="text-lg font-extrabold text-[#173132] dark:text-white">{service.name}</strong>
                  <strong className="whitespace-nowrap text-base text-[#173132] dark:text-white">{service.startingPrice}</strong>
                </span>
                <span className="mt-1 flex flex-wrap gap-x-3 gap-y-1 text-xs font-medium text-slate-400">
                  <span className="flex items-center gap-1">
                    <Users className="h-3.5 w-3.5" /> {index === 2 ? "7" : index === 0 ? "1" : "4"} khách
                  </span>
                  <span className="flex items-center gap-1">
                    <Clock3 className="h-3.5 w-3.5" /> Đón trong {3 + index} phút
                  </span>
                </span>
                <span className="mt-2 block line-clamp-1 text-xs text-slate-500">{service.description}</span>
              </span>
            </button>
          ))}
        </div>
      </section>

      {/* Business Banner */}
      <section className="soft-cyan-panel rounded-[30px] p-6 sm:flex sm:items-center sm:justify-between">
        <div>
          <p className="text-xs font-bold text-[#008F88]">ALO SM BUSINESS</p>
          <h2 className="mt-2 text-2xl font-extrabold text-[#173132]">Di chuyển cho doanh nghiệp</h2>
          <p className="mt-2 max-w-xl text-sm text-slate-500">Quản lý chuyến đi minh bạch và linh hoạt cho cả đội ngũ.</p>
        </div>
        <button
          type="button"
          onClick={() => openWithPrefill("Tôi cần dịch vụ xe doanh nghiệp.")}
          className="mt-5 rounded-2xl bg-[#00C9B7] px-6 py-3 text-sm font-extrabold text-white shadow-lg shadow-[#00C9B7]/20 sm:mt-0"
        >
          Tìm hiểu ngay
        </button>
      </section>
    </div>
  );
};