import { fetchApi } from "@/app/config/api";
import { getAccessToken } from "@/features/auth/storage";
import type { RideBooking, RideSession, RideTurn } from "@/features/ride/api";

// BookingPage là 1 form hướng dẫn, lái CHÍNH engine hội thoại thật (Core Agent) thay
// vì có luồng đặt xe riêng — tạo session mới, gửi 1 câu mô tả tuyến đường + loại xe,
// rồi gửi "Đúng" để xác nhận. Tái dùng 100% logic đã test kỹ ở
// `src/agents/workflows/booking.py` (resolve địa điểm, xác nhận, tạo booking) thay vì
// xây 1 đường đặt xe riêng cho form — không trùng lặp business logic.
const VEHICLE_LABEL: Record<"taxi" | "plus" | "premium", string> = {
  taxi: "4 chỗ",
  plus: "7 chỗ",
  premium: "hạng sang",
};

function authHeader(): HeadersInit {
  const token = getAccessToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}

function createFormSession(): Promise<RideSession> {
  return fetchApi<RideSession>("/api/v1/sessions", {
    method: "POST",
    headers: authHeader(),
    body: JSON.stringify({ channel: "WEB_TEXT", device_id: "booking-form" }),
  });
}

function sendMessage(sessionId: string, message: string): Promise<RideTurn> {
  return fetchApi<RideTurn>(`/api/v1/sessions/${sessionId}/messages`, {
    method: "POST",
    headers: authHeader(),
    body: JSON.stringify({ message, source: "TEXT" }),
  });
}

export interface FormBookingResult {
  booking: RideBooking;
  sessionId: string;
}

/** Đặt xe qua form (không phải chat) — vẫn đi qua đúng dialogue engine thật. Ném lỗi
 * (Error thường, không phải ApiError) nếu agent không xác nhận được (vd chưa hiểu địa
 * chỉ) — component gọi nên hiển thị `error.message` cho người dùng thử lại. */
export async function createBookingViaForm(
  pickup: string,
  destination: string,
  serviceId: "taxi" | "plus" | "premium",
): Promise<FormBookingResult> {
  const session = await createFormSession();
  const routeMessage = `Đặt xe ${VEHICLE_LABEL[serviceId]} từ ${pickup} đến ${destination}`;
  const routeTurn = await sendMessage(session.session_id, routeMessage);
  if (routeTurn.action === "HANDOFF") {
    throw new Error(routeTurn.message || "Không thể xử lý yêu cầu, vui lòng thử lại hoặc liên hệ tổng đài.");
  }

  const confirmTurn = await sendMessage(session.session_id, "Đúng");
  if (confirmTurn.action !== "RESPOND" || !confirmTurn.booking) {
    throw new Error(confirmTurn.message || "Chưa xác nhận được đặt xe, vui lòng thử lại.");
  }

  return { booking: confirmTurn.booking, sessionId: session.session_id };
}
