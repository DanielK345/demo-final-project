import React from "react";
import { Car, Clock3, MapPin, Navigation } from "lucide-react";
import type { BookingLifecycleStatus } from "@/features/ride/api";

export type BookingFieldProgress = {
  label: string;
  resolved: boolean;
  place_id?: string | null;
};

export type BookingProgress = {
  pickup?: BookingFieldProgress | null;
  destination?: BookingFieldProgress | null;
  vehicle_type?: string | null;
  missing_field?: "pickup" | "destination" | "vehicle_type" | null;
  lifecycle_status?: BookingLifecycleStatus | null;
};

const LIFECYCLE_LABELS: Record<BookingLifecycleStatus, string> = {
  PENDING: "Đang xử lý",
  SUCCESS: "Thành công",
  FAILED: "Thất bại",
};

const LIFECYCLE_STYLES: Record<BookingLifecycleStatus, string> = {
  PENDING: "bg-amber-100 text-amber-800 border-amber-200",
  SUCCESS: "bg-emerald-100 text-emerald-800 border-emerald-200",
  FAILED: "bg-rose-100 text-rose-800 border-rose-200",
};

const VEHICLE_LABELS: Record<string, string> = {
  "4_SEAT": "4 chỗ",
  "7_SEAT": "7 chỗ",
  PREMIUM: "Hạng sang",
};

const FIELD_LABELS: Record<string, string> = {
  pickup: "Điểm đón",
  destination: "Điểm đến",
  vehicle_type: "Loại xe",
};

type Props = {
  progress: BookingProgress | null;
  lifecycleStatus?: BookingLifecycleStatus | null;
  isProcessing?: boolean;
};

function fieldStatus(
  key: "pickup" | "destination" | "vehicle_type",
  progress: BookingProgress,
): { value: string; pending: boolean; active: boolean } {
  if (key === "vehicle_type") {
    const value = progress.vehicle_type
      ? VEHICLE_LABELS[progress.vehicle_type] ?? progress.vehicle_type
      : "Chưa chọn";
    return {
      value,
      pending: !progress.vehicle_type,
      active: progress.missing_field === "vehicle_type",
    };
  }

  const field = progress[key];
  return {
    value: field?.label ?? "Chưa có",
    pending: !field,
    active: progress.missing_field === key,
  };
}

export const BookingProgressSidebar: React.FC<Props> = ({
  progress,
  lifecycleStatus,
  isProcessing = false,
}) => {
  const status = lifecycleStatus ?? progress?.lifecycle_status ?? (isProcessing ? "PENDING" : null);
  const items = [
    { key: "pickup" as const, icon: MapPin },
    { key: "destination" as const, icon: Navigation },
    { key: "vehicle_type" as const, icon: Car },
  ];

  return (
    <aside className="w-full lg:w-72 shrink-0">
      <div className="bg-white border border-slate-200 rounded-2xl shadow-sm p-5 sticky top-6">
        <h2 className="text-sm font-bold text-slate-800 uppercase tracking-wide">
          Thông tin đặt xe
        </h2>
        <p className="text-xs text-slate-500 mt-1">
          Agent chỉ hỏi thông tin còn thiếu.
        </p>
        {status && (
          <div
            className={`mt-3 inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-xs font-semibold ${LIFECYCLE_STYLES[status]}`}
          >
            {status === "PENDING" && <Clock3 className="w-3.5 h-3.5" />}
            {LIFECYCLE_LABELS[status]}
          </div>
        )}
        <ul className="mt-4 space-y-3">
          {items.map(({ key, icon: Icon }) => {
            const status = progress
              ? fieldStatus(key, progress)
              : { value: "Chưa có", pending: true, active: key === "pickup" };
            return (
              <li
                key={key}
                className={`rounded-xl border p-3 transition ${
                  status.active
                    ? "border-[#00D1C1] bg-[#00D1C1]/5"
                    : "border-slate-100 bg-slate-50"
                }`}
              >
                <div className="flex items-center gap-2 text-xs font-semibold text-slate-500">
                  <Icon className="w-3.5 h-3.5" />
                  {FIELD_LABELS[key]}
                </div>
                <p
                  className={`mt-1 text-sm font-medium ${
                    status.pending ? "text-slate-400 italic" : "text-slate-800"
                  }`}
                >
                  {status.value}
                </p>
                {status.active && (
                  <p className="mt-1 text-[11px] font-semibold text-[#006a62]">
                    Đang chờ thông tin này
                  </p>
                )}
              </li>
            );
          })}
        </ul>
      </div>
    </aside>
  );
};
