export const BOOKING_STATE_TOPIC = "alosm.booking_state.v1";
export const TRANSCRIPT_REWRITE_TOPIC = "alosm.transcript_rewrite.v1";

export type TranscriptRewriteEvent = {
  schema_version: "1";
  item_id: string;
  raw_text: string;
  normalized_text: string;
  applied: boolean;
  status: string;
  duration_ms: number | null;
};

export type PlaceState = {
  place_id: string;
  display_name: string;
  address: string;
  provider: string;
  city?: string | null;
};

export type QuoteState = {
  quote_id: string;
  fare_amount: number;
  currency: string;
  distance_km: number;
  eta_minutes: number;
  estimated: boolean;
};

export type BookingResultState = {
  booking_id: string;
  status: string;
  estimated_fare: number;
  currency: string;
  eta_minutes: number;
};

export type VoiceFailureState = {
  code: string;
  message: string;
  retryable: boolean;
  fallback_action: "repeat_or_text" | "retry" | "handoff" | "none";
};

export type HandoffState = {
  handoff_id: string;
  status: "pending" | "accepted" | "connected" | "resolved" | "failed";
  reason_code: string;
};

export type BookingState = {
  schema_version: "1";
  revision: number;
  pickup: PlaceState | null;
  destination: PlaceState | null;
  vehicle_type: "MOTORBIKE" | "CAR_4" | "CAR_7" | "LUXURY" | null;
  quote: QuoteState | null;
  confirmation_status: "not_requested" | "awaiting" | "confirmed";
  booking: BookingResultState | null;
  locked_fields?: Array<"pickup" | "destination" | "vehicle_type">;
  failure?: VoiceFailureState | null;
  handoff?: HandoffState | null;
  recovered?: boolean;
};
