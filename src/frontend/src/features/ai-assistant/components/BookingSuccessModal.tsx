import React from "react";
import { X } from "lucide-react";
import { useVoiceAssistant } from "@/features/ai-assistant/context/useVoiceAssistant";
import { BookingSuccessPanel } from "@/features/ai-assistant/components/BookingSuccessPanel";

// Mục 10-11: kết quả đặt xe (thành công/thất bại) hiện thành thẻ nổi trong popup —
// tái dùng nguyên BookingSuccessPanel đã có sẵn (đủ cả 2 nhánh SUCCESS/FAILED, sao
// đánh giá, CTA đặt xe mới/kết thúc phiên), chỉ bọc thêm khung modal.
export const BookingSuccessModal: React.FC = () => {
  const { showSuccessModal, completedBooking, closeSuccessModal, submitRating, endSession, newSession, isSubmittingRating } =
    useVoiceAssistant();

  if (!showSuccessModal || !completedBooking) return null;

  return (
    <div className="absolute inset-0 z-20 flex items-end md:items-center justify-center p-3 md:p-6">
      <div className="absolute inset-0 bg-black/40 dark:bg-black/60 rounded-[inherit]" onClick={closeSuccessModal} />
      <div className="relative z-10 w-full max-w-sm">
        <div className="flex justify-end mb-1.5">
          <button
            type="button"
            onClick={closeSuccessModal}
            aria-label="Đóng"
            className="w-7 h-7 rounded-full bg-white/90 text-slate-500 grid place-items-center shadow hover:text-slate-800 dark:bg-[#12161A] dark:text-slate-400 dark:hover:text-white"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
        <BookingSuccessPanel
          booking={completedBooking}
          onSubmitRating={submitRating}
          onEndSession={() => void endSession()}
          onNewSession={() => void newSession()}
          isSubmittingRating={isSubmittingRating}
        />
      </div>
    </div>
  );
};
