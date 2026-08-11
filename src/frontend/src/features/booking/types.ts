export type VehicleType = "bike" | "car" | "premium" | "delivery";

export interface ServiceOption {
  id: VehicleType;
  name: string;
  description: string;
  basePrice: number;
  eta: string;
  iconName: string;
  popular?: boolean;
}

export interface BookingDetails {
  pickup: string;
  destination: string;
  serviceType: VehicleType;
  distanceKm: number;
  estimatedPrice: number;
  paymentMethod: "cash" | "momo" | "card" | "vnpay";
  note?: string;
}
