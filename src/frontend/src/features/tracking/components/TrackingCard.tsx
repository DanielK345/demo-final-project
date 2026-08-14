import React from "react";
import { Phone, ShieldCheck } from "lucide-react";
import type { TrackingTripDetails } from "../types";

interface TrackingCardProps {
  trip: TrackingTripDetails;
}

export const TrackingCard: React.FC<TrackingCardProps> = ({ trip }) => {
  return (
    <div className="bg-white rounded-[24px] p-6 shadow-[0_8px_30px_rgba(0,106,98,0.1)] border border-slate-200/80 space-y-6 dark:bg-[#12161A] dark:border-white/10">
      {/* Status Header */}
      <div className="flex items-center justify-between">
        <div>
          <span className="text-[10px] font-bold text-slate-400 dark:text-slate-500 uppercase tracking-widest block">
            TRẠNG THÁI HÀNH TRÌNH
          </span>
          <h2 className="text-xl font-bold text-[#191C1E] dark:text-white">{trip.statusText}</h2>
        </div>
        <span className="bg-[#00D1C1]/15 text-[#006a62] dark:text-[#00D1C1] px-3 py-1 rounded-full text-xs font-bold border border-[#00D1C1]/30">
          ETA: {trip.eta}
        </span>
      </div>

      {/* Driver Information */}
      {trip.driver && (
        <div className="p-4 rounded-2xl bg-slate-50 border border-slate-200 flex items-center justify-between dark:bg-white/5 dark:border-white/10">
          <div className="flex items-center gap-3">
            <img
              src={trip.driver.avatar}
              alt={trip.driver.name}
              className="w-12 h-12 rounded-full object-cover border-2 border-[#00D1C1]"
            />
            <div>
              <h3 className="text-sm font-bold text-[#191C1E] dark:text-white">{trip.driver.name}</h3>
              <p className="text-xs text-slate-500 dark:text-slate-400">
                {trip.driver.vehicleName} • <span className="font-mono text-[#006a62] dark:text-[#00D1C1] font-bold">{trip.driver.licensePlate}</span>
              </p>
            </div>
          </div>

          <a
            href={`tel:${trip.driver.phone}`}
            className="w-10 h-10 rounded-full bg-[#006a62] text-white flex items-center justify-center hover:bg-[#00D1C1] transition-colors"
          >
            <Phone className="w-5 h-5" />
          </a>
        </div>
      )}

      {/* Route Timeline */}
      <div className="space-y-3 relative pl-6">
        <div className="absolute left-[9px] top-2 bottom-2 w-0.5 bg-slate-200 dark:bg-white/10 z-0" />

        <div className="relative z-10 text-xs">
          <div className="absolute -left-[23px] top-0.5 w-3 h-3 rounded-full border-2 border-[#00D1C1] bg-white dark:bg-[#12161A]" />
          <span className="text-[10px] font-bold text-slate-400 dark:text-slate-500 uppercase tracking-wider block">
            ĐIỂM ĐÓN
          </span>
          <p className="font-bold text-[#191C1E] dark:text-white">{trip.pickup}</p>
        </div>

        <div className="relative z-10 text-xs pt-2">
          <div className="absolute -left-[23px] top-2.5 w-3 h-3 rounded-full bg-[#006a62] dark:bg-[#00D1C1]" />
          <span className="text-[10px] font-bold text-slate-400 dark:text-slate-500 uppercase tracking-wider block">
            ĐIỂM ĐẾN
          </span>
          <p className="font-bold text-[#191C1E] dark:text-white">{trip.destination}</p>
        </div>
      </div>

      {/* Security badge */}
      <div className="pt-2 flex items-center justify-between text-xs text-slate-500 dark:text-slate-400 border-t border-slate-100 dark:border-white/10">
        <div className="flex items-center gap-1.5 text-[#006a62] dark:text-[#00D1C1] font-semibold">
          <ShieldCheck className="w-4 h-4 text-[#00D1C1]" />
          <span>Bảo hiểm chuyến đi đang kích hoạt</span>
        </div>
        <span className="font-mono text-[10px] text-slate-400 dark:text-slate-500">ID: {trip.bookingId}</span>
      </div>
    </div>
  );
};
