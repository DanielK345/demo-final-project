import React from "react";
import { Clock, ChevronRight, RotateCcw } from "lucide-react";
import { MOCK_TRIP_HISTORY } from "../mockData";

interface ActivityListProps {
  activeFilter?: string;
}

export const ActivityList: React.FC<ActivityListProps> = ({ activeFilter = "all" }) => {
  const filteredTrips = MOCK_TRIP_HISTORY.filter((trip) => {
    if (activeFilter === "cancelled") return trip.status === "cancelled";
    if (activeFilter === "recent") return trip.status === "completed";
    return true;
  });

  return (
    <div className="space-y-4">
      {filteredTrips.map((item) => {
        const isCancelled = item.status === "cancelled";
        return (
          <div
            key={item.id}
            className="bg-white rounded-[24px] p-5 shadow-[0_4px_20px_rgba(16,18,19,0.05)] border border-slate-200/80 hover:shadow-md transition-shadow duration-200 flex flex-col md:flex-row gap-5 items-stretch overflow-hidden"
          >
            {/* Map Preview Thumbnail */}
            <div className="w-full md:w-44 h-36 md:h-auto rounded-xl overflow-hidden bg-slate-100 shrink-0 relative border border-slate-200/60">
              <img
                src={item.mapImage}
                alt="Bản đồ lộ trình"
                className={`w-full h-full object-cover ${isCancelled ? "grayscale opacity-75" : ""}`}
              />
              <div className="absolute top-2 left-2">
                <span
                  className={`px-2.5 py-1 rounded-full text-[10px] font-bold uppercase tracking-wider ${
                    isCancelled
                      ? "bg-rose-100 text-rose-700 border border-rose-200"
                      : "bg-[#00D1C1]/20 text-[#006a62] border border-[#00D1C1]/30"
                  }`}
                >
                  {item.statusText}
                </span>
              </div>
            </div>

            {/* Trip Information & Route Details */}
            <div className="flex-1 flex flex-col justify-between space-y-4 py-0.5">
              <div className="space-y-3">
                {/* Header Date & Time */}
                <div className="flex items-center justify-between text-xs text-slate-500 font-medium">
                  <div className="flex items-center gap-1.5">
                    <Clock className="w-3.5 h-3.5 text-slate-400" />
                    <span>{item.time}</span>
                  </div>
                  <ChevronRight className="w-4 h-4 text-slate-400" />
                </div>

                {/* Pickup & Destination Route Timeline */}
                <div className="space-y-2 relative pl-5">
                  {/* Timeline connecting line */}
                  <div className="absolute left-[5px] top-2 bottom-2 w-0.5 bg-slate-200 z-0" />

                  {/* Pickup */}
                  <div className="relative z-10 text-xs">
                    <div className="absolute -left-[19px] top-1 w-2.5 h-2.5 rounded-full border-2 border-[#00D1C1] bg-white" />
                    <p className="font-semibold text-[#191C1E] line-clamp-1">{item.pickup}</p>
                  </div>

                  {/* Destination */}
                  <div className="relative z-10 text-xs pt-1">
                    <div className="absolute -left-[19px] top-2 w-2.5 h-2.5 rounded-full bg-[#006a62]" />
                    <p className="font-semibold text-[#191C1E] line-clamp-1">{item.destination}</p>
                  </div>
                </div>
              </div>

              {/* Price & Rebooking CTA */}
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
                    {item.price}
                  </span>
                </div>

                <button
                  type="button"
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
