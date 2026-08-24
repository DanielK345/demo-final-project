import React from "react";
import { Car, MapPin, Navigation, Pencil, Wallet } from "lucide-react";
import { useVoiceAssistant } from "@/features/ai-assistant/context/useVoiceAssistant";
import { formatFare, vehicleLabel } from "@/features/ai-assistant/bookingLabels";

// Mục 7-9: khi agent đã thu thập đủ thông tin (đúng BookingStep.CONFIRM thật, xem
// VoiceAssistantContext), hiện thẻ xác nhận rõ ràng thay vì tự đặt xe ngay. Chỉ hiện
// field có dữ liệu THẬT từ backend (pickup/destination/loại xe/giá) — không có
// passenger_count/service tier/note/pickup_time vì BookingProgress thật hiện chưa có
// những field này (xem mustdo.md).
export const BookingConfirmationModal: React.FC = () => {
  const { showConfirmationModal, bookingProgress, dismissConfirmation, confirmBooking, status } = useVoiceAssistant();

  if (!showConfirmationModal || !bookingProgress) return null;

  const isConfirming = status === "processing";
  const fareLabel = formatFare(bookingProgress.fare_amount, bookingProgress.currency);

  return (
    <div className="absolute inset-0 z-20 flex items-end md:items-center justify-center p-3 md:p-6">
      <div className="absolute inset-0 bg-black/40 dark:bg-black/60 rounded-[inherit]" onClick={dismissConfirmation} />
      <div className="relative z-10 w-full max-w-sm bg-white rounded-2xl shadow-2xl border border-slate-200/80 overflow-hidden dark:bg-[#12161A] dark:border-white/10">
        <div className="px-5 pt-5 pb-4 border-b border-slate-100 dark:border-white/10">
          <h3 className="text-sm font-bold text-[#191C1E] dark:text-white uppercase tracking-wide">
            Xác nhận chuyến đi
          </h3>
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
            Kiểm tra lại thông tin trước khi AloSM tìm tài xế cho anh/chị.
          </p>
        </div>

        <div className="px-5 py-4 space-y-3">
          {bookingProgress.pickup && (
            <div className="flex items-start gap-3">
              <MapPin className="w-4 h-4 text-[#00C9B7] mt-0.5 shrink-0" />
              <div>
                <p className="text-[11px] font-bold text-slate-400 dark:text-slate-500 uppercase tracking-wide">
                  Điểm đón
                </p>
                <p className="text-sm font-semibold text-[#191C1E] dark:text-slate-100">
                  {bookingProgress.pickup.label}
                </p>
              </div>
            </div>
          )}
          {bookingProgress.destination && (
            <div className="flex items-start gap-3">
              <Navigation className="w-4 h-4 text-[#008F88] dark:text-[#00C9B7] mt-0.5 shrink-0" />
              <div>
                <p className="text-[11px] font-bold text-slate-400 dark:text-slate-500 uppercase tracking-wide">
                  Điểm đến
                </p>
                <p className="text-sm font-semibold text-[#191C1E] dark:text-slate-100">
                  {bookingProgress.destination.label}
                </p>
              </div>
            </div>
          )}
          {bookingProgress.vehicle_type && (
            <div className="flex items-start gap-3">
              <Car className="w-4 h-4 text-slate-400 dark:text-slate-500 mt-0.5 shrink-0" />
              <div>
                <p className="text-[11px] font-bold text-slate-400 dark:text-slate-500 uppercase tracking-wide">
                  Loại xe
                </p>
                <p className="text-sm font-semibold text-[#191C1E] dark:text-slate-100">
                  {vehicleLabel(bookingProgress.vehicle_type)}
                </p>
              </div>
            </div>
          )}
          {fareLabel && (
            <div className="flex items-start gap-3">
              <Wallet className="w-4 h-4 text-slate-400 dark:text-slate-500 mt-0.5 shrink-0" />
              <div>
                <p className="text-[11px] font-bold text-slate-400 dark:text-slate-500 uppercase tracking-wide">
                  Giá dự kiến
                </p>
                <p className="text-sm font-bold text-[#191C1E] dark:text-white">{fareLabel}</p>
              </div>
            </div>
          )}
        </div>

        <div className="px-5 pb-5 pt-1 flex gap-2">
          <button
            type="button"
            onClick={dismissConfirmation}
            disabled={isConfirming}
            className="flex-1 inline-flex items-center justify-center gap-1.5 rounded-xl border border-slate-200 px-4 py-2.5 text-sm font-semibold text-slate-600 hover:bg-slate-50 disabled:opacity-50 dark:border-white/10 dark:text-slate-300 dark:hover:bg-white/5"
          >
            <Pencil className="w-3.5 h-3.5" />
            Chỉnh sửa
          </button>
          <button
            type="button"
            onClick={() => void confirmBooking()}
            disabled={isConfirming}
            className="flex-1 rounded-xl bg-[#00C9B7] px-4 py-2.5 text-sm font-bold text-[#0B0E11] hover:opacity-90 disabled:opacity-60"
          >
            {isConfirming ? "Đang đặt xe…" : "Xác nhận đặt xe"}
          </button>
        </div>
      </div>
    </div>
  );
};
