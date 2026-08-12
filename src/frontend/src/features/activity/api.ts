import { fetchApi } from "@/app/config/api";
import { getAccessToken } from "@/features/auth/storage";

export interface BookingLocation {
  display_name?: string;
  name?: string;
  address?: string;
}

export interface BookingSummary {
  booking_id: string;
  status: string;
  estimated_fare: number | null;
  currency: string;
  pickup: BookingLocation | null;
  destination: BookingLocation | null;
  vehicle_type: string | null;
  created_at: string | null;
}

function authHeader(): HeadersInit {
  const token = getAccessToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}

export function listBookings(): Promise<BookingSummary[]> {
  return fetchApi<BookingSummary[]>("/api/v1/bookings", { headers: authHeader() });
}

export function locationLabel(location: BookingLocation | null, fallback: string): string {
  if (!location) return fallback;
  return location.display_name || location.name || location.address || fallback;
}

const STATUS_TEXT: Record<string, string> = {
  SEARCHING_DRIVER: "Đang tìm tài xế",
  DRIVER_ASSIGNED: "Tài xế đã nhận",
  ARRIVING: "Tài xế đang đến",
  ON_TRIP: "Đang di chuyển",
  COMPLETED: "Hoàn thành",
  ALREADY_CREATED: "Đã đặt",
};

export function statusLabel(status: string): string {
  return STATUS_TEXT[status] || status;
}
