import { fetchApi } from "@/app/config/api";
import { getAccessToken } from "@/features/auth/storage";

export interface TripStatusResponse {
  trip_id: string;
  status: "SEARCHING_DRIVER" | "DRIVER_ASSIGNED" | "ARRIVING" | "ON_TRIP" | "COMPLETED";
  eta_minutes: number | null;
  driver_name: string | null;
  vehicle: string | null;
  license_plate: string | null;
  driver_rating: number | null;
  driver_phone: string | null;
}

function authHeader(): HeadersInit {
  const token = getAccessToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}

export function getTripStatus(sessionId: string): Promise<TripStatusResponse> {
  return fetchApi<TripStatusResponse>(`/api/v1/trips/status?session_id=${encodeURIComponent(sessionId)}`, {
    headers: authHeader(),
  });
}

export const TRIP_STATUS_TEXT: Record<TripStatusResponse["status"], string> = {
  SEARCHING_DRIVER: "Đang tìm tài xế phù hợp",
  DRIVER_ASSIGNED: "Tài xế đã nhận chuyến",
  ARRIVING: "Tài xế đang di chuyển tới điểm đón",
  ON_TRIP: "Đang trong chuyến đi",
  COMPLETED: "Chuyến đi đã hoàn thành",
};
