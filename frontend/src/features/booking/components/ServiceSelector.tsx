import React from "react";
import { Bike, Car, Crown, PackageCheck } from "lucide-react";
import { cn } from "@/utils/cn";
import type { VehicleType, ServiceOption } from "../types";

export const SERVICE_OPTIONS: ServiceOption[] = [
  {
    id: "bike",
    name: "AloSM Bike",
    description: "Xe máy điện công nghệ cao, di chuyển linh hoạt",
    basePrice: 15000,
    eta: "2 - 4 phút",
    iconName: "bike",
    popular: true,
  },
  {
    id: "car",
    name: "AloSM Car",
    description: "Xe 4 chỗ êm ái, thích hợp di chuyển nhóm hoặc gia đình",
    basePrice: 35000,
    eta: "3 - 5 phút",
    iconName: "car",
  },
  {
    id: "premium",
    name: "AloSM Luxury",
    description: "Xe sang trọng, tài xế chuyên nghiệp 5 sao",
    basePrice: 70000,
    eta: "5 - 8 phút",
    iconName: "premium",
  },
  {
    id: "delivery",
    name: "AloSM Express",
    description: "Giao hàng siêu tốc nội thành trong 30 phút",
    basePrice: 20000,
    eta: "Lấy ngay",
    iconName: "delivery",
  },
];

const iconMap = {
  bike: Bike,
  car: Car,
  premium: Crown,
  delivery: PackageCheck,
};

export interface ServiceSelectorProps {
  selected: VehicleType;
  onSelect: (type: VehicleType) => void;
}

export const ServiceSelector: React.FC<ServiceSelectorProps> = ({ selected, onSelect }) => {
  return (
    <div className="flex flex-col gap-2.5">
      <label className="text-xs font-semibold text-slate-300">Chọn dịch vụ AloSM</label>
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        {SERVICE_OPTIONS.map((opt) => {
          const Icon = iconMap[opt.id];
          const isSelected = selected === opt.id;
          return (
            <div
              key={opt.id}
              onClick={() => onSelect(opt.id)}
              className={cn(
                "p-4 rounded-2xl border transition-all duration-200 cursor-pointer relative overflow-hidden flex flex-col justify-between gap-3",
                isSelected
                  ? "bg-emerald-500/10 border-emerald-500 text-slate-100 shadow-lg shadow-emerald-500/10"
                  : "bg-slate-900/80 border-slate-800 text-slate-400 hover:border-slate-700 hover:text-slate-200"
              )}
            >
              {opt.popular && (
                <span className="absolute top-0 right-0 bg-emerald-500 text-slate-950 text-[9px] font-bold px-2 py-0.5 rounded-bl-lg uppercase tracking-wider">
                  Phổ biến
                </span>
              )}
              <div className="flex items-start justify-between">
                <div className="p-2.5 rounded-xl bg-slate-800/80 text-emerald-400">
                  <Icon className="w-6 h-6" />
                </div>
                <div className="text-right">
                  <span className="text-sm font-bold text-slate-100">
                    {opt.basePrice.toLocaleString("vi-VN")} đ
                  </span>
                  <span className="block text-[10px] text-slate-500">Dự kiến</span>
                </div>
              </div>

              <div>
                <h4 className="text-sm font-bold text-slate-200 mb-0.5">{opt.name}</h4>
                <p className="text-xs text-slate-400 line-clamp-2">{opt.description}</p>
              </div>

              <div className="flex items-center justify-between pt-2 border-t border-slate-800/60 text-[11px] text-slate-400">
                <span>Đón khoảng:</span>
                <span className="font-semibold text-emerald-400">{opt.eta}</span>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};
