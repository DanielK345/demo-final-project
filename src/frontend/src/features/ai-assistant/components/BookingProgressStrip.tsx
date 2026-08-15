import React from "react";
import { Car, Check, MapPin, Navigation } from "lucide-react";
import type { BookingProgress } from "@/features/ride/api";
import { vehicleLabel } from "@/features/ai-assistant/bookingLabels";

type Props = {
  progress: BookingProgress | null;
};

// Bản rút gọn của BookingProgressSidebar cũ (đã bỏ, không còn chỗ cho 1 cột dọc rộng
// trong popup hẹp) — 1 dải ngang nhỏ ngay trong khu chat, chỉ 3 chấm tiến trình
// pickup/destination/loại xe, bấm không được (chỉ hiển thị, agent tự cập nhật qua hội
// thoại — không có form chỉnh trực tiếp để tránh state lệch khỏi AgentState thật).
export const BookingProgressStrip: React.FC<Props> = ({ progress }) => {
  if (!progress || (!progress.pickup && !progress.destination && !progress.vehicle_type)) return null;

  const items = [
    { key: "pickup", icon: MapPin, label: progress.pickup?.label, active: progress.missing_field === "pickup" },
    {
      key: "destination",
      icon: Navigation,
      label: progress.destination?.label,
      active: progress.missing_field === "destination",
    },
    {
      key: "vehicle_type",
      icon: Car,
      label: progress.vehicle_type ? vehicleLabel(progress.vehicle_type) : undefined,
      active: progress.missing_field === "vehicle_type",
    },
  ];

  return (
    <div className="flex items-center gap-1.5 px-4 py-2 overflow-x-auto border-b border-slate-100 dark:border-white/10">
      {items.map(({ key, icon: Icon, label, active }) => (
        <span
          key={key}
          title={label}
          className={`shrink-0 inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-[11px] font-semibold max-w-[140px] ${
            label
              ? "bg-[#00D1C1]/10 text-[#006a62] dark:text-[#00D1C1]"
              : active
                ? "bg-amber-50 text-amber-700 dark:bg-amber-500/10 dark:text-amber-300"
                : "bg-slate-100 text-slate-400 dark:bg-white/5 dark:text-slate-500"
          }`}
        >
          {label ? <Check className="w-3 h-3 shrink-0" /> : <Icon className="w-3 h-3 shrink-0" />}
          <span className="truncate">{label ?? (active ? "Đang chờ…" : "Chưa có")}</span>
        </span>
      ))}
    </div>
  );
};
