import { fetchApi } from "@/app/config/api";
import { getAccessToken } from "@/features/auth/storage";

export interface RideSession {
  session_id: string;
  status: string;
  channel: string;
  created_at: string;
}

export interface BookingFieldProgress {
  label: string;
  resolved: boolean;
  place_id?: string | null;
}

export type BookingLifecycleStatus = "PENDING" | "FAILED" | "SUCCESS";

export interface BookingProgress {
  pickup?: BookingFieldProgress | null;
  destination?: BookingFieldProgress | null;
  vehicle_type?: string | null;
  missing_field?: "pickup" | "destination" | "vehicle_type" | "fare_estimate" | "phone_number" | null;
  lifecycle_status?: BookingLifecycleStatus | null;
  fare_amount?: number | null;
  currency?: string | null;
}

export interface RideBooking {
  booking_id: string;
  status: string;
  lifecycle_status?: BookingLifecycleStatus;
  estimated_fare: number;
}

export interface RideTurn {
  message_id: string;
  action: "ASK_USER" | "RESPOND" | "HANDOFF" | "END_SESSION";
  message: string;
  state: Record<string, unknown> & {
    booking_progress?: BookingProgress | null;
    booking_lifecycle_status?: BookingLifecycleStatus | null;
    // "RIDE_BOOKING" + "CONFIRM" (xem src/agents/schemas.py::WorkflowType,
    // src/agents/workflows/booking_models.py::BookingStep) — tín hiệu THẬT, chính
    // xác nhất để biết agent đang chờ xác nhận đặt xe (dùng để tự mở
    // BookingConfirmationModal), đáng tin hơn suy luận gián tiếp từ
    // booking_progress.missing_field.
    current_workflow?: string | null;
    current_step?: string | null;
  };
  booking?: RideBooking | null;
}

function authHeader(): HeadersInit {
  const token = getAccessToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}

export function createRideSession(): Promise<RideSession> {
  return fetchApi<RideSession>("/api/v1/sessions", {
    method: "POST",
    headers: authHeader(),
    body: JSON.stringify({ channel: "WEB_VOICE", device_id: "browser" }),
  });
}

export function getRideSession(sessionId: string): Promise<RideSession> {
  return fetchApi<RideSession>(`/api/v1/sessions/${sessionId}`, {
    headers: authHeader(),
  });
}

export function sendRideMessage(sessionId: string, message: string, source: "TEXT" | "VOICE", sttConfidence?: number): Promise<RideTurn> {
  return fetchApi<RideTurn>(`/api/v1/sessions/${sessionId}/messages`, {
    method: "POST",
    headers: authHeader(),
    body: JSON.stringify({ message, source, stt_confidence: sttConfidence }),
  });
}

export function endRideSession(sessionId: string): Promise<unknown> {
  return fetchApi(`/api/v1/sessions/${sessionId}/end`, {
    method: "POST",
    headers: authHeader(),
    body: JSON.stringify({ reason: "USER_ENDED" }),
  });
}

export function submitSessionFeedback(
  sessionId: string,
  rating: number,
  comment?: string,
): Promise<{ session_id: string; feedback: { rating: number; comment?: string } }> {
  return fetchApi(`/api/v1/sessions/${sessionId}/feedback`, {
    method: "POST",
    headers: authHeader(),
    body: JSON.stringify({ rating, comment }),
  });
}
