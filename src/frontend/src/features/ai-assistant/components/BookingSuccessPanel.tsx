import React, { useState } from "react";
import { CheckCircle2, RotateCcw, Star, XCircle } from "lucide-react";

export type BookingLifecycleStatus = "PENDING" | "FAILED" | "SUCCESS";

export type CompletedBooking = {
  booking_id: string;
  estimated_fare?: number;
  lifecycle_status: BookingLifecycleStatus;
};

type Props = {
  booking: CompletedBooking;
  onSubmitRating: (rating: number) => Promise<void>;
  onEndSession: () => void;
  onNewSession: () => void;
  isSubmittingRating?: boolean;
};

export const BookingSuccessPanel: React.FC<Props> = ({
  booking,
  onSubmitRating,
  onEndSession,
  onNewSession,
  isSubmittingRating = false,
}) => {
  const [hovered, setHovered] = useState(0);
  const [rating, setRating] = useState(0);
  const [submitted, setSubmitted] = useState(false);

  const handleRate = async (value: number) => {
    setRating(value);
    await onSubmitRating(value);
    setSubmitted(true);
  };

  if (booking.lifecycle_status === "FAILED") {
    return (
      <div className="mt-4 rounded-2xl border border-rose-200 bg-rose-50 p-5 dark:border-rose-500/30 dark:bg-rose-500/10">
        <div className="flex items-start gap-3">
          <XCircle className="w-6 h-6 text-rose-600 dark:text-rose-400 shrink-0 mt-0.5" />
          <div>
            <p className="font-semibold text-rose-900 dark:text-rose-200">Đặt xe thất bại</p>
            <p className="text-sm text-rose-800 dark:text-rose-300 mt-1">
              Em chưa hoàn tất được chuyến xe. Anh/chị có thể thử xác nhận lại hoặc bắt đầu phiên mới.
            </p>
            <div className="flex flex-wrap gap-2 mt-4">
              <button
                type="button"
                onClick={onNewSession}
                className="inline-flex items-center gap-2 rounded-xl bg-[#00C9B7] px-4 py-2 text-sm font-semibold text-white hover:opacity-90"
              >
                <RotateCcw className="w-4 h-4" />
                Phiên mới
              </button>
              <button
                type="button"
                onClick={onEndSession}
                className="rounded-xl border border-rose-300 px-4 py-2 text-sm font-semibold text-rose-800 hover:bg-rose-100 dark:border-rose-500/40 dark:text-rose-300 dark:hover:bg-rose-500/10"
              >
                Kết thúc phiên
              </button>
            </div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="mt-4 rounded-2xl border border-emerald-200 bg-emerald-50 p-5 dark:border-emerald-500/30 dark:bg-emerald-500/10">
      <div className="flex items-start gap-3">
        <CheckCircle2 className="w-6 h-6 text-emerald-600 dark:text-emerald-400 shrink-0 mt-0.5" />
        <div className="flex-1">
          <p className="font-semibold text-emerald-900 dark:text-emerald-200">Đặt xe thành công</p>
          <p className="text-sm text-emerald-800 dark:text-emerald-300 mt-1">
            Mã chuyến: <span className="font-mono font-semibold">{booking.booking_id}</span>
            {booking.estimated_fare != null && (
              <> · Ước tính {booking.estimated_fare.toLocaleString("vi-VN")}đ</>
            )}
          </p>

          <div className="mt-4">
            <p className="text-sm font-medium text-slate-700 dark:text-slate-300">
              {submitted ? "Cảm ơn anh/chị đã đánh giá!" : "Anh/chị hài lòng thế nào?"}
            </p>
            <div className="flex gap-1 mt-2" role="group" aria-label="Đánh giá sao">
              {[1, 2, 3, 4, 5].map((value) => (
                <button
                  key={value}
                  type="button"
                  disabled={isSubmittingRating || submitted}
                  onMouseEnter={() => setHovered(value)}
                  onMouseLeave={() => setHovered(0)}
                  onClick={() => handleRate(value)}
                  className="p-1 rounded-lg hover:bg-emerald-100 dark:hover:bg-emerald-500/20 disabled:opacity-60 transition"
                  aria-label={`${value} sao`}
                >
                  <Star
                    className={`w-7 h-7 ${
                      value <= (hovered || rating)
                        ? "fill-amber-400 text-amber-400"
                        : "text-slate-300 dark:text-slate-600"
                    }`}
                  />
                </button>
              ))}
            </div>
          </div>

          <p className="text-sm text-slate-600 dark:text-slate-300 mt-4">Anh/chị muốn tiếp tục thế nào?</p>
          <div className="flex flex-wrap gap-2 mt-3">
            <button
              type="button"
              onClick={onNewSession}
              className="inline-flex items-center gap-2 rounded-xl bg-[#00C9B7] px-4 py-2 text-sm font-semibold text-white hover:opacity-90"
            >
              <RotateCcw className="w-4 h-4" />
              Đặt xe mới
            </button>
            <button
              type="button"
              onClick={onEndSession}
              className="rounded-xl border border-emerald-300 px-4 py-2 text-sm font-semibold text-emerald-900 hover:bg-emerald-100 dark:border-emerald-500/40 dark:text-emerald-200 dark:hover:bg-emerald-500/10"
            >
              Kết thúc phiên
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
