import React from "react";
import { MapPin, Navigation, ArrowDownUp } from "lucide-react";
import { Input } from "@/components/ui/Input";

export interface LocationPickerProps {
  pickup: string;
  destination: string;
  onPickupChange: (val: string) => void;
  onDestinationChange: (val: string) => void;
  onSwap?: () => void;
}

export const LocationPicker: React.FC<LocationPickerProps> = ({
  pickup,
  destination,
  onPickupChange,
  onDestinationChange,
  onSwap,
}) => {
  return (
    <div className="relative flex flex-col gap-3 p-4 rounded-2xl bg-slate-900/90 border border-slate-800">
      {/* Pickup Input */}
      <div className="relative">
        <Input
          label="Điểm đón"
          placeholder="Nhập địa chỉ điểm đón của bạn..."
          value={pickup}
          onChange={(e) => onPickupChange(e.target.value)}
          leftIcon={<Navigation className="w-4 h-4 text-emerald-400" />}
        />
      </div>

      {/* Connector Line & Swap Button */}
      <div className="relative flex items-center justify-center my-0.5">
        <div className="absolute inset-0 flex items-center">
          <div className="w-full border-t border-dashed border-slate-800" />
        </div>
        {onSwap && (
          <button
            type="button"
            onClick={onSwap}
            aria-label="Đổi điểm đón và điểm đến"
            className="relative z-10 p-1.5 rounded-full bg-slate-800 hover:bg-slate-700 text-slate-300 hover:text-emerald-400 border border-slate-700 transition-all shadow-md active:scale-95"
          >
            <ArrowDownUp className="w-3.5 h-3.5" />
          </button>
        )}
      </div>

      {/* Destination Input */}
      <div className="relative">
        <Input
          label="Điểm đến"
          placeholder="Bạn muốn đi đâu?"
          value={destination}
          onChange={(e) => onDestinationChange(e.target.value)}
          leftIcon={<MapPin className="w-4 h-4 text-rose-400" />}
        />
      </div>
    </div>
  );
};
