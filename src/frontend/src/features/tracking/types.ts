export interface DriverInfo {
  name: string;
  avatar: string;
  vehicleName: string;
  licensePlate: string;
  rating: number;
  phone: string;
}

export interface TrackingTripDetails {
  bookingId: string;
  status: "searching" | "accepted" | "arriving" | "in_transit" | "completed";
  statusText: string;
  pickup: string;
  destination: string;
  eta: string;
  driver?: DriverInfo;
}
