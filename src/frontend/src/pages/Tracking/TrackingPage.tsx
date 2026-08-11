import React from "react";
import { TrackingCard } from "@/features/tracking/components/TrackingCard";
import type { TrackingTripDetails } from "@/features/tracking/types";
import { Navigation, AlertCircle } from "lucide-react";

export const TrackingPage: React.FC = () => {
  const currentTrip: TrackingTripDetails = {
    bookingId: "BK-882910",
    status: "arriving",
    statusText: "Tài xế đang di chuyển tới điểm đón",
    pickup: "123 Tech Start Blvd, D1",
    destination: "Airport Terminal 2",
    eta: "4 phút",
    driver: {
      name: "Nguyễn Văn A",
      avatar:
        "https://images.unsplash.com/photo-1534528741775-53994a69daeb?w=150&auto=format&fit=crop&q=80",
      vehicleName: "AloSM Plus (VinFast VF8)",
      licensePlate: "29A-888.88",
      rating: 4.9,
      phone: "0901234567",
    },
  };

  const mapBgUrl =
    "https://lh3.googleusercontent.com/aida-public/AB6AXuA9-JzFmj0AFqu7hGXvp5QIBGayZ8Rrag3Fm12h_x1kQKe_pXhdufywgmE5vI7IJqsWE86ZRyMAWaR8aBdxLx2GfX3QSadKDT6ry12dxcTw6bXLeLOa58DPFA9ktZeMIYIdpfRWPLjyPZsk_E0epFY73vGCx1dVFQgGYEC_yxnaFJK8XvffhhUJK7merVrPneWWBdLgXEpWwj0kum89ioxKPu_uRO-Fzy9oa1xSexiY1zO8IJhvmSrI";

  return (
    <div className="space-y-6 pb-12">
      {/* Disclaimer Banner */}
      <div className="p-3.5 rounded-xl bg-amber-50 border border-amber-200 text-amber-800 text-xs flex items-center gap-2">
        <AlertCircle className="w-4 h-4 text-amber-600 shrink-0" />
        <span>
          <strong>TRACKING UI:</strong> Giao diện theo dõi hành trình trực tiếp. Đang chờ tích hợp GPS / WebSocket Backend API.
        </span>
      </div>

      {/* Page Title */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-extrabold text-[#191C1E] tracking-tight">
            Theo dõi chuyến đi
          </h1>
          <p className="text-sm text-slate-500 mt-0.5">
            Cập nhật vị trí tài xế và hành trình di chuyển trực tiếp
          </p>
        </div>

        <div className="flex items-center gap-2 bg-[#00D1C1]/10 text-[#006a62] px-3.5 py-1.5 rounded-full border border-[#00D1C1]/30 text-xs font-semibold">
          <Navigation className="w-4 h-4 text-[#00D1C1] animate-spin-slow" />
          <span>GPS Live Streaming</span>
        </div>
      </div>

      {/* Main Grid: Left Map View & Right Details */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-start">
        {/* Left Column: Simulated Map Display */}
        <div className="lg:col-span-7 h-[460px] rounded-[24px] overflow-hidden relative border border-slate-200 shadow-md">
          <div
            className="w-full h-full bg-cover bg-center"
            style={{ backgroundImage: `url(${mapBgUrl})` }}
          />

          {/* Overlay gradient */}
          <div className="absolute inset-0 bg-gradient-to-t from-slate-900/40 via-transparent to-transparent pointer-events-none" />

          {/* Marker Pickup */}
          <div className="absolute top-1/2 left-1/3 -translate-x-1/2 -translate-y-1/2 flex flex-col items-center">
            <div className="px-2.5 py-1 bg-[#191C1E] text-white text-[10px] font-bold rounded-lg shadow-md mb-1">
              Điểm đón
            </div>
            <div className="w-4 h-4 bg-[#00D1C1] rounded-full border-2 border-white shadow-lg animate-ping" />
          </div>

          {/* Marker Driver Car */}
          <div className="absolute top-1/3 left-1/2 -translate-x-1/2 -translate-y-1/2 flex flex-col items-center">
            <div className="px-2.5 py-1 bg-[#006a62] text-white text-[10px] font-bold rounded-lg shadow-md mb-1 flex items-center gap-1">
              <span>Tài xế (4 phút)</span>
            </div>
            <div className="w-8 h-8 rounded-full bg-white shadow-xl flex items-center justify-center text-[#006a62] border-2 border-[#00D1C1]">
              <Navigation className="w-4 h-4 transform rotate-45" />
            </div>
          </div>
        </div>

        {/* Right Column: Tracking Detail Card */}
        <div className="lg:col-span-5 space-y-6">
          <TrackingCard trip={currentTrip} />
        </div>
      </div>
    </div>
  );
};
